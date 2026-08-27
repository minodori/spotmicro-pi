# Simulation/ — 상속받은 상태 그대로입니다. 고치지 마십시오

이 디렉터리는 **업스트림에서 받은 PyBullet 시뮬레이션**입니다. 현재 쓰지 않습니다.
지금 쓰는 시뮬레이션은 [`rl/`](../rl/) 의 MuJoCo 모델입니다.

## 여기 숫자는 낡았습니다. 그것을 보여주려고 남깁니다

한 저장소 안에 서로 다른 로봇이 세 벌 들어 있었습니다.

```
urdf/spotmicroai_gen.urdf.xml       L 186  W 72  l1 52  l2 0   l3 120.4  l4 135
Simulation/spotmicroai.py:103-104   L 140  W 120                              발끝 목표 좌표
Simulation/kinematics.py:30-36      L 140  W 75  l1 50  l2 20  l3 100    l4 100
Kinematics/kinematics.py:59-65      L 185  W 78  l1 56  l2 20  l3 110    l4 135   <- 실측
```

PyBullet 이 화면에 띄우고 중력과 충돌을 계산하는 몸은 다리가 120.4+135mm 인데,
그 몸에 넣을 관절 각도를 계산하는 코드는 100+100mm 로 알고 있었습니다. 같은 각도를
넣어도 발이 의도한 자리에 가지 않습니다. 보행 구간 95개 자세에서 재보니 중앙값
18mm, 최대 33mm 어긋났습니다 (`python tools/ik_urdf_mismatch.py` 로 재현).

**한 곳만 고치면 나머지 두 곳은 옛 값 그대로 남습니다.** 에러도 경고도 나지 않아서
6년간 아무도 몰랐고, 이 프로젝트가 몇 주를 잃은 원인이 그것입니다
([work11 §6.25](../study/minho/work11.md), [README](../README.md)).

그래서 이 디렉터리를 **증거로 남깁니다.** 숫자를 맞추면 우리가 쓴 것처럼 보이고,
지우면 무엇이 문제였는지 보이지 않습니다.

## 지금 코드는 어떻게 하고 있는가

`rl/gen_mjcf.py` 가 `Kinematics/kinematics.py` 의 상수를 import 해서 MuJoCo 모델을
생성합니다. 사람이 옮겨 적는 단계가 없으므로 어긋날 수가 없습니다.
`rl/validate_mjcf.py` 의 순기구학 대조 항목이 시뮬 발끝과 역기구학 발끝을 매번
확인하고, CI 가 커밋된 모델이 상수에서 생성한 것과 같은지 봅니다.

## 파일

| | |
|---|---|
| `kinematics.py`, `kinematicMotion.py` | `Kinematics/` 의 낡은 사본. `kinematicMotion.py` 는 PyBullet 의존이 섞여 있어 단순 중복은 아닙니다 |
| `spotmicroai.py` | PyBullet 로봇 래퍼. `RaspberryPi/` 의 동명 파일은 PyBullet 을 걷어낸 별개 판입니다 |
| `pybullet_automatic_gait.py` | 실행 진입점 |
| `gym_spotmicroai/` | gym 환경 골격. `step()` 이 `stepSimulation()` 만 부르고 관측·행동 공간이 없어 학습에 쓸 수 없습니다 |

## 물리도 실물과 다릅니다

기하만 어긋난 것이 아닙니다. `spotmicroai.py:179` 가 모든 링크의 관성을
`1e-6` 으로 덮어씁니다. 우리 모델 중앙값의 약 1/100 입니다. 모터 힘은 12.5 N·m 로
DS3235 의 6V 스톨 3.14 N·m 의 4배이고, URDF 총 질량은 5.30 kg 으로 실측 2.20 kg 의
2.4배입니다.

그 조건에서는 대부분의 궤적이 걷습니다. **여기서 실물로 넘어가는 것은 궤적뿐이고
동역학은 넘어가지 않습니다.**
