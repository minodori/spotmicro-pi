# Simulation/ — 상속받은 상태 그대로입니다. 고치지 마십시오

이 디렉터리는 **업스트림에서 받은 PyBullet 시뮬레이션**입니다. 현재 쓰지 않습니다.
지금 쓰는 시뮬레이션은 [`rl/`](../rl/) 의 MuJoCo 모델입니다.

## 여기 숫자는 낡았습니다 — 그게 요지입니다

```
Simulation/kinematics.py:27-33     l1=50  l3=100  l4=100  L=140  W=75
Simulation/spotmicroai.py:100-101  L=140  W=75+5+40
Kinematics/kinematics.py           l1=56  l3=110  l4=135  L=185  W=78   <- 실측
```

**같은 상수가 저장소 안에 여러 벌 있었고, 한 곳만 고치면 나머지가 조용히
어긋났습니다.** 이 프로젝트가 몇 주를 잃은 원인이 그것입니다
([work11 §6.25](../study/minho/work11.md), [README](../README.md)).

그래서 이 디렉터리를 **증거로 남깁니다.** 숫자를 맞추면 우리가 쓴 것처럼 보이고,
지우면 무엇이 문제였는지 보이지 않습니다.

## 지금 코드는 어떻게 하고 있는가

`rl/gen_mjcf.py` 가 `Kinematics/kinematics.py` 의 상수를 import 해서 MuJoCo
모델을 생성합니다. 사람이 옮겨 적는 단계가 없으므로 어긋날 수가 없습니다.
`rl/validate_mjcf.py` 게이트 3 이 시뮬 발끝과 역기구학 발끝을 매번 대조하고,
CI 가 커밋된 모델이 상수에서 생성한 것과 같은지 확인합니다.

## 파일

| | |
|---|---|
| `kinematics.py`, `kinematicMotion.py` | `Kinematics/` 의 낡은 사본. `kinematicMotion.py` 는 PyBullet 의존이 섞여 있어 단순 중복은 아닙니다 |
| `spotmicroai.py` | PyBullet 로봇 래퍼. `JetsonNano/`(현 `RaspberryPi/`) 의 동명 파일은 PyBullet 을 걷어낸 별개 판입니다 |
| `pybullet_automatic_gait.py` | 실행 진입점 |
| `gym_spotmicroai/` | gym 환경 골격. `step()` 이 `stepSimulation()` 만 부르고 관측·행동 공간이 없어 학습에 쓸 수 없습니다 |
