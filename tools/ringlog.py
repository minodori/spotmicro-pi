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

(이름은 시간창 시절 것이 남았다. 촬영 주간에 명령줄을 바꾸지 않으려고 그대로 둔다.)

프레임 경계는 상태판의 '=' 줄이다. 이 도구는 이 프로그램 전용이므로 그 정도의
결합은 의도한 것이다. 구분선이 안 보이면 줄 단위 비교로 자동 강등한다.
"""
import os
import sys


DELIM = '=' * 20        # 상태판 구분선의 앞부분. 길이가 바뀌어도 걸린다


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
    cur = []            # 모으는 중인 프레임
    prev = None         # 직전에 파일에 쓴 프레임
    repeat = 0          # 그 뒤로 같은 프레임이 몇 번 왔는가
    sawDelim = False

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
            cur.append(line)
            # 구분선을 못 봤으면 줄 하나를 프레임으로 친다
            if line.startswith(DELIM) or not sawDelim:
                if line.startswith(DELIM):
                    sawDelim = True
                commit()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            commit()
            if repeat:
                out.write("... 같은 상태 %d 회 반복 ...\n" % repeat)
            out.close()
        except OSError:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
