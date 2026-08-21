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


def render(out, seconds, fps, imgW, imgH, camera, measure=False, **params):
    model = mujoco.MjModel.from_xml_path(MJCF_SCENE)
    data = mujoco.MjData(model)
    renderer = None if measure else mujoco.Renderer(model, height=imgH, width=imgW)
    track = []

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
        if measure:
            R = data.xmat[1].reshape(3, 3)
            track.append((data.qpos[2], (R.T @ np.array([0, 0, -1.0]))[2]))
            continue
        if t >= nextFrame:
            renderer.update_scene(data, camera=camera)
            frames.append(renderer.render())
            nextFrame += 1.0 / fps

    if measure:
        h = np.array([p[0] for p in track])
        g = np.array([p[1] for p in track])
        return dict(vx=float(data.qpos[0]) / seconds, drift=float(data.qpos[1]),
                    h_mean=float(h.mean()), h_min=float(h.min()),
                    tilt_worst=float(g.max()),
                    fell=bool((h < 0.15).any() or (g > -0.5).any()))

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
    # 보행 파라미터의 기본값은 Common/gait_params.py 가 정본이다. 여기 숫자를
    # 복붙하면 갈라진다 — 실제로 height 가 110 으로 남아 있었는데, l3 를 135->110
    # 으로 줄인 뒤 그 자세는 다리 도달의 한계에 가까워 시연 영상이 잘못된 포즈로
    # 뽑힐 뻔했다. 정본은 95 다.
    _d = defaultParams()
    p.add_argument('--Tt', type=float, default=_d['Tt'])
    p.add_argument('--duty', type=float, default=_d['duty'])
    p.add_argument('--Sh', type=float, default=_d['Sh'])
    p.add_argument('--height-mm', dest='hmm', type=float, default=_d['height'])
    # 보폭은 운전자가 주는 명령이라 defaultParams 에 없다. -70 / Tt 1400 이
    # 실물 실측 50mm/s 에 해당한다.
    p.add_argument('--Sl', type=float, default=-70.0)
    p.add_argument('--pitch', type=float, default=0.0,
                   help='피치 트림 mm. 양수가 앞으로 숙임 (웹 UI 와 같은 부호)')
    p.add_argument('--measure', action='store_true',
                   help='영상 대신 수치만. 시뮬 동역학이 실물을 재현하는지 본다')
    a = p.parse_args()
    kw = dict(Tt=a.Tt, duty=a.duty, Sh=a.Sh, height=a.hmm, IDstepLength=a.Sl,
              IDtrim=[a.pitch, a.pitch, -a.pitch, -a.pitch])

    if a.measure:
        r = render(a.out, max(a.seconds, 12.0), a.fps, a.imgwidth, a.imgheight,
                   a.camera, measure=True, **kw)
        print(f"\n  규칙 기반 보행을 시뮬레이터에서 재생 "
              f"(보폭 {a.Sl:+.0f}mm, 주기 {a.Tt:.0f}ms, 높이 {a.hmm:.0f}mm)")
        print(f"    전진 속도    {r['vx']*1000:6.0f} mm/s   "
              f"명령상 {abs(a.Sl)/a.Tt*1000:.0f} mm/s")
        print(f"    동체 높이    {r['h_mean']*1000:6.0f} mm   (최저 {r['h_min']*1000:.0f})")
        print(f"    횡방향 편차  {r['drift']*1000:+6.0f} mm")
        print(f"    최대 기울기  {r['tilt_worst']:6.2f}     (-1.0 이 완전 수평)")
        print(f"    {'❌ 넘어짐' if r['fell'] else '✅ 넘어지지 않음'}\n")
        raise SystemExit(1 if r['fell'] else 0)

    out, n, x = render(a.out, a.seconds, a.fps, a.imgwidth, a.imgheight, a.camera, **kw)
    print(f"{out}  프레임 {n}  전진 {x*1000:+.0f}mm  ({x/a.seconds*1000:+.0f}mm/s)")
