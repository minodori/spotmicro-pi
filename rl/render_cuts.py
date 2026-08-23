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
                          standingQpos, standingTheta, standingTrunkHeight,
                          jointRanges, LEGS, JOINTS)

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
    """상속받은 상수와 실측 상수로 만든 로봇을 같은 카메라로 나란히 걷게 한다.

    가만히 세워두면 크기 차이만 보인다. 같은 보행 코드를 두 모델에 물리면
    다리 길이가 보폭과 몸통 높이를 바꾸므로 "다른 로봇이다" 가 움직임으로
    드러난다. 궤적 코드는 하나이고 상수만 다르다는 것이 요지다.
    """
    from Kinematics.kinematicMotion import TrottingGait
    from Common.gait_params import defaultParams, gaitPhases

    half = W // 2
    panes = []
    # 몸통 높이는 모델마다 다르게 준다. 하나로 맞출 수가 없다 —
    # 옛 모델은 다리가 200mm 라 H(=120+height)가 그것을 넘으면 IK 가 안 풀리고,
    # 실측 모델은 낮추면 무릎 모멘트 팔이 커져 3N·m 서보가 못 버티고 주저앉는다.
    # 각자 도달 한계의 90% 근처, 즉 자기 작동 자세에서 걷게 한다.
    for k, bodyH in ((OldKin(), 60.0), (Kinematic(), 95.0)):
        m = mujoco.MjModel.from_xml_string(wrapScene(build(k)))
        d = mujoco.MjData(m)
        adr = [m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)]
               for n in JOINT_ORDER]
        aid = [mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, n) for n in JOINT_ORDER]
        # 각 모델의 기구 상수로 역기구학을 푼다. 같은 발끝 궤적을 명령해도
        # 다리가 다르면 관절각이 다르게 나오고, 그것이 이 컷의 내용이다.
        kin = Kinematic()
        for a, b in (('l1', k.l1), ('l2', k.l2), ('l3', k.l3),
                     ('l4', k.l4), ('L', k.L), ('W', k.W)):
            setattr(kin, a, b)
        g = TrottingGait()
        # 발 위치를 각 모델의 기하로 다시 잡는다. TrottingGait 의 기본값은
        # 실측 로봇(L=185, W=78, l1=56)에 맞춘 것이라, 몸통이 140mm 인 옛
        # 모델에 그대로 쓰면 발이 관절에서 너무 멀어 다리가 닿지 않는다.
        #   앞뒤: 관절 바로 아래에서 25mm 뒤 (work11 §6.25 의 무게중심 정렬)
        #   좌우: 어깨각이 0 이 되는 W/2 + l1
        g.Fo = 50 + k.L / 2.0 - 25
        g.Ro = k.L / 2.0 - 25
        g.Spf = g.Spr = k.W / 2.0 + k.l1
        # height 70. 실측 모델의 상용값은 95 지만 옛 모델은 다리가 200mm 라
        # 그 자세에 도달하지 못한다(H=215 > 200, IK 가 풀리지 않는다). 같은
        # 명령을 두 로봇에 주는 것이 이 컷의 요지이므로 둘 다 되는 값을 쓴다.
        # 그래도 자세는 갈린다 - 옛 모델은 무릎 내각 144도로 거의 곧게 서고
        # 실측 모델은 101도로 굽힌다. 같은 명령, 다른 로봇.
        kb = dict(defaultParams(), Tt=1400.0, duty=0.143, Sh=20.0, height=bodyH,
                  IDstepLength=-55.0, IDstepWidth=0.0, IDstepAlpha=0.0,
                  IDtrim=[3.0, 3.0, -3.0, -3.0])
        g.Sh = kb['Sh']; g.t1, g.t3 = gaitPhases(kb)
        mujoco.mj_resetData(m, d)
        d.qpos[2] = 0.30
        panes.append((m, d, mujoco.Renderer(m, H, half), adr, aid, kin, g, kb))

    sg = jointSigns()
    out = []
    step = panes[0][0].opt.timestep
    n = int(seconds * FPS)
    tid = [mujoco.mj_name2id(p[0], mujoco.mjtObj.mjOBJ_BODY, 'trunk') for p in panes]
    for i in range(n):
        row = []
        for pi, (m, d, r, adr, aid, kin, g, kb) in enumerate(panes):
            for _ in range(int(1.0 / FPS / step)):
                t = d.time
                th = np.asarray(kin.calcIK(g.positions(t, kb), (0, 0, 0),
                                           (50, 40 + kb['height'], 0)), float)
                tgt = sg * np.array([th[LEGS.index(nm.split('_')[0])]
                                     [JOINTS.index(nm.split('_')[1])] for nm in JOINT_ORDER])
                if not np.isnan(tgt).any():
                    for kk, a in enumerate(aid):
                        d.ctrl[a] = tgt[kk]
                mujoco.mj_step(m, d)
            look = d.xpos[tid[pi]].copy(); look[2] -= 0.06
            r.update_scene(d, camera=camera(0.66, 128, -10, look))
            row.append(r.render())
        out.append(np.hstack(row))
    for p in panes:
        p[2].close()
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
        # 대각 쌍을 반주기 어긋나게 둔다. 네 다리를 같은 위상으로 움직이면
        # 동시에 굽혔다 펴는 동작이 되어 "이 로봇은 이렇게 걷는다" 로 읽힌다.
        # 이 컷의 화제는 걸음걸이가 아니라 마커인데 시선을 뺏긴다.
        for j, name in enumerate(JOINT_ORDER):
            leg = name.split('_')[0]
            p_ = ph + (np.pi if leg in ('FR', 'RL') else 0.0)
            if name.endswith('_leg'):  th[j] = base[j] + 0.32 * np.sin(p_)
            if name.endswith('_foot'): th[j] = base[j] - 0.32 * np.sin(p_)
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
            # 로봇 전체가 들어오는 거리로 잡는다. 발만 클로즈업하면 무엇의
            # 발인지, 빨간 공이 무엇에 대한 것인지 맥락이 사라진다.
            # 몸통이 아니라 몸통과 발 사이를 본다. 몸통을 보면 발이 프레임
            # 아래로 잘리는데, 이 컷에서 봐야 하는 것은 발이다.
            look = d.xpos[tid].copy(); look[2] -= 0.10
            r.update_scene(d, camera=camera(0.52, 148, -6, look))
            for li, leg in enumerate(LEGS):
                q = kin.calcLegPoints((th[li*3], th[li*3+1], th[li*3+2]))[4]
                fx = +1 if leg in ('FL', 'FR') else -1
                fy = +1 if leg in ('FL', 'RL') else -1
                ik = d.xpos[tid] + np.array([fx*kin.L/2.0 + q[2],
                                             fy*(kin.W/2.0 - q[0]), q[1]]) * 0.001
                # 28mm. 화면의 회색 공은 발 지오메트리(12mm)가 아니라 터치 센서
                # site(18mm)이고 그것도 렌더링된다. 그보다 작으면 겹쳤을 때
                # site 안에 숨어 "마커가 없다" 로 읽힌다.
                marker(r.scene, ik, (0.95, 0.28, 0.20, 1.0), 0.028)
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


# --- 컷 4. 5cm 낙하 후 정착 ---------------------------------------------
def cut4(seconds=5.0):
    """기립 자세를 명령한 채로 떨어뜨려 서보가 받아내는 것을 보인다.

    검증 게이트 5 가 매번 하는 것이다. 카메라를 고정해 몸통 높이가 실제로
    가라앉았다 잡히는 것이 보이게 한다.
    """
    m = mujoco.MjModel.from_xml_path(MJCF_SCENE)
    d = mujoco.MjData(m)
    r = mujoco.Renderer(m, H, W)
    q = standingQpos()
    adr = [m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)]
           for n in JOINT_ORDER]
    aid = [mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, n) for n in JOINT_ORDER]
    mujoco.mj_resetData(m, d)
    d.qpos[2] = standingTrunkHeight() + 0.05         # 5cm 위에서
    for k, a in enumerate(adr):
        d.qpos[a] = q[k]
        d.ctrl[aid[k]] = q[k]
    # 카메라를 고정한다. 몸통을 따라가면 가라앉는 것이 안 보인다.
    cam = camera(0.52, 152, -4, (0.0, 0.0, 0.16))
    out = []
    step = m.opt.timestep
    for i in range(int(seconds * FPS)):
        for _ in range(int(1.0 / FPS / step)):
            mujoco.mj_step(m, d)
        r.update_scene(d, camera=cam)
        out.append(r.render())
    r.close()
    return out


# --- 컷 5. 관절 12개 순차 구동 -------------------------------------------
def cut5(seconds=10.0):
    """관절을 하나씩 돌린다. 다리마다 shoulder -> leg -> foot 순서.

    모델이 12자유도이고 각 관절이 어디를 움직이는지 한 번에 보여준다.
    가동 범위는 실측 서보 영점에서 유도한 것이라, 여기서 도는 폭이 곧
    실물이 낼 수 있는 폭이다.
    """
    m = mujoco.MjModel.from_xml_path(MJCF_SCENE)
    d = mujoco.MjData(m)
    r = mujoco.Renderer(m, H, W)
    q = standingQpos()
    rng = jointRanges(m)
    adr = [m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)]
           for n in JOINT_ORDER]
    out = []
    n = int(seconds * FPS)
    per = n // len(JOINT_ORDER)
    for i in range(n):
        j = min(i // per, len(JOINT_ORDER) - 1)
        ph = (i % per) / per
        qq = q.copy()
        # 기립 자세에서 ±0.30 rad. 가동 범위 안으로 자른다.
        qq[j] = float(np.clip(q[j] + 0.30 * np.sin(2 * np.pi * ph), *rng[j]))
        mujoco.mj_resetData(m, d)
        d.qpos[2] = 0.34                              # 띄워 둔다. 접촉이 자세를 흔든다
        for k, a in enumerate(adr):
            d.qpos[a] = qq[k]
        mujoco.mj_forward(m, d)
        r.update_scene(d, camera=camera(0.60, 140 + 24 * i / n, -12, (0, 0, 0.20)))
        out.append(r.render())
    r.close()
    return out


# --- 컷 6. 무게중심과 대각 지지선 ----------------------------------------
def cut6(seconds=6.0):
    """트롯이 버티는 선과 무게중심이 어긋나 있는 것을 보인다.

    빨간 선이 대각선 두 발을 잇는 지지선, 노란 구가 무게중심이다. 트롯은
    주기의 일부를 그 두 발로만 버티므로, 무게중심이 선 뒤에 있으면 뒤로 넘어간다.
    8/20 에 실기에서 뒤로 몇 번 넘어진 것이 이것이고, 피치 트림이 그것을
    상쇄하고 있었다.

    숫자는 검증 게이트 7 이 매번 재는 것이다 (validate_mjcf.py).
    """
    m = mujoco.MjModel.from_xml_path(MJCF_SCENE)
    d = mujoco.MjData(m)
    r = mujoco.Renderer(m, H, W)
    standModel(m, d)
    sid = {l: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_SITE, f'{l}_foot') for l in LEGS}
    out = []
    n = int(seconds * FPS)
    for i in range(n):
        # 위에서 내려다보되 가까이 붙는다. 어긋남이 10.5mm 라 멀리서는 마커에
        # 가려 안 보인다. 마커도 그 간격보다 작아야 한다.
        r.update_scene(d, camera=camera(0.30, 178, -26 - 30 * i / n, (-0.03, 0, 0.03)))
        fl, rr = d.site_xpos[sid['FL']].copy(), d.site_xpos[sid['RR']].copy()
        fr, rl = d.site_xpos[sid['FR']].copy(), d.site_xpos[sid['RL']].copy()
        for a, b in ((fl, rr), (fr, rl)):
            a[2] = b[2] = 0.003
            connector(r.scene, a, b, (0.95, 0.28, 0.20, 0.9), 0.0022)
        cross = (fl + rr) / 2.0                       # 대각선이 만나는 점
        com = d.subtree_com[1].copy()
        marker(r.scene, [cross[0], cross[1], 0.003], (0.95, 0.28, 0.20, 1.0), 0.006)
        marker(r.scene, [com[0], com[1], 0.003], (1.0, 0.85, 0.15, 1.0), 0.006)
        # 둘을 잇는 선. 이 선의 길이가 어긋난 양이다.
        connector(r.scene, [cross[0], cross[1], 0.003], [com[0], com[1], 0.003],
                  (1.0, 1.0, 1.0, 0.95), 0.0016)
        out.append(r.render())
    r.close()
    return out


# --- 컷 7. 시뮬 보행 (시나리오 17번, 실물과 좌우 분할용) ----------------
def cut7(seconds=10.0):
    """실물과 나란히 놓을 시뮬 보행. 8/20 실기와 같은 설정으로 돌린다.

    시나리오 17번 자막이 "시뮬레이션과 실물을 같은 자로" 인데, 서 있는 모델이
    도는 컷(cut3)을 실물 보행 옆에 붙이면 그 말이 성립하지 않는다. 같은 자로
    쟀다는 근거는 같은 궤적 코드로 걸었을 때 속도가 맞았다는 것이다 —
    실측 50mm/s, 시뮬 49mm/s (8/21).

    실기 설정: 주기 1400ms, 스윙비율 0.143, 발 들어올림 20mm, 보폭 70mm,
    피치 트림 +3. 몸통 높이는 95 — 당시 화면에는 110 이었으나 링크가 18mm
    길게 잡혀 있어 실제 자세가 그것이다 (결정.md CC-1).

    카메라는 옆에서 따라간다. 실물 촬영이 측면 고정이므로 붙였을 때 어색하지 않다.
    """
    from Kinematics.kinematicMotion import TrottingGait
    from Common.gait_params import defaultParams, gaitPhases
    from Kinematics.kinematics import Kinematic as K

    m = mujoco.MjModel.from_xml_path(MJCF_SCENE)
    d = mujoco.MjData(m)
    r = mujoco.Renderer(m, H, W)
    kin = K()
    kb = dict(defaultParams(), Tt=1400.0, duty=0.143, Sh=20.0, height=95.0,
              IDstepLength=-70.0, IDstepWidth=0.0, IDstepAlpha=0.0,
              IDtrim=[3.0, 3.0, -3.0, -3.0])
    g = TrottingGait(); g.Sh = kb['Sh']; g.t1, g.t3 = gaitPhases(kb)
    aid = [mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, n) for n in JOINT_ORDER]
    sg = jointSigns()
    mujoco.mj_resetData(m, d)
    d.qpos[2] = standingTrunkHeight() + 0.01
    out = []
    step = m.opt.timestep
    for i in range(int(seconds * FPS)):
        for _ in range(int(1.0 / FPS / step)):
            th = np.asarray(kin.calcIK(g.positions(d.time, kb), (0, 0, 0),
                                       (50, 40 + kb['height'], 0)), float)
            tgt = sg * np.array([th[LEGS.index(n.split('_')[0])]
                                 [JOINTS.index(n.split('_')[1])] for n in JOINT_ORDER])
            if not np.isnan(tgt).any():
                for k, a in enumerate(aid):
                    d.ctrl[a] = tgt[k]
            mujoco.mj_step(m, d)
        look = d.xpos[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, 'trunk')].copy()
        look[2] -= 0.05
        r.update_scene(d, camera=camera(0.55, 90, -6, look))   # 정측면
        out.append(r.render())
    r.close()
    print(f"    전진 {d.qpos[0]*1000:+.0f}mm / {seconds:.0f}초 = {d.qpos[0]/seconds*1000:+.0f}mm/s")
    return out


CUTS = {1: cut1, 2: cut2, 3: cut3, 4: cut4, 5: cut5, 6: cut6, 7: cut7}

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
