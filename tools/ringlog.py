#!/usr/bin/env python3
"""tee 처럼 화면에 그대로 흘리면서, 파일에는 최근 N 초 분량만 남긴다.

    python RaspberryPi/start_automatic_gait.py 2>&1 | tools/ringlog.py ~/gait.log 60

보행 스크립트는 루프마다 17 줄을 찍는다 (result_dict 1 + jointAngles 4 +
서보값 12). 39Hz 이므로 시간당 2 백만 줄, 하루 켜 두면 수백 MB 가 된다.
8/25 세션의 gait.log 가 800MB 였고 그중 실제로 걸은 구간은 몇 분이었다.

tee 는 append 만 하므로 앞을 잘라낼 수 없다. 여기서는 최근 줄을 메모리에
들고 있다가 주기적으로 파일을 다시 쓴다. 파일 크기는 창 크기에서 멈춘다.

**tee 와 똑같이 화면에도 그대로 내보낸다.** 이게 빠지면 상태판이 안 보이고,
파라미터를 바꿔도 네발지지·슬루가 안 변하는 것처럼 보인다 (8/25 실제로 그랬다).

파일을 rename 으로 갈아끼우므로 `tail -f` 는 첫 교체에서 멈춘다. 파일로 볼 때는
이름을 따라가는 `tail -F` 를 쓸 것. 다만 화면에 그대로 나오므로 보통은 필요 없다.

  ringlog.py <파일> [창(초)] [다시쓰는 주기(초)]

Ctrl-C 로 보행을 끝내면 그 시점의 창이 파일에 남는다 - 무엇을 하다 멈췄는지
보려면 그 구간이면 충분하다. 전체가 필요하면 그냥 tee 를 쓰면 된다.
"""
import collections
import os
import sys
import time


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        return 1
    path = os.path.expanduser(sys.argv[1])
    window = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
    every = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0

    # 파이프로 넘어온 줄을 화면에 즉시 보여야 한다. 터미널이면 파이썬이 알아서
    # 줄 단위로 흘려보내지만, 화면 출력까지 파이프로 다시 받는 경우를 위해 명시한다.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass

    buf = collections.deque()          # (시각, 줄)
    nextWrite = time.time() + every

    def flush():
        cut = time.time() - window
        while buf and buf[0][0] < cut:
            buf.popleft()
        # 임시 파일에 쓰고 rename 한다. 도중에 죽어도 반쯤 쓰인 파일이 남지 않고,
        # tail -f 가 붙어 있어도 안전하다.
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            f.writelines(line for _, line in buf)
        os.replace(tmp, path)

    try:
        for line in sys.stdin:
            now = time.time()
            sys.stdout.write(line)      # tee 와 같다. 화면이 먼저다
            buf.append((now, line))
            if now >= nextWrite:
                flush()
                nextWrite = now + every
    except KeyboardInterrupt:
        pass
    finally:
        try:
            flush()
        except OSError:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
