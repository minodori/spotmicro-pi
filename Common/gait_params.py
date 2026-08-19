"""보행 튜닝 파라미터의 저장/복원.

트림을 어렵게 찾아놓고 재시작하면 0 으로 돌아가는 문제를 없앤다.
코드가 아니라 실행 상태이므로 홈 디렉터리에 둔다 (rsync/git 과 무관하게 유지된다).

저장 대상은 "실물을 보며 맞추는" 값들이다. 궤적 타이밍(t1/t3)처럼 계산으로
검증해야 하는 값은 코드에 남긴다.
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
#            링크 길이를 실측값으로 바로잡으면서(l3+l4 = 200 -> 263mm) 이 값의 의미가
#            바뀌었다. Upper축~발 거리 H = 120 + height 이고, 무릎 내각은
#              내각 100도 -> height  82
#              내각 110도 -> height  96
#              내각 120도 -> height 108
#              내각 130도 -> height 118
#            이전 기본값 60 은 새 모델에서 무릎을 86도까지 접는 극단적 자세다.
#            110 을 기본으로 두고 60~130 을 허용한다. 조합 위험은 제어 루프가
#            실시간 감시한다 (servoRotate 반환값).
#   Sh     : 발 들어올림. 무릎 요구 슬루율이 Sh*pi/t3 이다.
#   IDtrim : 값 자체보다 다리 사이 "차이" 가 중요하다. 차이가 Sh 에 육박하면 높은 발이
#            접지하지 못해 반대 대각선으로 넘어진다.
DEFAULTS = {
    'IDtrim': ([0.0, 0.0, 0.0, 0.0], None, None),   # 다리별 y 트림 (mm)
    'Sh': (20.0, 5.0, 30.0),                        # 발 들어올림 (mm)
    'height': (110.0, 60.0, 130.0),                 # bodyPosition y = 40 + height
}


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
    trim = p.get('IDtrim')
    if not isinstance(trim, list) or len(trim) != 4:
        p['IDtrim'] = [0.0] * 4
    else:
        try:
            p['IDtrim'] = [float(x) for x in trim]
        except (TypeError, ValueError):
            p['IDtrim'] = [0.0] * 4
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
