"""시연 영상용 시뮬레이션 컷. 1920x1080 / 30fps.

화면에 글자를 넣지 않는다 — 자막은 편집에서 붙는다.

  MUJOCO_GL=egl python -m rl.render_cuts --out docs/media --cuts 1 2 3
"""
import argparse
import os
import sys

import numpy as np
import mujoco

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Kinematics.kinematics import Kinematic                      # noqa: E402
from rl.gen_mjcf import build                                     # noqa: E402
from rl.model_api import (MJCF_SCENE, JOINT_ORDER, jointSigns,    # noqa: E402
                          standingQpos, standingTheta, LEGS, JOINTS)

W, H, FPS = 1920, 1080, 30


class OldKin:
    """원본 공개값. 이 프로젝트가 상속받았을 때의 상수."""
    l1, l2, l3, l4, L, W = 50, 20, 100, 100, 140, 75


def wrapScene(robotXml):
    """gen_mjcf.build() 가 준 로봇 XML 에 바닥·조명·렌더 버퍼를 얹는다.

    scene_flat.xml 은 파일 include 를 쓰므로 문자열로 만든 모델에는 못 쓴다.
    오프스크린 버퍼(offwidth/offheight)가 없으면 640x480 에서 잘린다.
    """
    extra = """
  <visual>
    <headlight diffuse="0.6 0.6 0.6" ambient="0.3 0.3 0.3"/>
    <global azimuth="130" elevation="-20" offwidth="1920" offheight="1080"/>
  </visual>
  <asset>
    <texture name="grid" type="2d" builtin="checker" rgb1="0.2 0.22 0.25"
             rgb2="0.28 0.30 0.33" width="300" height="300"/>
    <material name="grid" texture="grid" texrepeat="6 6" reflectance="0.05"/>
  </asset>
  <worldbody>
    <light pos="0 0 2" dir="0 0 -1" directional="true"/>
    <geom name="floor" type="plane" size="0 0 0.05" material="grid"/>
  </worldbody>
"""
    return robotXml.replace('</mujoco>', extra + '</mujoco>')


def camera(dist, azim, elev, lookat=(0, 0, 0.12)):
    c = mujoco.MjvCamera()
    c.type = mujoco.mjtCamera.mjCAMERA_FREE
    c.distance, c.azimuth, c.elevation = dist, azim, elev
    c.lookat[:] = lookat
    return c


def marker(scene, pos, rgba, size=0.012, kind=mujoco.mjtGeom.mjGEOM_SPHERE, mat=None):
    """장면에 구·선을 하나 얹는다. update_scene 뒤에 호출한다."""
    if scene.ngeom >= scene.maxgeom:
        return
    g = scene.geoms[scene.ngeom]
    mujoco.mjv_initGeom(g, kind, np.asarray(size, dtype=float).repeat(3)[:3],
                        np.asarray(pos, dtype=float),
                        (mat if mat is not None else np.eye(3)).flatten(),
                        np.asarray(rgba, dtype=np.float32))
    scene.ngeom += 1


def connector(scene, a, b, rgba, width=0.004):
    """두 점을 잇는 캡슐. 지지선을 그린다."""
    if scene.ngeom >= scene.maxgeom:
        return
    g = scene.geoms[scene.ngeom]
    mujoco.mjv_initGeom(g, mujoco.mjtGeom.mjGEOM_CAPSULE, np.zeros(3),
                        np.zeros(3), np.eye(3).flatten(), np.asarray(rgba, np.float32))
    mujoco.mjv_connector(g, mujoco.mjtGeom.mjGEOM_CAPSULE, width,
                         np.asarray(a, float), np.asarray(b, float))
    scene.ngeom += 1


def standModel(model, data, height=None):
    """기립 자세로 세워 정지시킨다."""
    q = standingQpos() if height is None else standingQpos(height)
    adr = [model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n)]
           for n in JOINT_ORDER]
    aid = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, n) for n in JOINT_ORDER]
    mujoco.mj_resetData(model, data)
    data.qpos[2] = 0.30
    for k, a in enumerate(adr):
        data.qpos[a] = q[k]
        data.ctrl[aid[k]] = q[k]
    for _ in range(int(3.0 / model.opt.timestep)):
        mujoco.mj_step(model, data)
    return adr, aid


def write(path, frames):
    import imageio.v2 as imageio
    imageio.mimwrite(path, frames, fps=FPS, quality=9, macro_block_size=1)
    return path


# --- 컷 1. 기존값 모델 vs 실측 모델 -------------------------------------
def cut1(seconds=8.0):
    """상속받은 상수와 실측 상수로 만든 로봇을 같은 카메라로 나란히 세운다.

    다리 200mm 대 245mm, 몸통 140mm 대 185mm. 같은 코드가 두 로봇을 그린다는
    것이 요지이므로, 두 화면 모두 gen_mjcf.build() 가 만든 것을 쓴다.
    """
    half = W // 2
    out = []
    scenes = []
    for kin in (OldKin(), Kinematic()):
        m = mujoco.MjModel.from_xml_string(wrapScene(build(kin)))
        d = mujoco.MjData(m)
        # 옛 모델은 다리가 짧아 기립 명령이 달라진다. 각 모델의 무릎 내각을
        # 같게 두어 "같은 자세, 다른 크기" 로 보이게 한다.
        h = 95.0 if kin is not OldKin else 95.0
        try:
            standModel(m, d, h)
        except Exception:
            mujoco.mj_resetData(m, d); d.qpos[2] = 0.25; mujoco.mj_forward(m, d)
        scenes.append((m, d, mujoco.Renderer(m, H, half)))
    for i in range(int(seconds * FPS)):
        az = 120 + 50 * i / (seconds * FPS)         # 천천히 돌아 3D 로 읽히게
        cam = camera(0.62, az, -12)
        row = []
        for m, d, r in scenes:
            r.update_scene(d, camera=cam)
            row.append(r.render())
        out.append(np.hstack(row))
    for _, _, r in scenes:
        r.close()
    return out


# --- 컷 2. 순기구학 대조 -------------------------------------------------
def cut2(seconds=6.0):
    """순기구학 대조 게이트가 무엇을 잡아내는지 보인다.

    "두 점이 겹친다" 를 그대로 그리면 화면에서는 아무 일도 일어나지 않는다.
    한 구가 다른 구를 가릴 뿐이라, 겹쳐서 안 보이는 것인지 애초에 하나만
    그린 것인지 구분되지 않는다.

    그래서 대조군을 나란히 둔다. 두 화면 모두 빨간 마커는 역기구학이 계산한
    발끝이고, 회색 발은 시뮬레이터의 발끝이다.
        왼쪽  — 시뮬 모델을 옛 상수로 만든 경우. 둘이 벌어진다
        오른쪽 — 실측 상수 하나에서 둘 다 나온 경우. 붙어 있다
    이것이 validate_mjcf.py 게이트 3 이 매번 확인하는 것이다.
    """
    kin = Kinematic()
    half = W // 2
    panes = []
    for k in (OldKin(), kin):
        m = mujoco.MjModel.from_xml_string(wrapScene(build(k)))
        panes.append((m, mujoco.MjData(m), mujoco.Renderer(m, H, half)))
    sg = jointSigns()
    base = standingTheta()                      # 역기구학은 양쪽 다 실측 상수로
    out = []
    n = int(seconds * FPS)
    for i in range(n):
        ph = 2 * np.pi * i / n
        th = base.copy()
        for j, name in enumerate(JOINT_ORDER):
            if name.endswith('_leg'):  th[j] = base[j] + 0.32 * np.sin(ph)
            if name.endswith('_foot'): th[j] = base[j] - 0.32 * np.sin(ph)
        p = kin.calcLegPoints((th[0], th[1], th[2]))[4]
        row = []
        for m, d, r in panes:
            adr = [m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, nm)]
                   for nm in JOINT_ORDER]
            mujoco.mj_resetData(m, d)
            d.qpos[2] = 0.32
            for kk, a in enumerate(adr):
                d.qpos[a] = sg[kk] * th[kk]
            mujoco.mj_forward(m, d)
            tid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, 'trunk')
            sid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_SITE, 'FL_foot')
            ik = d.xpos[tid] + np.array([kin.L / 2.0 + p[2],
                                         kin.W / 2.0 - p[0], p[1]]) * 0.001
            r.update_scene(d, camera=camera(0.24, 152, -6, d.site_xpos[sid]))
            # 22mm 로 둔다. 화면의 회색 공은 발 지오메트리(12mm)가 아니라
            # 터치 센서용 site(18mm)이고 그것도 렌더링된다. 그보다 작으면
            # 겹쳤을 때 site 안에 숨어 "마커가 없다" 로 읽힌다.
            marker(r.scene, ik, (0.95, 0.28, 0.20, 1.0), 0.022)
            row.append(r.render())
        out.append(np.hstack(row))
    for _, _, r in panes:
        r.close()
    return out


# --- 컷 3. 360도 회전 ----------------------------------------------------
def cut3(seconds=8.0):
    m = mujoco.MjModel.from_xml_path(MJCF_SCENE)
    d = mujoco.MjData(m)
    r = mujoco.Renderer(m, H, W)
    standModel(m, d)
    out = []
    n = int(seconds * FPS)
    for i in range(n):
        r.update_scene(d, camera=camera(0.62, 360 * i / n, -14))
        out.append(r.render())
    r.close()
    return out


CUTS = {1: cut1, 2: cut2, 3: cut3}

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='docs/media')
    ap.add_argument('--cuts', type=int, nargs='+', default=sorted(CUTS))
    ap.add_argument('--scale', type=float, default=1.0, help='미리보기용 축소')
    a = ap.parse_args()
    if a.scale != 1.0:
        W = int(W * a.scale) // 2 * 2
        H = int(H * a.scale) // 2 * 2
    os.makedirs(a.out, exist_ok=True)
    for c in a.cuts:
        frames = CUTS[c]()
        p = write(os.path.join(a.out, f'cut{c}.mp4'), frames)
        print(f"  cut{c}  {len(frames)}프레임  {frames[0].shape[1]}x{frames[0].shape[0]}  {p}")
