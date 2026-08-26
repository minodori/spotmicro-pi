"""실측 링크 상수에서 MuJoCo MJCF 를 생성한다.

치수를 URDF 에서 가져오지 않는 이유:

  urdf/spotmicroai_gen.urdf.xml 은 실물과 부분적으로 다르다. 어디가 다른지
  정확히 적어 둔다 - 이 저장소가 "치수가 크게 틀렸다" 고 과장했던 곳이다.

      대퇴   120mm      실측 110      +9%
      하퇴   135mm      실측 135      일치
      l2     0          실측 20       빠짐
      질량   5.30kg     실측 2.2kg    2.4배
      관성   ixx=1000 12개, 100 8개   플레이스홀더

  하퇴는 맞다. toe 조인트 원점이 -0.115 지만 그 끝에 반지름 0.02 구체가 붙어
  접지점이 135mm 다. 구체를 빼고 115 와 비교하면 17% 차이로 보이는데, 그것은
  같은 것을 재지 않은 것이다. 원저자들 로봇은 실제로 걷는다.

  work11.md §6.25 는 "코드의 링크 길이가 실물과 달라 몇 주를 잃었다" 고 기록한다.
  같은 실수를 시뮬레이터에서 반복하지 않으려면 치수의 출처가 하나여야 한다.
  그래서 Kinematics/kinematics.py 의 상수를 import 한다. IK 와 시뮬레이터가
  같은 숫자를 쓰게 되고, 한쪽만 고쳐 어긋나는 일이 구조적으로 불가능해진다.

좌표계 변환 (SpotMicroAI -> MuJoCo):

  kinematics.py 는 x 전후 / y 상하 / z 좌우 를 쓴다 (y 가 위, 발끝이 y=-100).
  MuJoCo 관례는 x 전방 / y 좌 / z 상 이다.
      mjc_x = +kin_x      mjc_y = +kin_z      mjc_z = +kin_y
  단위도 다르다. kinematics 는 mm, MuJoCo 는 m 다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Kinematics.kinematics import Kinematic
from Common.servo_map import (FUTABA_INDICES, JOINT_NAMES, SERVO_SIGN,
                              thetaLimitsDeg)

MM = 0.001

# 질량 (kg). 실측은 총 2.2kg / 앞 0.8kg 뿐이므로 (work11 §6.18) 링크별 배분은 추정이다.
# 부품 단위로 재서 확정할 것 — 이 값들이 학습되는 로봇의 관성을 정한다.
#
# 메시에서 관성을 자동 계산하지 않는다. 메시는 서보가 안에 들어 있다는 걸 모른다.
# DS3235 는 강철 기어와 구리로 60g 인데 그걸 감싼 프린트 껍데기는 15g 이다.
# 메시 기반 관성은 "정밀하게 계산된 쓰레기" 가 되어 ixx=100 과 실패 방식이 같다.
# 대신 충돌 프리미티브에 실측 질량을 주고 MuJoCo 가 그 형상에서 관성을 뽑게 한다.
MASS = {
    # 이 1.180 은 전면 플레이트에 CM4 가 얹힌 상태에서 잰 값이다. 문서상 기준
    # 보드는 Pi 4B 4GB 이고 (결정.md CC-13), 교체하면 질량과 그 위치가 둘 다
    # 바뀐다 -> 게이트 6/7 의 무게중심과 gait_params 의 피치 트림 기본값을
    # 다시 잡아야 한다. 그때까지는 실물과 같은 CM4 값을 쓴다.
    'trunk':    1.180,      # 프레임 + LiPo + CM4 + PCA9685 x2 + UBEC
    'hip':      0.100,      # 어깨 서보 + 브래킷
    'upper':    0.110,      # 무릎 서보 + 대퇴
    'lower':    0.040,      # 하퇴
    'foot':     0.005,      # 미끄럼방지 패드 (추후 TPU 신발)
}

# 무게중심의 전후 위치 (m, 어깨축 중점 기준. 음수가 뒤).
#
# work11 §6.18 실측: 앞발 800g / 전체 2200g. 어깨축이 ±92.5mm 에 있으므로
#   앞 하중 비율 = (Xcom + 92.5) / 185 = 800/2200 = 36.4%  ->  Xcom = -25.2mm
# 이 값이 트롯의 안정성을 지배한다. 주기의 28.6% 를 대각선 두 발로만 버티고,
# 그때 지지선이 무게중심을 지나야 넘어지지 않기 때문이다 (§6.25).
#
# 주의: §6.18 의 실측 자체가 불확실하다 (앞 800 + 뒤 1000 = 1800 인데 전체는 2200,
# 18% 불일치). 도메인 랜덤화에서 ±15mm 흔들 것.
COM_X = -0.0252

# 서보 최대 토크 (N·m). 우리가 쓰는 6V 에서 DS3235 스톨은 32kg·cm = 3.14 이고,
# 여기 3.0 은 그 96% 다 — 7.4V(3.43) 기준으로 잡았을 때의 87% 여유가 아니다.
# **여유라고 부를 수 없는 값이다.** MuJoCo 액추에이터는 forcerange 에 무한정
# 머무를 수 있지만 실물 서보는 스톨 근처에서 열이 나 버틴다. 여기 기대어 학습한
# 정책은 이식되지 않는다. 연속 토크 기준(보통 스톨의 50~60%)으로 다시 잡아야 하고,
# 그것은 재학습을 뜻하므로 제출 뒤에 한다 (결정.md CC-19).
# 인덱스 5 (FR-Shoulder) 만 Futaba 25kg 이라 2.5 로 낮춘다 (work11 §0).
TORQUE_DS3235 = 3.0
TORQUE_FUTABA = 2.5

# MJCF 관절각 = 이 부호 x kinematics theta.  rl/fk_mapping.py 가 독립적으로 검증한다.
# 여기서 선언하고 거기서 확인하는 구조라, 축 정의를 바꾸면 검증이 바로 잡아낸다.
MJCF_SIGN = {'FL': (+1, -1, -1), 'FR': (-1, -1, -1),
             'RL': (+1, -1, -1), 'RR': (-1, -1, -1)}   # (shoulder, leg, foot)

# MJCF 관절 이름 -> 서보 인덱스. 가동 범위를 서보 오프셋에서 유도하는 데 쓴다.
JOINT_TO_SERVO = {}
for _i, (_leg, _th, _s) in enumerate(SERVO_SIGN):
    _legName = ('FL', 'FR', 'RL', 'RR')[_leg]
    JOINT_TO_SERVO[f"{_legName}_{('shoulder', 'leg', 'foot')[_th]}"] = _i


def jointRange(name):
    """MJCF 관절의 가동 범위 (rad). URDF 가 아니라 서보 오프셋에서 유도한다.

    URDF 의 값을 그대로 쓰면 실물이 낼 수 있는 각도를 sim 이 막거나 (기립 자세의
    무릎이 잘려 로봇이 주저앉는다), 반대로 실물이 못 내는 각도를 sim 이 허용해
    정책이 그걸 쓰도록 학습하고 servoRotate() 가 조용히 잘라낸다.
    """
    import math
    lo, hi = thetaLimitsDeg()[JOINT_TO_SERVO[name]]
    leg, joint = name.split('_')
    s = MJCF_SIGN[leg][('shoulder', 'leg', 'foot').index(joint)]
    a, b = sorted((s * math.radians(lo), s * math.radians(hi)))
    return a, b

# kv = forcerange / 무부하 각속도. 서보의 토크-속도 직선을 재현하는 값이라
# 이렇게 두면 액추에이터가 실제 서보보다 빨리 움직일 수 없다.
#
# ⚠ 545 는 **7.4V** 값이다. 우리 벅 컨버터는 6V 이고 그 열은 500°/s 다
#   (Common.servo_map.SERVO_RATED_SLEW). 그러므로 이 모델의 액추에이터는
#   실물보다 9% 빠르다.
#
# 그런데 지금 고치지 않는다. 이 상수는 kv 를 바꾸고, kv 는 모델의 물리를 바꾸며,
# checkpoints/policy.zip 은 **545 모델에서 학습된 것**이다. 모델만 고치면
# 저장소의 정책과 저장소의 모델이 서로 다른 로봇을 가리키게 된다 — 지금은
# 문서만 어긋나 있고 모델과 정책은 짝이 맞는다. 조용히 어긋나는 쪽이 더 나쁘다.
#
# 제출 뒤 순서: 여기를 SERVO_RATED_SLEW 로 바꾸고 -> 모델 재생성 -> make verify
# -> 재학습 -> 정책 교체. 10월 기능테스트 전까지 (결정.md CC-19).
NO_LOAD_RAD_S = 545.0 * 3.141592653589793 / 180.0

LEGS = [   # 이름, 전후 부호, 좌우 부호 (MuJoCo 좌표)
    ('FL', +1, +1),
    ('FR', +1, -1),
    ('RL', -1, +1),
    ('RR', -1, -1),
]


def build(kin=None):
    k = kin or Kinematic()
    l1, l2, l3, l4 = k.l1 * MM, k.l2 * MM, k.l3 * MM, k.l4 * MM
    L, W = k.L * MM, k.W * MM

    # 기립 높이. height=95 에서 어깨축~발바닥이 140+95=235mm 다 (gait_params 주석).
    stand = (140 + 95) * MM

    out = []
    a = out.append
    a('<mujoco model="spotmicro">')
    a('  <!-- rl/gen_mjcf.py 가 Kinematics/kinematics.py 에서 생성한다. 직접 고치지 말 것. -->')
    a(f'  <!-- l1={k.l1} l2={k.l2} l3={k.l3} l4={k.l4} L={k.L} W={k.W} (mm, work11 §6.25 실측) -->')
    # "auto" 는 <inertial> 이 있으면 그걸 쓰고 없으면 geom 에서 뽑는다.
    # URDF 를 읽을 때는 위험한 설정이지만 (플레이스홀더가 살아남는다), 이 파일은
    # 우리가 생성하므로 플레이스홀더가 없다. 아는 곳(몸통 무게중심)만 명시하고
    # 모르는 곳(다리)은 형상에서 계산하게 하는 것이 정확하다.
    a('  <compiler angle="radian" autolimits="true"')
    a('            inertiafromgeom="auto" inertiagrouprange="0 0"/>')
    a('  <option timestep="0.004" iterations="10" solver="Newton" cone="elliptic"/>')
    a('')
    a('  <default>')
    a('    <geom group="0" condim="3" friction="0.9 0.02 0.001"/>')
    a('    <joint type="hinge" armature="0.008" damping="0.05" frictionloss="0.05"/>')
    a(f'    <position kp="25" kv="{TORQUE_DS3235 / NO_LOAD_RAD_S:.3f}"'
      f' forcerange="-{TORQUE_DS3235} {TORQUE_DS3235}"/>')
    a('  </default>')
    a('')
    a('  <worldbody>')
    a(f'    <body name="trunk" pos="0 0 {stand:.4f}">')
    a('      <freejoint name="root"/>')
    # 충돌 상자는 몸통 외형 그대로 두고, 질량 중심만 실측 위치로 옮긴다.
    # 상자를 통째로 뒤로 밀면 충돌 형상이 몸통 밖으로 나간다.
    mt, bh = MASS['trunk'], 0.060
    comX = COM_X * (mt + 4 * (MASS['hip'] + MASS['upper'] + MASS['lower']
                              + MASS['foot'])) / mt
    a(f'      <inertial pos="{comX:.4f} 0 0" mass="{mt}"'
      f' diaginertia="{mt/12*(W**2+bh**2):.6f} {mt/12*(L**2+bh**2):.6f}'
      f' {mt/12*(L**2+W**2):.6f}"/>')
    a(f'      <geom name="trunk" type="box" size="{L/2:.4f} {W/2:.4f} {bh/2:.4f}"'
      f' mass="{mt}"/>')
    a('      <site name="imu" pos="0 0 0"/>')

    for name, fx, fy in LEGS:
        # 어깨축은 몸통 네 모서리. L 은 앞뒤 어깨축 간격, W 는 좌우 어깨축 간격.
        hx, hy = fx * L / 2, fy * W / 2
        a('')
        a(f'      <body name="{name}_hip" pos="{hx:.4f} {hy:.4f} 0">')
        # 어깨(abduction): 전후축 둘레 회전
        a(f'        <joint name="{name}_shoulder" axis="1 0 0"'
          f' range="{jointRange(name + "_shoulder")[0]:.3f}'
          f' {jointRange(name + "_shoulder")[1]:.3f}"/>')
        # 어깨(abduction): 전후축(x) 둘레 회전
        
        a(f'        <geom name="{name}_hip" type="capsule" mass="{MASS["hip"]}"'
          f' fromto="0 0 0 0 {fy*l1:.4f} 0" size="0.018"/>')
        # l1 은 좌우 성분, l2 는 수직 성분. URDF 에는 l2 가 빠져 있었다.
        a(f'        <body name="{name}_upper" pos="0 {fy*l1:.4f} {-l2:.4f}">')
        a(f'          <joint name="{name}_leg" axis="0 1 0"'
          f' range="{jointRange(name + "_leg")[0]:.3f} {jointRange(name + "_leg")[1]:.3f}"/>')
        a(f'          <geom name="{name}_upper" type="capsule" mass="{MASS["upper"]}"'
          f' fromto="0 0 0 0 0 {-l3:.4f}" size="0.014"/>')
        a(f'          <body name="{name}_lower" pos="0 0 {-l3:.4f}">')
        a(f'            <joint name="{name}_foot" axis="0 1 0"'
          f' range="{jointRange(name + "_foot")[0]:.3f} {jointRange(name + "_foot")[1]:.3f}"/>')
        a(f'            <geom name="{name}_lower" type="capsule" mass="{MASS["lower"]}"'
          f' fromto="0 0 0 0 0 {-l4:.4f}" size="0.011"/>')
        # 발끝. 착지 충격이 무릎 혼을 이탈시킨 원인이므로 (work11 §6.16.3, §6.17)
        # 접촉을 약간 무르게 둔다.
        a(f'            <geom name="{name}_foot" type="sphere" mass="{MASS["foot"]}"'
          f' pos="0 0 {-l4:.4f}" size="0.012" solref="0.015 1"/>')
        # touch 센서는 site 부피 안에 들어온 접촉만 센다. 크기가 없으면 0 만 읽힌다.
        a(f'            <site name="{name}_foot" type="sphere" size="0.018"'
          f' pos="0 0 {-l4:.4f}"/>')
        a('          </body>')
        a('        </body>')
        a('      </body>')

    a('    </body>')
    a('  </worldbody>')
    a('')
    a('  <actuator>')
    for name, _, _ in LEGS:
        for joint in ('shoulder', 'leg', 'foot'):
            jn = f'{name}_{joint}'
            if JOINT_TO_SERVO[jn] in FUTABA_INDICES:
                a(f'    <position name="{jn}" joint="{jn}" kp="25"'
                  f' kv="{TORQUE_FUTABA / NO_LOAD_RAD_S:.3f}"'
                  f' forcerange="-{TORQUE_FUTABA} {TORQUE_FUTABA}"/>   <!-- Futaba 25kg -->')
            else:
                a(f'    <position name="{jn}" joint="{jn}"/>')
    a('  </actuator>')
    a('')
    a('  <sensor>')
    a('    <gyro name="gyro" site="imu"/>')             # BNO085 로 실기에 존재
    a('    <framequat name="orient" objtype="site" objname="imu"/>')
    a('    <framelinvel name="base_vel" objtype="site" objname="imu"/>')  # 특권정보: 보상 전용
    for name, _, _ in LEGS:
        a(f'    <touch name="{name}_touch" site="{name}_foot"/>')         # 특권정보: 보상 전용
    a('  </sensor>')
    a('</mujoco>')
    return '\n'.join(out) + '\n'


SCENE = """<mujoco model="spotmicro_scene">
  <include file="spotmicro.xml"/>
  <statistic center="0 0 0.15" extent="0.8"/>
  <visual>
    <headlight diffuse="0.6 0.6 0.6" ambient="0.3 0.3 0.3"/>
    <!-- offwidth/offheight 를 올리지 않으면 오프스크린 렌더가 640x480 에서 잘린다.
         시연 영상을 1080p 로 뽑기 위한 값이다. -->
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
    <camera name="track" mode="trackcom" pos="0 -1.2 0.5" xyaxes="1 0 0 0 0.4 1"/>
  </worldbody>
</mujoco>
"""


if __name__ == '__main__':
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mjcf')
    with open(os.path.join(here, 'spotmicro.xml'), 'w') as f:
        f.write(build())
    with open(os.path.join(here, 'scene_flat.xml'), 'w') as f:
        f.write(SCENE)
    print(f"wrote {here}/spotmicro.xml, scene_flat.xml")
