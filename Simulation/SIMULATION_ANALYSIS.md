# SpotMicroAI PyBullet 시뮬레이션 코드 분석

## 목차
1. [전체 구조](#1-전체-구조)
2. [파일별 역할](#2-파일별-역할)
3. [메인 진입점: pybullet_automatic_gait.py](#3-메인-진입점-pybullet_automatic_gaitpy)
4. [로봇 클래스: spotmicroai.py](#4-로봇-클래스-spotmicroaipy)
5. [역기구학: kinematics.py](#5-역기구학-kinematicspy)
6. [보행 생성: kinematicMotion.py](#6-보행-생성-kinematicmotionpy)
7. [키보드 입력: Common/multiprocess_kb.py](#7-키보드-입력-commonmultiprocess_kbpy)
8. [전체 데이터 흐름](#8-전체-데이터-흐름)
9. [좌표계와 핵심 자료구조](#9-좌표계와-핵심-자료구조)
10. [보행 알고리즘 상세](#10-보행-알고리즘-상세)

---

## 1. 전체 구조

```
Simulation/
├── pybullet_automatic_gait.py   # 메인 실행 파일 (키보드 제어)
├── spotmicroai.py               # 로봇 PyBullet 제어 클래스
├── kinematics.py                # 역기구학 (foot 위치 → 관절각)
├── kinematicMotion.py           # 트로팅 보행 패턴 생성
├── environment.py               # 환경 클래스 (미구현 placeholder)
├── gym_test.py                  # OpenAI Gym 인터페이스 테스트
│
├── Common/
│   └── multiprocess_kb.py       # 멀티프로세스 키보드 입력 처리
│
├── Kinematics/
│   └── kinematics.py            # 역기구학 (spotmicroai.py가 이쪽을 import)
│
├── gym_spotmicroai/             # OpenAI Gym 환경 래퍼
│   └── envs/spotmicroai_env.py
│
└── urdf/ (상위 디렉토리)
    ├── spotmicroai_gen.urdf.xml  # 로봇 URDF 모델 (12관절)
    └── stairs_gen.urdf.xml       # 계단 환경
```

### 의존성 그래프

```
pybullet_automatic_gait.py
    ├── spotmicroai.Robot           ─── PyBullet 물리 엔진
    │       └── Kinematics.kinematics.Kinematic  ─── 역기구학
    ├── kinematicMotion.TrottingGait ─── 트로팅 보행 생성
    └── Common.multiprocess_kb.KeyInterrupt ─── 키보드 입력 (별도 프로세스)
```

---

## 2. 파일별 역할

| 파일 | 역할 | 핵심 클래스/함수 |
|------|------|-----------------|
| `pybullet_automatic_gait.py` | 진입점, 메인 루프 | `main()` |
| `spotmicroai.py` | 로봇 물리 제어 | `Robot`, `RobotState` |
| `kinematics.py` | 역기구학 계산 | `Kinematic.calcIK()`, `Kinematic.legIK()` |
| `kinematicMotion.py` | 보행 패턴 생성 | `TrottingGait.positions()`, `TrottingGait.calcLeg()` |
| `Common/multiprocess_kb.py` | 키보드 입력 | `KeyInterrupt.keyInterrupt()` |

---

## 3. 메인 진입점: pybullet_automatic_gait.py

### 실행 흐름

```
__main__
    ├── KeyInterrupt() 생성          # 키보드 핸들러 초기화
    ├── Process(keyInterrupt).start() # 별도 프로세스로 키보드 입력 시작
    └── main(id, command_status)     # 메인 시뮬레이션 루프
```

### `main()` 함수 구조 (line 53~106)

#### 초기화 단계 (line 54~69)

```python
robot = spotmicroai.Robot(False, True, reset)

spurWidth = robot.W/2 + 20   # 좌우 발 간격 (120/2 + 20 = 80)
stepLength = 0                # 보폭 초기값
stepHeight = 72               # 발 높이 초기값
iXf = 120                     # 앞다리 X 위치
iXb = -132                    # 뒷다리 X 위치

IDheight = p.addUserDebugParameter("height", -40, 90, 20)  # GUI 슬라이더

# 4개 발의 초기 위치 (동차좌표 [x, y, z, 1])
Lp = np.array([
    [iXf, -100, spurWidth,  1],   # 앞-왼쪽 (FL)
    [iXf, -100, -spurWidth, 1],   # 앞-오른쪽 (FR)
    [-50, -100, spurWidth,  1],   # 뒤-왼쪽 (RL)
    [-50, -100, -spurWidth, 1],   # 뒤-오른쪽 (RR)
])

trotting = TrottingGait()         # 트로팅 보행 객체
```

#### 메인 루프 (line 73~106)

```
while True:
    1. 로봇 위치·자세 읽기 (getPos, getIMU)
    2. 원점에서 50 이상 벗어나면 → resetBody()
    3. 키보드 명령 큐에서 result_dict 읽기
    4. StartStepping == True
           → trotting.positions(d-3, result_dict)  # 트로팅 발 위치 계산
       False
           → Lp (정적 위치 유지)
    5. robot.feetPosition(...)    # 발 위치 설정
    6. robot.bodyRotation(...)    # 몸체 회전 설정
    7. robot.bodyPosition(...)    # 몸체 위치 설정
    8. robot.step()               # 물리 시뮬레이션 1스텝
    9. consoleClear()             # 터미널 지우기
```

#### 리셋 조건
- `distance > 50`: 로봇이 원점에서 50단위 이상 이탈 시 자동 리셋
- roll/pitch > 60°: `checkSimulationReset()`에서 넘어짐 감지 → 리셋

---

## 4. 로봇 클래스: spotmicroai.py

### RobotState (Enum)

```python
class RobotState(Enum):
    OFF    = 0   # 비활성
    READY  = 1   # 대기 자세
    STAND  = 2   # 기립
    TROTTING_GAIT = 3   # 트로팅 보행 (0/3, 1/2 다리 교대)
    CRAWL  = 4   # 4보 크롤 (1→2→3→0)
    CRAWL2 = 5   # 역방향 크롤 (2→1→3→0)
```

> 현재 시뮬레이션에서 상태머신은 미사용 — `pybullet_automatic_gait.py`가 직접 발 위치를 제어함

### Robot 클래스 주요 파라미터

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| `fixedTimeStep` | 1/550 초 | 물리 업데이트 주기 |
| `numSolverIterations` | 200 | 물리 엔진 반복 횟수 |
| `kp` | 0.045 | 서보 위치 제어 비례 이득 |
| `kd` | 0.4 | 서보 속도 제어 미분 이득 |
| `maxForce` | 25.0 | 최대 토크 |
| `L` | 140 | 몸체 길이 |
| `W` | 120 (75+5+40) | 몸체 폭 |

### 초기화 순서 (`__init__`)

```
1. PyBullet 연결 (SHARED_MEMORY → 실패 시 GUI)
2. GUI 디버그 슬라이더 추가 (Kp, Kd, MaxForce)
3. loadModels()    → URDF 로드 (바닥면, 계단, 로봇)
4. createEnv()     → 5×5 콘크리트 타일 바닥 생성
5. changeDynamics() → 모든 관절 관성 최소화 (0.000001)
6. getJointNames() → 관절명 → 인덱스 딕셔너리 생성
7. LIDAR 초기화   → 360개 레이 설정 (반경 12m)
8. Kinematic()    → 역기구학 객체 생성
9. 카메라 설정    → 90° FOV, 320×200 해상도
```

### `step()` 메서드 — 물리 시뮬레이션 1스텝 (line 270~335)

```
step():
    1. 시간 업데이트 (실시간 or 고정 스텝)
    2. 로봇 위치·자세·속도 읽기
    3. GUI 슬라이더에서 Kp, Kd, MaxForce 읽기
    4. 카메라 업데이트 (handleCamera)
    5. 넘어짐 검사 (checkSimulationReset)
    6. 역기구학 계산:
           self.angles = self.kin.calcIK(self.Lp, self.rot, self.pos)
    7. 12개 관절 모터 제어:
           for leg in [FL, FR, RL, RR]:
               for part in [shoulder, leg, foot]:
                   setJointMotorControl2(POSITION_CONTROL, angle, kp, kd, force)
    8. LIDAR 레이캐스트 (0.2초마다 360개 레이)
    9. 고정 스텝 모드: stepSimulation() + sleep()
```

### 관절 제어 방식

```
각 다리 3개 관절 (shoulder / leg / foot)
× 4개 다리 (front_left / front_right / rear_left / rear_right)
= 총 12개 관절

제어: POSITION_CONTROL (PID 위치 제어)
  targetPosition = angles[lx][px] * dirs[lx][px]
  dirs = [[-1,1,1], [1,1,1], [-1,1,1], [1,1,1]]  # 방향 부호 보정
```

### LIDAR 시스템

- 360개 레이, 원형 배치, 높이 0.045m
- 최대 감지 거리 12m
- 0.2초마다 갱신 (`rayTestBatch`)
- 충돌 감지 시 빨간색, 미감지 시 초록색 (debugLidar=True일 때만 표시)
- 현재 버전에서는 감지 데이터를 상위 로직에 전달하지 않음 (미래 기능 예정)

---

## 5. 역기구학: kinematics.py

### 다리 구조 파라미터

```
l1 = 50   Coxa  (hip → shoulder 관절)
l2 = 20   Transition (짧은 링크)
l3 = 100  Femur (대퇴부)
l4 = 100  Tibia (하퇴부)

L  = 140  몸체 길이
W  = 75   몸체 폭
```

### `bodyIK()` — 몸체 변환 행렬 계산

```python
def bodyIK(omega, phi, psi, xm, ym, zm):
```

**입력**
- `omega`: 롤 (roll) 각도
- `phi`: 피치 (pitch) 각도
- `psi`: 요 (yaw) 각도
- `xm, ym, zm`: 몸체 중심 위치 오프셋

**처리**
```
Rx(omega) * Ry(phi) * Rz(psi) = Rxyz  # 3D 회전 행렬 합성
T = 변환 행렬 + Rxyz                   # 동차 변환 행렬
각 다리 부착점 오프셋 적용:
  - FL: (+L/2, 0, +W/2)
  - FR: (+L/2, 0, -W/2)
  - RL: (-L/2, 0, +W/2)
  - RR: (-L/2, 0, -W/2)
```

**출력**: 4개 다리 변환 행렬 `[Tlf, Trf, Tlb, Trb]`

### `legIK()` — 단일 다리 역기구학

```python
def legIK(point):  # point = (x, y, z)
```

**알고리즘 (기하학적 방법)**

```
F = sqrt(x² + y² - l1²)   # 수평 투영 거리
G = F - l2                  # l2 제거 후 거리
H = sqrt(G² + z²)          # 발까지 직선 거리

theta1 = -atan2(y, x) - atan2(F, -l1)          # 어깨 회전각

D = (H² - l3² - l4²) / (2 * l3 * l4)           # 코사인 법칙
theta3 = acos(D)                                  # 무릎 굴곡각

theta2 = atan2(z, G) - atan2(l4*sin(θ3), l3 + l4*cos(θ3))  # 고관절각
```

**출력**: `(theta1, theta2, theta3)` — 어깨/대퇴/하퇴 관절각 (라디안)

### `calcIK()` — 전체 역기구학

```python
def calcIK(Lp, angles, center):
```

```
(Tlf, Trf, Tlb, Trb) = bodyIK(roll, pitch, yaw, xm, ym, zm)

Ix = [[-1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]  # 좌우 대칭 반전

FL 각도 = legIK( inv(Tlf) · Lp[0] )
FR 각도 = legIK( Ix · inv(Trf) · Lp[1] )   # X축 반전 적용
RL 각도 = legIK( inv(Tlb) · Lp[2] )
RR 각도 = legIK( Ix · inv(Trb) · Lp[3] )   # X축 반전 적용
```

**출력**: `4×3 배열` — 4다리 × 3관절 각도

---

## 6. 보행 생성: kinematicMotion.py

### 클래스 구조

```
KinematicLegMotion   단일 다리 보간 이동
KinematicMotion      4개 다리 통합 조정
TrottingGait         트로팅 보행 패턴 (실제 사용)
```

### TrottingGait 보행 파라미터

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `t0` | 0 ms | 지면 대기 시간 |
| `t1` | 510 ms | 지면 드래그 시간 |
| `t2` | 0 ms | 지면 대기 시간 2 |
| `t3` | 185 ms | 발 들기 시간 |
| `Tt` | 695 ms | 전체 사이클 시간 |
| `Sl` | 0.0 | 보폭 (전후) |
| `Sw` | 0 | 횡폭 (좌우) |
| `Sh` | 60 | 발 높이 |
| `Sa` | 0 | 회전각 (yaw) |
| `Spf` | 87 | 앞다리 좌우 간격 |
| `Spr` | 77 | 뒷다리 좌우 간격 |

### `calcLeg()` — 단일 다리 위치 계산

```python
def calcLeg(t, x, y, z):
    startLp = [x - Sl/2, y, z - Sw/2, 1]   # 시작 위치
    endLp   = [x + Sl/2, y, z + Sw/2, 1]   # 끝 위치
```

**상태 머신 (사이클 내 t 기반)**

```
t < t0            → stay    : startLp 위치 유지
t0 ≤ t < t0+t1   → drag    : startLp → endLp 선형 이동 (지면 밀기)
                              + 회전 행렬 Ry(Sa*t_progress) 적용
t0+t1 ≤ t < t0+t1+t2 → stay : endLp 위치 유지
t0+t1+t2 ≤ t ≤ Tt   → lift  : endLp → startLp 복귀
                              + curLp[1] += Sh * sin(π * t_progress)  # 포물선 궤적
```

### `positions()` — 4개 발 위치 일괄 계산

```python
def positions(t, kb_offset={}):
```

**트로팅 위상 (trotting phase)**

```
Tt  = t0 + t1 + t2 + t3      # 전체 주기 (695ms)
Tt2 = Tt / 2                  # 반 주기 (347.5ms)

td  = (t × 1000) % Tt         # 대각선 페어 A 시간
t2  = (t × 1000 - Tt2) % Tt  # 대각선 페어 B 시간 (반 주기 오프셋)

다리 배치:
  FR (0번): calcLeg(td,  Fx, Fy, +spf)   ← 대각선 페어 A
  FL (1번): calcLeg(t2,  Fx, Fy, -spf)   ← 대각선 페어 B
  RR (2번): calcLeg(t2,  Rx, Ry, +spr)   ← 대각선 페어 B
  RL (3번): calcLeg(td,  Rx, Ry, -spr)   ← 대각선 페어 A
```

**트로팅 보행 패턴 시각화**

```
시간 →
     |── t0 ─|──── t1 ────|─ t2 ─|── t3 ──|
FR   [stay]  [drag →     ] [stay] [↑lift↑ ]   페어 A
RL   [stay]  [drag →     ] [stay] [↑lift↑ ]   페어 A (동시)

FL   [↑lift↑]  [stay] [drag →    ] [stay]      페어 B
RR   [↑lift↑]  [stay] [drag →    ] [stay]      페어 B (동시)
      ↑ Tt2 오프셋 차이
```

---

## 7. 키보드 입력: Common/multiprocess_kb.py

### KeyInterrupt 클래스

```python
X_STEP  = 10.0   # 전후 이동 단위
Y_STEP  = 5.0    # 좌우 이동 단위
YAW_STEP = 3.0   # 회전 단위
```

### 키 매핑

| 키 | 동작 |
|----|------|
| `w` | 전진 (stepLength 증가) |
| `s` | 후진 (stepLength 감소) |
| `a` | 왼쪽 이동 |
| `d` | 오른쪽 이동 |
| `q` | 반시계 회전 |
| `e` | 시계 회전 |
| `space` | 전체 리셋 (정지) |

### 멀티프로세스 구조

```
메인 프로세스                    키보드 프로세스
─────────────────                ─────────────────────
main()                           keyInterrupt()
  │                                │
  ├─ command_status.get()  ←───────┤─ command_status.put(result_dict)
  │                                │
  └─ command_status.put()  ──────→ │  (큐에 복원)
```

### command_status 딕셔너리 구조

```python
result_dict = {
    'IDstepLength': float,   # 전후 보폭 (w/s 키)
    'IDstepWidth':  float,   # 좌우 이동 (a/d 키)
    'IDstepAlpha':  float,   # 회전각 (q/e 키)
    'StartStepping': bool,   # 보행 시작 여부
}
```

---

## 8. 전체 데이터 흐름

```
[키보드 입력]
    키 누름 감지 (keyboard 라이브러리)
        │
        ▼
    calcRbStep()
    IDstepLength = X_STEP * (s_count - w_count)
    IDstepWidth  = Y_STEP * (d_count - a_count)
    IDstepAlpha  = YAW_STEP * (q_count - e_count)
        │
        ▼
    command_status Queue (프로세스 간 통신)
        │
        ▼
[메인 루프]
    result_dict = command_status.get()
        │
        ├── StartStepping == True
        │       │
        │       ▼
        │   TrottingGait.positions(t, result_dict)
        │       │
        │       ├── calcLeg(td, ...)   FR, RL
        │       └── calcLeg(t2, ...)   FL, RR
        │           └── 포물선 발 궤적 + 선형 드래그
        │               │
        │               ▼
        │           Lp [4×4 동차좌표]
        │
        └── StartStepping == False
                └── Lp = 정적 초기 위치
        │
        ▼
    robot.feetPosition(Lp)    # Lp 저장
    robot.bodyRotation(rot)   # rot 저장
    robot.bodyPosition(pos)   # pos 저장
        │
        ▼
    robot.step()
        │
        ▼
    Kinematic.calcIK(Lp, rot, pos)
        │
        ├── bodyIK(roll, pitch, yaw, x, y, z)
        │   └── 4개 다리 변환 행렬 (Tlf, Trf, Tlb, Trb)
        │
        └── legIK(inv(T) · Lp[i])  × 4
            └── (theta1, theta2, theta3) 각 다리
        │
        ▼
    angles [4×3 배열]
        │
        ▼
    p.setJointMotorControl2(POSITION_CONTROL)  × 12관절
        │
        ▼
    PyBullet 물리 엔진 (550Hz)
        │
        ▼
    렌더링 출력 (GUI 창)
```

---

## 9. 좌표계와 핵심 자료구조

### 좌표계 정의

```
PyBullet 월드 좌표계:
  X → 앞
  Y → 왼쪽
  Z → 위

로봇 바디 좌표계:
  X → 앞 (몸체 길이 방향)
  Y → 아래 (-100 = 발이 몸체 아래 100 단위)
  Z → 오른쪽 (양수)

발 위치 배열 Lp [4×4]:
  [FL_x, FL_y, FL_z, 1]   앞-왼쪽
  [FR_x, FR_y, FR_z, 1]   앞-오른쪽
  [RL_x, RL_y, RL_z, 1]   뒤-왼쪽
  [RR_x, RR_y, RR_z, 1]   뒤-오른쪽

동차좌표 마지막 원소 1 → 행렬 변환 시 이동(translation) 적용됨
```

### 관절각 배열 angles [4×3]

```
[[shoulder_FL, leg_FL, foot_FL],
 [shoulder_FR, leg_FR, foot_FR],
 [shoulder_RL, leg_RL, foot_RL],
 [shoulder_RR, leg_RR, foot_RR]]

단위: 라디안
dirs 배열로 방향 보정 후 PyBullet에 전달
dirs = [[-1,1,1], [1,1,1], [-1,1,1], [1,1,1]]
```

---

## 10. 보행 알고리즘 상세

### 트로팅 (Trotting) 이란?

4족 보행 로봇의 대각선 보행 패턴:
- **페어 A**: FL (앞-왼쪽) + RR (뒤-오른쪽) 동시 이동
- **페어 B**: FR (앞-오른쪽) + RL (뒤-왼쪽) 동시 이동
- 두 페어가 Tt/2 만큼 위상 차이를 두고 교대

### 발 궤적 (Foot Trajectory)

```
높이 (Y축)
 Sh |          ╭───╮
    |        ╭╯     ╰╮
  0 |────────╯         ╰────────
    드래그(지면)         드래그(지면)
    ←──── t1 ────→ ←─t3─→
    startLp          endLp
```

- 지면 단계 (`t1`): 선형 보간으로 전진
- 공중 단계 (`t3`): `Sh * sin(π * progress)` 포물선 궤적으로 복귀

### 키보드 입력 → 보행 파라미터 매핑

```
w/s 키  → IDstepLength (+/-) → Sl (전후 보폭)
a/d 키  → IDstepWidth  (+/-) → Sw (좌우 횡이동)
q/e 키  → IDstepAlpha  (+/-) → Sa (제자리 회전)
space   → 모두 0으로 리셋    → 정지
```

### PyBullet GUI 실시간 슬라이더 목록

| 슬라이더 | 범위 | 기본값 | 설명 |
|----------|------|--------|------|
| `Kp` | 0 ~ 0.05 | 0.045 | 서보 위치 이득 |
| `Kd` | 0 ~ 1 | 0.4 | 서보 속도 이득 |
| `MaxForce` | 0 ~ 50 | 12.5 | 최대 토크 |
| `height` | -40 ~ 90 | 20 | 몸체 높이 |
| `spur front` | 20 ~ 150 | 87 | 앞다리 간격 |
| `spur rear` | 20 ~ 150 | 77 | 뒷다리 간격 |
| `step length` | -150 ~ 150 | 0 | 보폭 |
| `step width` | -150 ~ 150 | 0 | 횡폭 |
| `step height` | 0 ~ 150 | 60 | 발 높이 |
| `step alpha` | -90 ~ 90 | 0 | 회전각 |
| `t0` ~ `t3` | 0 ~ 1000 | 각각 설정 | 보행 타이밍 |
| `front/rear Offset` | 0 ~ 200 | 120/50 | 다리 전후 위치 |

---

## 실행 방법

```bash
# Linux (키보드 입력에 sudo 필요)
sudo python pybullet_automatic_gait.py

# Windows (관리자 권한으로 실행)
python pybullet_automatic_gait.py
```

### 제어

- `w/a/s/d`: 전후좌우 이동
- `q/e`: 좌우 회전
- `space`: 정지 (보행 리셋)
- PyBullet GUI 슬라이더로 보행 파라미터 실시간 조정
