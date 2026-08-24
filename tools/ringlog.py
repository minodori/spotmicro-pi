#!/usr/bin/env python3
"""표준입력을 파일에 쓰되 최근 N 초 분량만 남긴다.

    python RaspberryPi/start_automatic_gait.py 2>&1 | tools/ringlog.py ~/gait.log 60

보행 스크립트는 루프마다 17 줄을 찍는다 (result_dict 1 + jointAngles 4 +
서보값 12). 39Hz 이므로 시간당 2 백만 줄, 하루 켜 두면 수백 MB 가 된다.
8/25 세션의 gait.log 가 800MB 였고 그중 실제로 걸은 구간은 몇 분이었다.

tee 는 append 만 하므로 앞을 잘라낼 수 없다. 여기서는 최근 줄을 메모리에
들고 있다가 주기적으로 파일을 다시 쓴다. tail -f 로 보는 것은 그대로 되고,
파일 크기는 창 크기에서 멈춘다.

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
