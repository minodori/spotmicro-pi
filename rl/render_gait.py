"""IK 보행을 MuJoCo 에서 재생해 영상으로 뽑는다. 시연 영상용.

정책 학습 결과가 아니라 **규칙 기반 보행을 시뮬레이터에서 확인**하는 컷이다.
실물과 같은 궤적 코드(Kinematics/kinematicMotion.py)를 그대로 돌리므로,
같은 걸음이 시뮬과 실물에서 어떻게 보이는지 나란히 붙일 수 있다.

  MUJOCO_GL=egl python -m rl.render_gait --out gait.mp4 --seconds 6
"""
import argparse
import os
import sys

import numpy as np
import mujoco

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Kinematics.kinematics import Kinematic                   # noqa: E402
from Kinematics.kinematicMotion import TrottingGait           # noqa: E402
from Common.gait_params import defaultParams, gaitPhases      # noqa: E402
from rl.model_api import MJCF_SCENE, JOINT_ORDER, jointSigns  # noqa: E402

LEGS = ('FL', 'FR', 'RL', 'RR')


def render(out, seconds, fps, imgW, imgH, camera, **params):
    model = mujoco.MjModel.from_xml_path(MJCF_SCENE)
    data = mujoco.MjData(model)
    renderer = mujoco.Renderer(model, height=imgH, width=imgW)

    kb = dict(defaultParams(), IDstepWidth=0.0, IDstepAlpha=0.0)
    kb.update(params)
    kin, gait = Kinematic(), TrottingGait()
    gait.Sh = kb['Sh']
    signs = jointSigns()

    qadr = [model.jnt_qposadr[mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_JOINT, n)] for n in JOINT_ORDER]
    aid = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, n) for n in JOINT_ORDER]

    mujoco.mj_resetData(model, data)
    data.qpos[2] = 0.27

    frames, nextFrame = [], 0.0
    step = model.opt.timestep
    for i in range(int(seconds / step)):
        t = i * step
        gait.t1, gait.t3 = gaitPhases(kb)
        Lp = gait.positions(t, kb)
        th = np.asarray(kin.calcIK(Lp, (0, 0, 0), (50, 40 + kb['height'], 0)), dtype=float)
        # calcIK 는 (4,3) theta 를 준다. JOINT_ORDER 는 다리마다 (shoulder, leg, foot).
        target = signs * np.array([th[LEGS.index(n.split('_')[0])][
            ('shoulder', 'leg', 'foot').index(n.split('_')[1])] for n in JOINT_ORDER])
        if np.isnan(target).any():
            continue
        for k, a in enumerate(aid):
            data.ctrl[a] = target[k]
        mujoco.mj_step(model, data)
        if t >= nextFrame:
            renderer.update_scene(data, camera=camera)
            frames.append(renderer.render())
            nextFrame += 1.0 / fps

    try:
        import imageio.v2 as imageio
        imageio.mimwrite(out, frames, fps=fps, quality=8)
    except ImportError:
        np.save(out.replace('.mp4', '.npy'), np.asarray(frames))
        out = out.replace('.mp4', '.npy')
    return out, len(frames), float(data.qpos[0])


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--out', default='gait.mp4')
    p.add_argument('--seconds', type=float, default=6.0)
    p.add_argument('--fps', type=int, default=30)
    p.add_argument('--imgwidth', type=int, default=1920)
    p.add_argument('--imgheight', type=int, default=1080)
    p.add_argument('--camera', default='track')
    p.add_argument('--Tt', type=float, default=1400.0)
    p.add_argument('--duty', type=float, default=0.143)
    p.add_argument('--Sh', type=float, default=20.0)
    p.add_argument('--height-mm', dest='hmm', type=float, default=110.0)
    p.add_argument('--Sl', type=float, default=-70.0)
    p.add_argument('--pitch', type=float, default=0.0,
                   help='피치 트림 mm. 양수가 앞으로 숙임 (웹 UI 와 같은 부호)')
    a = p.parse_args()
    out, n, x = render(a.out, a.seconds, a.fps, a.imgwidth, a.imgheight, a.camera,
                       Tt=a.Tt, duty=a.duty, Sh=a.Sh, height=a.hmm, IDstepLength=a.Sl,
                       IDtrim=[a.pitch, a.pitch, -a.pitch, -a.pitch])
    print(f"{out}  프레임 {n}  전진 {x*1000:+.0f}mm  ({x/a.seconds*1000:+.0f}mm/s)")
