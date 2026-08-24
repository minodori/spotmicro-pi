"""보행 튜닝 파라미터의 저장/복원.

트림을 어렵게 찾아놓고 재시작하면 0 으로 돌아가는 문제를 없앤다.
코드가 아니라 실행 상태이므로 홈 디렉터리에 둔다 (rsync/git 과 무관하게 유지된다).

저장 대상은 "실물을 보며 맞추는" 값들이다. 발 위치(Fo/Ro/Spf/Spr)처럼 기하로
확정되는 값은 코드에 남긴다.

궤적 타이밍은 원래 코드에 두었으나 실기에서 찾을 수밖에 없는 값이라 여기로 옮겼다.
다만 t1/t3 을 그대로 노출하지는 않는다 — 아래 Tt/duty 주석 참조.
"""
import json
import os
import tempfile

PARAM_FILE = os.path.expanduser("~/.spotmicro_gait.json")

# 키 -> (기본값, 최소, 최대)
#
# 범위는 계산으로 정했다 (오프셋 [179,88,81,13,87,88,179,96,91,26,81,81] 기준).
#
#   height : bodyPosition y = 40 + height.  어깨축~발바닥 수직거리가 140+height 다.
#            Upper축~발 거리 H = 120 + height 이고, 이 둘은 명령하는 기하라
#            링크 길이와 무관하다. 바뀌는 것은 그 자세에서의 무릎 내각이다.
#
#            2026-08-21 재실측(l3 125->110, l4 138->135)으로 다리 최대 도달이
#            263 -> 245mm 로 줄었다. H 가 그것을 넘으면 IK 가 풀리지 않는다.
#
#            **이 값의 의미가 바뀌었다.** 옛 코드는 다리를 길다고 믿었으므로
#            height 110 을 명령하면 실제로는 H 214.5mm 자세로 섰다 - 새 코드의
#            height 95 에 해당한다. 8/20 에 50mm/s 로 걸은 것이 그 자세다.
#            그래서 기본값을 110 -> 95 로 내린다. 같은 숫자가 아니라 같은 자세다.
#
#            상한은 도달 한계(125)가 아니라 슬루가 정한다. 다리를 뻗을수록
#            특이점에 가까워져 작은 발끝 이동에 관절이 크게 돈다:
#              height  80 -> 무릎 내각 109도,  슬루 309도/s (57%)
#              height  95 -> 내각 121도,       슬루 366도/s (67%)   <- 기본값
#              height 100 -> 내각 127도,       슬루 397도/s (73%)
#              height 110 -> 내각 139도,       슬루 516도/s (95%)   <- 위험
#              height 125 -> 내각 180도,       도달 한계 그 자체
#            105 를 상한으로 둔다. 그 위는 보폭을 조금만 키워도 정격을 넘는다.
#            조합 위험은 제어 루프가 실시간 감시한다 (servoRotate 반환값).
#   Sh     : 발 들어올림. 무릎 요구 슬루율이 Sh*pi/t3 이다.
#            상한을 30 -> 40 으로 올렸다. 슬루율은 Sh 가 아니라 Sh/t3 이 정하므로,
#            t3 를 함께 늘리면 40 도 서보 정격 안에 들어온다 (아래 duty 주석).
#   IDtrim : 값 자체보다 다리 사이 "차이" 가 중요하다. 차이가 Sh 에 육박하면 높은 발이
#            접지하지 못해 반대 대각선으로 넘어진다.
#
#            기본값이 피치 +4 다 (앞 두 다리를 4mm 짧게, 뒤 두 다리를 4mm 길게).
#            0 이 아닌 이유는 이 로봇의 무게중심이 대각 지지선보다 10.4mm 뒤에
#            있기 때문이다 (rl/validate_mjcf.py 게이트 7). 트롯은 주기의 일부를
#            대각선 두 발로만 버티는데, 그 선보다 무게중심이 뒤면 뒤로 넘어간다.
#            실기에서 매번 손으로 넣던 값이라 시작점으로 옮겼다.
#
#            근본 해결은 발 위치다. Fo 117.5->107.5, Ro 67.5->77.5 로 앞뒤 발을
#            10mm 씩 뒤로 옮기면 교차점이 무게중심 위로 와 트림 0 에서 균형이
#            맞는다(차이 +0.3mm). 다만 그러면 잘 걷는 설정이 통째로 바뀌므로
#            대회 마감 뒤에 한다. 더 나은 방법은 배터리·보드를 앞으로 옮겨
#            무게중심 자체를 전진시키는 것이다 (work11 §6.18, 서보 여유 손실 없음).
#
#   Tt/duty: 궤적 타이밍. t1(접지)/t3(스윙) 을 직접 노출하지 않고 이 둘로 노출한다.
#            t1/t3 은 서로 얽혀 있어 하나만 만지면 다른 축까지 움직인다 —
#            work11 §6.16.1 이 "t3 만 올리면 네발지지가 반 토막 난다" 고 적어둔 함정이다.
#            Tt 와 duty 는 서로 독립이다:
#                 전진 속도  = |Sl| / Tt          <- Tt 만 정한다
#                 네발지지   = 1 - 2*duty          <- duty 만 정한다
#                 무릎 슬루율 = Sh*pi / (Tt*duty)
#            (t1 = Tt*(1-duty),  t3 = Tt*duty)
#
#            현재값 t1/t3 = 1200/200 은 Tt=1400, duty=0.143 이다.
#            duty 0.5 가 정통 트롯(네발지지 0). IMU 없는 개루프에서는 위험하므로
#            상한을 그 값에 두되, 실제로는 0.15~0.2 근처에서 쓰게 된다.
#
#            "발을 더 높이 들되 서보에는 더 편하게" 하려면 Tt 와 duty 를 같이 올린다.
#            예: Tt 2800 / duty 0.143 / Sh 30 -> t3 400, 네발지지 71% 유지,
#                슬루율은 오히려 25% 감소. 대가는 속도이므로 Sl 을 키워 보상한다.
DEFAULTS = {
    'IDtrim': ([4.0, 4.0, -4.0, -4.0], None, None),  # 다리별 y 트림 (mm). 피치 +4
    'Sh': (20.0, 5.0, 40.0),                        # 발 들어올림 (mm)
    'height': (95.0, 60.0, 105.0),                  # bodyPosition y = 40 + height
    'Tt': (1400.0, 800.0, 3600.0),                  # 보행 한 주기 (ms)
    'duty': (0.143, 0.10, 0.50),                    # 스윙 비율 t3/Tt
}


def gaitPhases(p):
    """Tt/duty -> (t1, t3) ms. 궤적 코드가 쓰는 형태로 환산한다.

    t0/t2 는 0 이다. work11 §6.12 에서 지웠다 — 네 발이 다 닿은 채 두 발만
    멈춰 있으면 미끄러지는 것 외에 다른 해가 없다.
    """
    Tt = float(p.get('Tt', DEFAULTS['Tt'][0]))
    duty = float(p.get('duty', DEFAULTS['duty'][0]))
    t3 = Tt * duty
    return Tt - t3, t3


def supportRatio(duty):
    """네 발이 모두 접지해 있는 시간 비율. 0 이면 정통 트롯이다.

    대각 쌍이 반주기 어긋나 있으므로 스윙 구간 두 개가 겹치지 않는 한
    1 - 2*duty 가 그대로 네발지지 비율이 된다.
    """
    return max(0.0, 1.0 - 2.0 * float(duty))


def defaultParams():
    out = {}
    for k, (v, _, _) in DEFAULTS.items():
        out[k] = list(v) if isinstance(v, list) else v
    return out


def clampParams(p):
    """범위를 벗어난 값을 잘라낸다. 손으로 편집한 파일도 안전하게 받아들인다."""
    for k, (dflt, lo, hi) in DEFAULTS.items():
        if k not in p:
            p[k] = list(dflt) if isinstance(dflt, list) else dflt
            continue
        if lo is None:
            continue
        try:
            p[k] = max(lo, min(hi, float(p[k])))
        except (TypeError, ValueError):
            p[k] = dflt
    # 깨진 값은 0 이 아니라 기본 트림으로 되돌린다. 0 으로 두면 무게중심이
    # 대각 지지선보다 뒤인 채로 걷게 되어 뒤로 넘어간다 (위 IDtrim 주석).
    trim = p.get('IDtrim')
    if not isinstance(trim, list) or len(trim) != 4:
        p['IDtrim'] = list(DEFAULTS['IDtrim'][0])
    else:
        try:
            p['IDtrim'] = [float(x) for x in trim]
        except (TypeError, ValueError):
            p['IDtrim'] = list(DEFAULTS['IDtrim'][0])
    return p


def loadParams():
    """저장된 값을 읽는다. 없거나 깨졌으면 기본값."""
    try:
        with open(PARAM_FILE) as f:
            return clampParams(json.load(f))
    except (OSError, ValueError):
        return defaultParams()


def saveParams(state):
    """DEFAULTS 에 있는 키만 골라 저장한다.

    같은 디렉터리에 임시 파일로 쓰고 rename 한다. 저장 도중 전원이 끊겨도
    파일이 반쯤 쓰인 상태로 남지 않는다 (rename 은 원자적이다).
    """
    data = {k: state[k] for k in DEFAULTS if k in state}
    try:
        d = os.path.dirname(PARAM_FILE) or "."
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".gait_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=1)
            os.replace(tmp, PARAM_FILE)
        except Exception:
            os.unlink(tmp)
            raise
    except OSError:
        pass    # 저장 실패로 보행을 멈추지는 않는다
