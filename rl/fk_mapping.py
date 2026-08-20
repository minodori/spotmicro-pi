"""MJCF 관절각 <-> Kinematics 의 (theta1, theta2, theta3) 대응을 실험으로 찾는다.

부호 규약을 머리로 유도하면 틀린다. 다리마다 좌우 미러가 걸려 있고 (kinematics 의
Ix 행렬), MuJoCo 힌지 축의 오른손 법칙과 kinematics 의 평면 회전이 서로 다르게
정의돼 있기 때문이다. 그래서 무작위 각도를 넣어 두 모델의 발끝이 일치하는
부호 조합을 찾아낸다.

찾아낸 대응은 두 가지에 쓰인다:
  1. MJCF 가 실물과 같은 기하를 가졌다는 증명 (검증 게이트 3)
  2. 학습된 정책의 관절 명령을 servo_controller.angleToServo() 에 넘기는 변환
"""
import itertools
import os
import sys

import numpy as np
import mujoco

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Kinematics.kinematics import Kinematic          # noqa: E402

LEGS = ('FL', 'FR', 'RL', 'RR')
JOINTS = ('shoulder', 'leg', 'foot')


def ikFootPos(kin, leg, thetas):
    """Kinematics 모델의 발끝 위치를 MuJoCo 몸통 프레임(m)으로 준다."""
    p = kin.calcLegPoints(thetas)[4]                  # 다리 로컬 (x 좌우, y 상하, z 전후)
    fx = +1 if leg in ('FL', 'FR') else -1
    fy = +1 if leg in ('FL', 'RL') else -1
    # 좌우 다리는 kinematics 가 Ix 미러를 쓰므로 로컬 x 부호가 뒤집힌다.
    return np.array([fx * kin.L / 2.0 + p[2],
                     fy * (kin.W / 2.0 - p[0]),
                     p[1]]) * 0.001


def solve(model, data, kin, samples=40, seed=0):
    """다리·관절마다 부호를 찾는다. 반환: {leg: (s1, s2, s3)}, 최대 오차(mm)."""
    rng = np.random.default_rng(seed)
    # 실제 쓰는 범위 안에서만 뽑는다. 범위 밖은 어차피 명령하지 않는다.
    thetas = np.stack([rng.uniform(-0.4, 0.4, samples),
                       rng.uniform(-0.8, 0.4, samples),
                       rng.uniform(0.3, 2.0, samples)], axis=1)
    qadr = {f'{l}_{j}': model.jnt_qposadr[
        mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f'{l}_{j}')]
        for l in LEGS for j in JOINTS}
    trunkId = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'trunk')

    found, worst = {}, 0.0
    for leg in LEGS:
        best, bestErr = None, 1e9
        for signs in itertools.product((+1, -1), repeat=3):
            err = 0.0
            for th in thetas:
                mujoco.mj_resetData(model, data)
                data.qpos[2] = 0.30
                for j, (name, s) in enumerate(zip(JOINTS, signs)):
                    data.qpos[qadr[f'{leg}_{name}']] = s * th[j]
                mujoco.mj_forward(model, data)
                sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, f'{leg}_foot')
                mjc = data.site_xpos[sid] - data.xpos[trunkId]
                err = max(err, np.linalg.norm(mjc - ikFootPos(kin, leg, th)))
            if err < bestErr:
                best, bestErr = signs, err
        found[leg] = best
        worst = max(worst, bestErr)
    return found, worst * 1000.0


if __name__ == '__main__':
    mjcf = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mjcf', 'spotmicro.xml')
    model = mujoco.MjModel.from_xml_path(mjcf)
    data = mujoco.MjData(model)
    signs, err = solve(model, data, Kinematic())
    print("MJCF 관절 부호 (Kinematics theta 대비)\n")
    print(f"  {'다리':<6}{'shoulder':>10}{'leg':>8}{'foot':>8}")
    for leg in LEGS:
        s = signs[leg]
        print(f"  {leg:<6}{s[0]:>+10}{s[1]:>+8}{s[2]:>+8}")
    print(f"\n최대 발끝 오차 {err:.4f}mm")
