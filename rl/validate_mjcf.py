"""MJCF 검증 게이트. 학습 한 스텝 전에 전부 통과시킨다.

가장 중요한 것은 게이트 3 (FK 대조) 이다. MJCF 와 IK 가 같은 기하·같은 부호규약을
쓴다는 것을 증명하므로, 통과하면 servo_controller.angleToServo() 를 그대로
정책 배포에 재사용할 수 있다.
"""
import os
import sys

import numpy as np
import mujoco

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from Kinematics.kinematics import Kinematic                    # noqa: E402
from Kinematics.kinematicMotion import TrottingGait            # noqa: E402
from rl.fk_mapping import solve, LEGS, JOINTS                  # noqa: E402

TOTAL_MASS = 2.20
STAND_HEIGHT = 110.0          # gait_params 기본값
results = []


def gate(name, ok, detail=''):
    results.append((name, ok))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   {detail}" if detail else ''))
    return ok


def standingQpos(kin, signs, model):
    """기립 자세의 MJCF 관절각. start_automatic_gait 의 정지 자세와 같은 발 위치를 쓴다."""
    g = TrottingGait()
    Lp = np.array([[g.Fo, -100, g.Spf, 1], [g.Fo, -100, -g.Spf, 1],
                   [-g.Ro, -100, g.Spr, 1], [-g.Ro, -100, -g.Spr, 1]], dtype=float)
    th = kin.calcIK(Lp, (0, 0, 0), (50, 40 + STAND_HEIGHT, 0))
    q = {}
    for i, leg in enumerate(LEGS):
        for j, joint in enumerate(JOINTS):
            q[f'{leg}_{joint}'] = signs[leg][j] * th[i][j]
    return q


print("MJCF 검증\n")

# --- 1. 컴파일 -------------------------------------------------------------
model = mujoco.MjModel.from_xml_path(os.path.join(HERE, 'mjcf', 'scene_flat.xml'))
data = mujoco.MjData(model)
gate("1. 컴파일 (바닥 포함)", True,
     f"body {model.nbody}, joint {model.njnt}, actuator {model.nu}")

# --- 2. 질량 --------------------------------------------------------------
total = float(model.body_mass.sum())
gate("2. 총 질량", abs(total - TOTAL_MASS) < 0.02, f"{total:.3f}kg (목표 {TOTAL_MASS})")

# --- 3. FK 대조 (무작위 자세에서 부호까지) ---------------------------------
kin = Kinematic()
signs, err = solve(model, data, kin, samples=40)
sd = '  '.join(f"{l}{''.join('+' if x > 0 else '-' for x in signs[l])}" for l in LEGS)
gate("3. FK 대조 (40자세 x 4다리)", err < 1.0, f"최대 {err:.4f}mm   부호 {sd}")

# --- 4. 관성이 플레이스홀더가 아닌지 ---------------------------------------
bad = []
for i in range(1, model.nbody):
    m = model.body_mass[i]
    if m <= 0:
        continue
    r = np.sqrt(model.body_inertia[i].max() / m)
    if not (0.002 < r < 0.30):
        bad.append(f"{mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)} r={r*1000:.0f}mm")
gate("4. 관성 규모", not bad, "등가 회전반경 전부 2~300mm" if not bad else ', '.join(bad))

# --- 5. 기립 & 하중 배분 ---------------------------------------------------
qadr = {n: model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n)]
        for n in (f'{l}_{j}' for l in LEGS for j in JOINTS)}
aid = {n: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, n) for n in qadr}
stand = standingQpos(kin, signs, model)

mujoco.mj_resetData(model, data)
data.qpos[2] = 0.30
for n, v in stand.items():
    data.qpos[qadr[n]] = v
    data.ctrl[aid[n]] = v
for _ in range(int(4.0 / model.opt.timestep)):
    mujoco.mj_step(model, data)

z = float(data.qpos[2])
ok = np.isfinite(data.qpos).all() and 0.10 < z < 0.35
gate("5. 기립 안정 (5cm 낙하)", ok, f"4초 후 몸통 {z*1000:.0f}mm")

# 무게중심 — 트롯 안정성을 지배하는 값이라 하중배분보다 이걸 직접 본다.
# 주기의 28.6% 를 대각선 두 발로만 버티고, 그때 지지면은 두 발을 잇는 선이다.
# 그 선이 무게중심을 지나야 넘어지지 않는다 (work11 §6.25).
mujoco.mj_resetData(model, data)
data.qpos[2] = 0.30
mujoco.mj_forward(model, data)
com = float(data.subtree_com[1][0]) * 1000.0        # trunk 서브트리 = 로봇 전체
gate("6. 무게중심 전후 위치", abs(com - (-25.2)) < 2.0,
     f"{com:+.1f}mm (실측 800g/2200g -> -25.2)")

# 대각 지지선이 무게중심을 지나는가 (기립 자세 기준)
mujoco.mj_resetData(model, data)
data.qpos[2] = 0.30
for n, v in stand.items():
    data.qpos[qadr[n]] = v
mujoco.mj_forward(model, data)
tr = data.xpos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'trunk')]
fx = {l: (data.site_xpos[mujoco.mj_name2id(
    model, mujoco.mjtObj.mjOBJ_SITE, f'{l}_foot')][0] - tr[0]) * 1000 for l in LEGS}
cross = (fx['FL'] + fx['RR']) / 2.0
comStand = float(data.subtree_com[1][0]) * 1000.0
gate("7. 대각 지지선 vs 무게중심", abs(cross - comStand) < 12.0,
     f"교차 {cross:+.1f}mm, 무게중심 {comStand:+.1f}mm, 차이 {cross-comStand:+.1f}mm")

# --- 8. 액추에이터 ---------------------------------------------------------
fr = model.actuator_forcerange
fu = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, 'FR_shoulder')
gate("8. 액추에이터", model.nu == 12 and abs(fr[fu][1] - 2.5) < 1e-6,
     f"12개, FR-Shoulder {fr[fu][1]:.1f}N·m (Futaba), 나머지 {fr[0][1]:.1f}")

print()
nfail = sum(1 for _, ok in results if not ok)
print(f"{len(results)-nfail}/{len(results)} 통과")
sys.exit(1 if nfail else 0)
