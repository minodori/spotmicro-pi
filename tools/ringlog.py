#!/usr/bin/env python3
"""tee 처럼 화면에 흘리면서, 파일에는 최근 N 초 "움직인" 분량만 남긴다.

    python RaspberryPi/start_automatic_gait.py 2>&1 | tools/ringlog.py ~/gait.log 60

보행 스크립트는 루프마다 17 줄을 찍는다 (result_dict 1 + jointAngles 4 +
서보값 12) + 상태판. 39Hz 라 8/25 세션의 gait.log 가 800MB 였고, 그중 실제로
걸은 구간은 몇 분이었다.

**시간창으로 자르면 안 된다.** 걷고 나서 1 분 가만히 서 있으면 그 1 분이 방금
걸은 기록을 밀어낸다. 지워야 할 것은 오래된 것이 아니라 **반복되는 것**이다.

그래서 여기서는 프레임(루프 한 번의 출력) 단위로 보고, 직전 프레임과 내용이
똑같으면 저장하지 않고 횟수만 센다. 서 있으면 매 프레임이 같으므로 몇 시간을
서 있어도 한 프레임 + 반복 횟수로 남는다. 걸으면 위상이 달라 프레임마다
다르므로 전부 남는다. 창 크기는 "움직인 시간" 으로 센다.

  ringlog.py <파일> [창(움직인 초)] [다시쓰는 주기(초)]

프레임 경계는 상태판의 '=' 줄이다. 이 도구는 이 프로그램 전용이므로 그 정도의
결합은 의도한 것이다. 구분선이 안 보이면 줄 단위 시간창으로 자동 강등한다.

파일을 rename 으로 갈아끼우므로 `tail -f` 는 첫 교체에서 멈춘다. 파일로 볼 때는
이름을 따라가는 `tail -F` 를 쓸 것. 화면에 그대로 나오므로 보통은 필요 없다.
"""
import collections
import os
import sys
import time

DELIM = '=' * 20        # 상태판 구분선의 앞부분. 길이가 바뀌어도 걸린다
IDLE_CAP = 0.10         # 한 프레임이 창에서 차지할 수 있는 최대 시간(초).
                        # 이것 때문에 몇 시간을 서 있어도 0.1 초로만 계산된다


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        return 1
    path = os.path.expanduser(sys.argv[1])
    window = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
    every = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0

    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass

    frames = collections.deque()   # (차지시간, 줄목록, 반복횟수)
    charged = 0.0                  # frames 가 차지한 총 시간
    cur = []                       # 모으는 중인 프레임
    lastAt = time.time()
    nextWrite = lastAt + every
    sawDelim = False

    def commit(now):
        """모은 프레임을 확정한다. 직전과 같으면 횟수만 올린다."""
        nonlocal cur, charged, lastAt
        if not cur:
            return
        if frames and frames[-1][1] == cur:
            frames[-1][2] += 1                  # 서 있는 중 - 자리를 더 쓰지 않는다
        else:
            dt = min(now - lastAt, IDLE_CAP)
            frames.append([dt, cur, 1])
            charged += dt
            while charged > window and len(frames) > 1:
                charged -= frames.popleft()[0]
        lastAt = now
        cur = []

    def flush():
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            for _, lines, n in frames:
                f.writelines(lines)
                if n > 1:
                    f.write("... 같은 상태 %d 회 반복 (기록 생략) ...\n" % n)
        os.replace(tmp, path)

    try:
        for line in sys.stdin:
            sys.stdout.write(line)          # tee 와 같다. 화면이 먼저다
            now = time.time()
            if line.startswith(DELIM):
                sawDelim = True
                cur.append(line)
                commit(now)
            else:
                cur.append(line)
                # 구분선을 못 봤으면 줄 하나를 프레임으로 친다 (시간창으로 강등)
                if not sawDelim:
                    commit(now)
            if now >= nextWrite:
                flush()
                nextWrite = now + every
    except KeyboardInterrupt:
        pass
    finally:
        try:
            commit(time.time())
            flush()
        except OSError:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
