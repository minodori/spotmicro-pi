#!/usr/bin/env python3
"""tee 처럼 화면에 흘리면서, 파일에는 **바뀐 것만** 남긴다.

    python RaspberryPi/start_automatic_gait.py 2>&1 | tools/ringlog.py ~/gait.log

보행 스크립트는 루프마다 30 줄 남짓을 찍는다 (result_dict + jointAngles +
서보값 12 + 상태판). 39Hz 라 8/25 세션의 gait.log 가 800MB 였는데, 그중 대부분은
로봇이 가만히 서서 같은 값을 다시 찍은 것이었다.

시간창(최근 N 초만 남기기)을 먼저 만들었다가 버렸다. 걷고 나서 잠깐 서 있으면
그 정지 시간이 방금 걸은 기록을 밀어낸다. 8/25 에 실제로 앞 조건들을 잃었다.
지울 기준은 오래된 것이 아니라 **바뀌지 않은 것**이다.

그래서 프레임(루프 한 번의 출력) 단위로 직전과 비교해서, 같으면 쓰지 않고
횟수만 센다. 서 있으면 몇 시간이든 한 줄로 남고, 걸으면 위상이 매번 달라
전부 남는다. **시간 제한이 없으므로 어제 조건도 그대로 있다.**

파일은 append 로만 쓴다 - 메모리에 쌓이지 않고 `tail -f` 도 정상이다.
걷는 동안 분당 4MB 남짓 늘어난다 (정지 중에는 늘지 않는다).

  ringlog.py <파일> [--new]     --new 면 기존 파일을 비우고 시작한다

이어쓰기가 기본이라 한 파일에 여러 세션이 쌓인다. 그래서 실행할 때마다 구분줄을
넣는다 - 파일 가운데를 열면 어느 세션인지 알 수 없어서 값이 굳은 것처럼 보인다
(8/25 에 실제로 그렇게 읽혔다).

(이름은 시간창 시절 것이 남았다. 촬영 주간에 명령줄을 바꾸지 않으려고 그대로 둔다.)

프레임 경계는 result_dict 줄이다. 루프마다 정확히 한 번, 맨 앞에 찍힌다.
처음에는 상태판의 '=' 줄로 잡았는데 그것은 루프당 두 번 나와서, 프레임이
상태판 / 나머지로 번갈아 잡히고 서로 다른 종류끼리 비교되어 **중복 제거가 한 번도
걸리지 않았다** (8/25, 37MB / 축약 0 건). 그 줄이 안 보이면 줄 단위로 강등한다.
"""
import os
import sys
import time


MARK = "'IDstepLength'"     # 루프 맨 앞의 result_dict. 루프당 정확히 한 번 나온다


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        return 1
    path = os.path.expanduser(sys.argv[1])
    mode = 'w' if '--new' in sys.argv[2:] else 'a'

    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass

    out = open(path, mode)
    out.write("\n===== 세션 시작 %s =====\n"
              % time.strftime("%Y-%m-%d %H:%M:%S"))
    out.flush()

    cur = []            # 모으는 중인 프레임
    prev = None         # 직전에 파일에 쓴 프레임
    repeat = 0          # 그 뒤로 같은 프레임이 몇 번 왔는가
    sawMark = False

    def commit():
        """모은 프레임을 확정한다. 직전과 같으면 세기만 한다."""
        nonlocal cur, prev, repeat
        if not cur:
            return
        if cur == prev:
            repeat += 1
        else:
            if repeat:
                out.write("... 같은 상태 %d 회 반복 ...\n" % repeat)
                repeat = 0
            out.writelines(cur)
            out.flush()
            prev = cur
        cur = []

    try:
        for line in sys.stdin:
            sys.stdout.write(line)          # tee 와 같다. 화면이 먼저다
            if MARK in line:
                commit()                    # 새 루프가 시작됐다 - 앞 프레임을 확정
                sawMark = True
            cur.append(line)
            if not sawMark:
                commit()                    # 아직 마커를 못 봤다 - 줄 단위로 강등
    except KeyboardInterrupt:
        pass
    finally:
        try:
            commit()
            if repeat:
                out.write("... 같은 상태 %d 회 반복 ...\n" % repeat)
            out.write("===== 세션 끝 %s =====\n"
                      % time.strftime("%Y-%m-%d %H:%M:%S"))
            out.close()
        except OSError:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
