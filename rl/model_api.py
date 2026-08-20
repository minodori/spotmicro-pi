"""학습 코드가 모델에 대해 알아야 할 것 전부. 여기 없는 값은 복제하지 말고 요청할 것.

에이전트 B 의 학습 환경이 기구 상수·서보 오프셋·관절 순서·가동 범위를 자기 파일에
적어두면 반드시 어긋난다. 이 모듈이 그것들을 한 곳에서 계산해 준다.

  from rl.model_api import (MJCF_SCENE, JOINT_ORDER, standingQpos,
                            jointRanges, jointSigns, thetaToServo)

이 모듈은 mujoco 와 numpy 외에 아무것도 요구하지 않는다 (matplotlib 도, 하드웨어도).
"""
import os

import numpy as np
import mujoco

from Kinematics.kinematics import Kinematic
from Kinematics.kinematicMotion import TrottingGait
from Common.servo_map import SERVO_OFFSETS, SERVO_SIGN

HERE = os.path.dirname(os.path.abspath(__file__))
MJCF_SCENE = os.path.join(HERE, 'mjcf', 'scene_flat.xml')   # 학습용 (바닥 포함)
MJCF_ROBOT = os.path.join(HERE, 'mjcf', 'spotmicro.xml')    # 로봇만

LEGS = ('FL', 'FR', 'RL', 'RR')
JOINTS = ('shoulder', 'leg', 'foot')

# 관측·행동 벡터의 관절 순서. 서보 인덱스와 같은 순서로 두어 변환에 재정렬이 없다.
JOINT_ORDER = tuple(f'{leg}_{j}' for leg in LEGS for j in JOINTS)

# MJCF 관절각 = 이 부호 x kinematics theta.  rl/fk_mapping.py 가 검증한다.
MJCF_SIGN = {'FL': (+1, -1, -1), 'FR': (-1, -1, -1),
             'RL': (+1, -1, -1), 'RR': (-1, -1, -1)}

# 기립 자세의 몸통 높이. Common/gait_params.py 의 기본값과 같다 (조절 범위 60~105).
STAND_HEIGHT = 95.0


def jointSigns():
    """JOINT_ORDER 순서의 부호 배열 (12,)."""
    return np.array([MJCF_SIGN[n.split('_')[0]][JOINTS.index(n.split('_')[1])]
                     for n in JOINT_ORDER], dtype=float)


def standingTheta(height=STAND_HEIGHT):
    """기립 자세의 kinematics theta (12,) 라디안. legIK 로 계산하므로 실물과 같다."""
    k, g = Kinematic(), TrottingGait()
    Lp = np.array([[g.Fo, -100, g.Spf, 1], [g.Fo, -100, -g.Spf, 1],
                   [-g.Ro, -100, g.Spr, 1], [-g.Ro, -100, -g.Spr, 1]], dtype=float)
    th = k.calcIK(Lp, (0, 0, 0), (50, 40 + height, 0))
    return np.array([th[LEGS.index(n.split('_')[0])][JOINTS.index(n.split('_')[1])]
                     for n in JOINT_ORDER], dtype=float)


def standingQpos(height=STAND_HEIGHT):
    """기립 자세의 MJCF 관절각 (12,) 라디안.

    정책의 기본 자세(default_joint_pos)로 쓴다. 행동은 여기서의 변위다:
        target = standingQpos() + ACTION_SCALE * action
    """
    return jointSigns() * standingTheta(height)


def standingTrunkHeight(height=STAND_HEIGHT):
    """기립 시 몸통 원점의 지면 높이 (m). 보상의 base_height 목표값에 쓴다."""
    return (140.0 + height) * 0.001 + 0.012      # 어깨축~발바닥 + 발 구체 반지름


def jointRanges(model=None):
    """MJCF 관절 가동 범위 (12, 2) 라디안. 실측 서보 영점에서 유도된 값이다."""
    model = model or mujoco.MjModel.from_xml_path(MJCF_ROBOT)
    return np.array([model.jnt_range[
        mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n)] for n in JOINT_ORDER])


def thetaToServo(theta):
    """kinematics theta (12,) 라디안 -> 서보 각도 (12,) 도.

    실물 배포 경로다. servo_controller.angleToServo() 와 같은 계산이지만
    하드웨어 import 없이 쓸 수 있다. 0~180 을 벗어나면 실물에서 잘린다.
    """
    deg = np.degrees(np.asarray(theta, dtype=float))
    # 두 순서가 다르다. JOINT_ORDER 는 다리마다 (shoulder, leg, foot) = theta 인덱스
    # 0,1,2 순이지만, 서보 인덱스는 (Lower, Upper, Shoulder) = theta 인덱스 2,1,0 순이다.
    # SERVO_SIGN 이 서보 인덱스마다 (다리, theta 인덱스, 부호) 를 갖고 있으므로 그걸 쓴다.
    return np.array([SERVO_OFFSETS[i] + s * deg[leg * 3 + th]
                     for i, (leg, th, s) in enumerate(SERVO_SIGN)])


def qposToServo(qpos):
    """MJCF 관절각 (12,) 라디안 -> 서보 각도 (12,) 도. 정책 출력을 실물로 보낼 때."""
    return thetaToServo(np.asarray(qpos, dtype=float) / jointSigns())


if __name__ == '__main__':
    m = mujoco.MjModel.from_xml_path(MJCF_ROBOT)
    q, r = standingQpos(), jointRanges(m)
    print(f"{'관절':<14}{'기립(도)':>10}{'하한':>9}{'상한':>9}{'여유':>8}{'서보':>8}")
    sv = qposToServo(q)
    for i, n in enumerate(JOINT_ORDER):
        lo, hi = np.degrees(r[i])
        print(f"{n:<14}{np.degrees(q[i]):>10.1f}{lo:>9.1f}{hi:>9.1f}"
              f"{min(np.degrees(q[i])-lo, hi-np.degrees(q[i])):>8.1f}{sv[i]:>8.0f}")
    margin = min(min(np.degrees(q[i]) - np.degrees(r[i])[0],
                     np.degrees(r[i])[1] - np.degrees(q[i])) for i in range(12))
    print(f"\n기립 몸통 높이 {standingTrunkHeight()*1000:.0f}mm   최소 관절 여유 {margin:.1f}도")
