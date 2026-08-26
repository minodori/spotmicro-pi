"""상속받은 저장소에서 IK 가 계산한 발 위치와 URDF 가 실제로 놓는 발 위치의 차이.

보고서의 "중앙값 16mm, 최대 29mm" 가 어디서 나왔는지 열어볼 수 있게 남긴다.

시뮬레이터 안에 로봇이 둘이다. PyBullet 이 그리고 물리를 푸는 몸은
urdf/spotmicroai_gen.urdf.xml 이고, 관절 각도를 계산하는 코드는
Simulation/kinematics.py 다. 후자는 URDF 를 읽지 않고 자기 상수를 쓴다.
그래서 계산된 각도를 그대로 넣으면 발이 코드가 의도한 자리에 가지 않는다.

    python tools/ik_urdf_mismatch.py
"""
import sys
import pathlib
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Simulation"))
from kinematics import Kinematic  # noqa: E402

# Simulation/kinematics.py:30-36 — 각도를 계산하는 몸
IK = dict(l1=50, l2=20, l3=100, l4=100)

# urdf/spotmicroai_gen.urdf.xml — 화면에 그려지고 물리가 풀리는 몸
#   front_left_leg   xyz="0 -0.052 0"      l1=52, l2=0 (수직 낙차가 없다)
#   front_left_foot  xyz="-0.01 0 -0.12"   l3=sqrt(10^2+120^2)=120.4
#   front_left_toe   xyz="0 0 -0.115"      + front_left_toe_link 의
#                                            collision sphere radius=0.02
#                                          -> 무릎축에서 접지점까지 135
#
# l4 는 반드시 접지점까지 재야 한다. 조인트 원점 115 를 우리 실측 135(무릎축->
# 발바닥)와 비교하면 없는 차이가 생긴다. 두 값은 같은 것을 재지 않는다.
URDF = dict(l1=52, l2=0, l3=120.4, l4=135)

W_FOOT = 75 + 5 + 40  # Simulation/spotmicroai.py:104 — 발끝 목표의 좌우 간격


def main():
    k = Kinematic()
    rows = []
    for body_h in (-80, -90, -100, -110, -120):
        for foot_x in range(-60, 130, 10):
            hip = k.bodyIK(0, 0, 0, 0, 0, 0)[0]
            target = np.linalg.inv(hip).dot(np.array([foot_x, body_h, W_FOOT / 2, 1.0]))

            k.__dict__.update(IK)
            angles = k.legIK(target)
            if not np.all(np.isfinite(angles)):
                continue
            intended = k.calcLegPoints(angles)[4][:3]

            k.__dict__.update(URDF)  # 같은 각도, 다른 몸
            actual = k.calcLegPoints(angles)[4][:3]

            rows.append((float(np.linalg.norm(actual - intended)), float((actual - intended)[1])))

    dist = sorted(r[0] for r in rows)
    lift = [r[1] for r in rows]
    print(f"자세 {len(rows)}개 (몸통높이 80~120mm x 발 앞뒤 -60~120mm)")
    print(f"  발 위치 오차   최소 {dist[0]:.1f}  중앙 {dist[len(dist) // 2]:.1f}  최대 {dist[-1]:.1f} mm")
    print(f"  발 높이 오차   {min(lift):+.1f} ~ {max(lift):+.1f} mm")


if __name__ == "__main__":
    main()
