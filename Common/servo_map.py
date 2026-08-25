"""서보 오프셋과 각도 매핑. 하드웨어 의존이 없다.

servo_controller.py 는 adafruit/board 를 import 하므로 로봇 밖에서는 못 읽는다.
그런데 시뮬레이터도 같은 오프셋과 부호를 알아야 한다 — 관절 가동 범위가 여기서
유도되고, 학습된 정책의 관절 명령도 이 변환을 거쳐 서보로 나가기 때문이다.

두 곳에 같은 표를 두면 반드시 어긋난다 (work11 §6.25 가 치수로 겪은 일이다).
그래서 순수 데이터만 여기 두고 servo_controller 가 import 한다.
"""

# 서보 인덱스 순서: FL(Lower,Upper,Shoulder), FR, RL, RR
# 값은 그 관절이 기준 자세(theta=0)일 때의 서보 각도다. 혼이 스플라인에 물린
# 위치가 서보마다 달라 좌우가 대칭일 필요는 없다 (work11 §6.6).
#
# 2026-08-19 재캘리브레이션 (03736f8). 이전 값에서 무릎 세 개가 가동 한계
# 밖이었던 것이 안으로 들어왔다 (work11 §0).
# SERVO_OFFSETS = [165, 83, 79, 25, 83, 95, 164, 91, 88, 23, 81, 77]
# 2026-08-25 RR-Shoulder 재캘리브레이션 (실기 측정, 77 -> 79):
# SERVO_OFFSETS = [165, 83, 83, 25, 83, 95, 164, 91, 88, 23, 81, 77]
# 2026-08-25 전체 재캘리브레이션 (실기). FL-Lower +3, FR-Shoulder +4,
# RL 다리 전체 (+12/+1/+5). 이전 값:
# SERVO_OFFSETS = [165, 83, 83, 25, 83, 95, 164, 91, 88, 23, 81, 79]
# 2026-08-25 FL-Shoulder 재조정 (83 -> 81). 이전 값:
# SERVO_OFFSETS = [168, 83, 83, 25, 83, 99, 176, 92, 93, 23, 81, 79]
# 2026-08-25 FL-Shoulder 재조정 (81 -> 77). 이전 값:
# SERVO_OFFSETS = [168, 83, 81, 25, 83, 99, 176, 92, 93, 23, 81, 79]
# 2026-08-25 Upper 4개 재캘리브레이션 (FL -2, FR +2, RL +1, RR +1). 이전 값:
# SERVO_OFFSETS = [168, 83, 77, 25, 83, 99, 176, 92, 93, 23, 81, 79]
# 2026-08-25 앞 어깨 스탠스 폭 조정 (FL +6, FR -4). 이전 값:
# SERVO_OFFSETS = [168, 81, 77, 25, 85, 99, 176, 93, 93, 23, 82, 79]
# 2026-08-25 FR-Upper 재조정 (85 -> 88). 이전 값:
# SERVO_OFFSETS = [168, 81, 83, 25, 85, 95, 176, 93, 93, 23, 82, 79]
# 2026-08-25 FR-Upper 재조정 (88 -> 93). 이전 값:
# SERVO_OFFSETS = [168, 81, 83, 25, 88, 95, 176, 93, 93, 23, 82, 79]
# 2026-08-25 FL-Upper 81->78, FR-Upper 93->84 (오른쪽은 잘못 만진 것을 되돌림). 이전 값:
# SERVO_OFFSETS = [168, 81, 83, 25, 93, 95, 176, 93, 93, 23, 82, 79]
# 2026-08-25 RL-Upper 93->90, RR-Upper 82->85. 이 값으로 촬영. 이전 값:
# SERVO_OFFSETS = [168, 78, 83, 25, 84, 95, 176, 93, 93, 23, 82, 79]
# 2026-08-25 RL-Lower 혼 교체·재체결 (176 -> 160). SAFE_BAND(8,172) 안으로
# 들어와 home 이 다시 이 관절을 움직인다. 이전 값:
# SERVO_OFFSETS = [168, 78, 83, 25, 84, 95, 176, 90, 93, 23, 85, 79]
# 2026-08-25 혼 교체 뒤 재캘리브레이션. RL-Lower 160->169, RL-Upper +5,
# FL-Upper +8, RR-Lower -3, RR-Upper -6. 이전 값:
# SERVO_OFFSETS = [168, 78, 83, 25, 84, 95, 160, 90, 93, 23, 85, 79]
SERVO_OFFSETS = [168, 86, 83, 25, 84, 95, 169, 95, 93, 20, 79, 79]


# 인덱스 5 (FR-Shoulder) 만 Futaba 25kg, 나머지 11개는 DS3235 35kg·cm.
FUTABA_INDICES = {5}

JOINT_NAMES = ["FL-Lower", "FL-Upper", "FL-Shoulder", "FR-Lower", "FR-Upper", "FR-Shoulder",
               "RL-Lower", "RL-Upper", "RL-Shoulder", "RR-Lower", "RR-Upper", "RR-Shoulder"]

# 서보 인덱스 -> (다리, theta 인덱스, 부호).  servo = offset + 부호 * theta(도)
# theta 인덱스는 legIK 의 반환 순서다: 0 = theta1(어깨), 1 = theta2(대퇴), 2 = theta3(무릎)
SERVO_SIGN = [
    (0, 2, -1), (0, 1, -1), (0, 0, +1),     # FL
    (1, 2, +1), (1, 1, +1), (1, 0, -1),     # FR
    (2, 2, -1), (2, 1, -1), (2, 0, -1),     # RL
    (3, 2, +1), (3, 1, +1), (3, 0, +1),     # RR
]

# servoRotate() 가 실제로 거르는 범위. 180 초과는 179 로, 0 이하는 1 로 잘리고
# 그 관절은 "얼어붙는다" (명령이 전달되지 않는다).
SERVO_MIN, SERVO_MAX = 0.0, 180.0


def thetaLimitsDeg():
    """각 서보가 허용하는 kinematics theta 범위 (도). 반환 순서는 서보 인덱스.

    servo = offset + s*theta 이고 servo 가 (0, 180] 여야 하므로
        s = +1 -> theta in (-offset, 180-offset]
        s = -1 -> theta in [offset-180, offset)
    """
    out = []
    for i, (_, _, s) in enumerate(SERVO_SIGN):
        off = SERVO_OFFSETS[i]
        if s > 0:
            out.append((SERVO_MIN - off, SERVO_MAX - off))
        else:
            out.append((off - SERVO_MAX, off - SERVO_MIN))
    return out
