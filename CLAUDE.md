# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

- 답변은 친구 모드
- 답변이 너의 지식인지 웹 검색을 통한 최신 정보인지 표시해줘
- 질문 혹은 요청에 대한 답변에 대한 간략한 소개를 먼저하고 내가 요청하면 자세한 설명을 진행해라 
- 여러가지 케이스에 대해서 일일이 설명하지 마라. 답변이 너무 길면 읽기 힘들다. 
- 어떠한 방법이 있다는 정도 언급해주고 내가 상세한 설명을 요청할 때만 추가로 설명해라
- 영어를 직역해서 설명하지 마라. 이질감 느껴지고 잘 이해가 되지 않는다. 가장 근접한 한국어 표현법으로 설명해줘.
  (e.g. 한 곳만 고쳐도 조용히 갈라집니다 --> 영어 직역이다)
- 토큰 잔 여량이 50%,40%,30%,20%,10%,5%일 때 알려줘
- 물어본 것에만 답한다. 묻지 않은 배경 설명·주의사항·다음 단계 제안·대안 제시는 덧붙이지 않는다. 필요하면 다시 묻는다.
- 명령을 실행하기 전에 무엇을 왜 하는지 먼저 설명한다. 진단용 읽기 명령도 예외 아니다.
- em dash, 화살표, 도 기호를 쓰지 않는다. 각각 하이픈, `->`, `C` 또는 `도`로 대체한다.
- '함정' 이란 단어(ai가 자주 사용함) 사용 자제. 다른 적당한 말로 표현

## 저장소 설명

SpotMicro 4족보행 로봇의 실측 기반 보행 제어와 강화학습. 핵심 문제는 기구
치수가 코드 여러 곳에 흩어져 있으면 결국 서로 어긋난다는 것이고, 이 저장소의
구조·규칙·CI 모두 이걸 막으려는 장치다. 배경과 근거는 [README.md](README.md),
기여 규칙의 이유는 [CONTRIBUTING.md](CONTRIBUTING.md) 에 자세히 있다 — 둘 다
"왜"를 담고 있으니 치수/서보/보상 관련 작업 전에 먼저 확인한다.

## 명령

```bash
uv sync                 # 의존성 설치 (Python 3.12, GPU 불필요)
uv sync --extra robot    # + 실기 제어 (Raspberry Pi 전용, x86 에는 설치 안 됨)

make model               # Kinematics/kinematics.py 상수 -> rl/mjcf/*.xml 재생성
make verify               # model + rl/validate_mjcf.py (8단계 검증, 기하 일치 0.0000mm 요구)
make eval                 # 학습된 정책 재생 (checkpoints/), 실물 이식 가능성 판정
make eval-render          # eval 을 화면으로
make gait-check           # 실물 실측 보행 궤적을 시뮬에 넣어 속도 비교
make gait                 # 규칙 기반 보행을 영상으로 저장
make train                # OMP_NUM_THREADS=1, CPU 로 직접 학습 (수 시간)
make clean                # __pycache__ 제거
```

단위 테스트 스위트는 없다. 정확성 게이트는 `rl/validate_mjcf.py` (8단계 검증)이며
CI([.github/workflows/validate.yml](.github/workflows/validate.yml))가 매 push/PR 마다
이것과 "커밋된 rl/mjcf/ 가 상수에서 생성한 것과 일치하는가", GPL-2.0-only 의존성
혼입 여부를 확인한다.

기구 상수(`Kinematics/kinematics.py`)를 고쳤다면 반드시 `make model` 후
`make verify` 를 8/8 통과시킨다 — CI 도 같은 것을 강제한다.

## 아키텍처 — 단일 출처 원칙

상속받은 upstream 코드는 같은 로봇의 기구 치수를 URDF, 발끝 목표 계산, 역기구학
세 곳에 따로 박아뒀다(수치는 README.md 참조). 그래서 시뮬레이터가 그리는 로봇과
관절 각도를 계산하는 로봇이 서로 달랐다. 이 저장소는 시뮬레이션 모델을 URDF 에서
변환하지 않고 실측 상수에서 바로 만들어서 이 문제 자체를 없앤다:

```
Kinematics/kinematics.py       실측 기구 상수 (링크 길이 l1~l4, L, W) — 유일한 정본
        │
        ├──→ 역기구학 (RaspberryPi/ 의 실물 제어가 사용)
        └──→ rl/gen_mjcf.py ──→ rl/mjcf/*.xml   (생성물 — 손으로 고치지 않는다)
                                        │
                            rl/validate_mjcf.py 가 8개 게이트로 순기구학 대조 등을 검증
```

값별 정본과 "직접 고치면 안 되는 곳"은 다음과 같다 (CONTRIBUTING.md 표):

| 값 | 정본 | 직접 고치면 안 되는 곳 |
|---|---|---|
| 링크 길이 `l1 l2 l3 l4 L W` | `Kinematics/kinematics.py` | `rl/mjcf/*.xml`, `urdf/` |
| 서보 영점·방향 | `Common/servo_map.py` | 제어 코드 안의 상수 |
| 보행 파라미터 | `Common/gait_params.py` | |
| 학습 전용 값 (보상 가중치 등, 실물 대응물 없음) | `rl/envs/config.py` | |

`rl/model_api.py` 는 학습 코드(`rl/envs/`, `rl/eval.py`)가 필요로 하는 것 —
관절 순서(`JOINT_ORDER`), 기립 자세, 가동 범위, theta<->서보 각도 변환 — 을
이 정본들로부터 계산해서 넘겨준다. 학습 코드가 기구 상수·서보 오프셋·관절
순서를 따로 베껴 쓰면 반드시 어긋나므로, 필요한 값이 여기 없으면 이 파일에
추가하고 가져다 쓴다.

행동(action) 공간은 토크가 아니라 관절 각도 변위다 — 실물이 PCA9685 로 구동되는
위치제어 서보이기 때문이며, 그래서 학습 결과를 변환 없이 실물 제어 루프에 넣을 수
있다.

## 디렉터리

```
rl/                강화학습. gen_mjcf.py(모델 생성) -> mjcf/(생성물) -> envs/, train.py, eval.py
Common/            로봇 런타임 정본: servo_map.py(서보 오프셋/부호), gait_params.py, web_control.py(폰 웹 조작 UI)
Kinematics/        역기구학 + 기구 상수 정본(kinematics.py)
RaspberryPi/       서보 제어·PCA9685·캘리브레이션. 실물(Raspberry Pi 4B)에서만 실행
checkpoints/       학습된 정책 가중치 — 최종 결과 하나만 커밋 (README.md 에 판정 포함)
Simulation/        PyBullet, 초기 검증용 (상속, 현재 학습 경로는 rl/mjcf 사용)
urdf/, Parts/      초기 URDF 와 그것이 참조하는 3D 파트 (Jetson Nano 판) — 학습에는 미사용
STL/files/         본 팀이 실제로 출력한 3D 파트 (KDY0523 원본 판, Raspberry Pi 4B 용)
tools/             ik_urdf_mismatch.py(치수 불일치 재현) 등 1회성 분석/생성 스크립트
study/             개발 일지 (11주 기록, 실패 과정 포함)
```

`Parts/` 와 `STL/files/` 는 서로 다른 3D 파트 두 벌이며 이름이 대응해도 다르다
(`Parts/lfoot` = `STL/files/L_wrist`, `lfoot` 은 발이 아니라 하퇴 전체). 어느 쪽을
참조하는지 헷갈리면 README.md "저장소 구조" 절의 표를 확인한다.

`Images/` 의 데모 미디어는 upstream(Road-Balance) 것이고, 본 팀이 촬영한 것은
`docs/media/` 에 있다 — 구분해서 인용한다.

## 라이선스

소프트웨어는 GPL-3.0-or-later, 3D 모델(`STL/`, `STEP_Files/`, `Parts/`)은
CC BY 3.0 (원저작자 KDY0523)로 서로 다르다. 두 트리를 섞어 재배포하는 코드를
작성할 때는 [NOTICE](NOTICE) 3~4장을 확인한다. 의존성을 추가할 때 GPL-2.0-only
라이선스는 GPL-3.0 과 비호환이며 CI 가 이를 검사한다(예: `stable-baselines3[extra]`
가 끌고 오는 `ale-py`).

## 개발/배포 워크플로우

원본은 로컬(이 저장소)에서만 수정한다. Pi에서 직접 git을 다루지 않는다 — 두
군데서 하면 혼동이 온다는 이유로 이렇게 정했다.

1. 로컬에서 수정
2. 로컬 -> Pi로 복사해서 실기 테스트 (git pull 이 아니라 파일 복사)
3. 테스트 성공 = 로컬 코드가 검증된 것 -> 그제서야 로컬에서 커밋/푸시

Pi 접속 정보: `minodori@RPi-CM4`, 저장소 경로
`~/Projects/SpotMicroJetson`, 비밀번호 없이 SSH 접속 가능. 실행은
`uv run python RaspberryPi/start_automatic_gait.py`.

로봇 전원 인가 시 자동 실행은 `RaspberryPi/spotmicro-gait.service`
(systemd, Pi의 `/etc/systemd/system/`에 설치)가 담당한다. 서보 켜짐/꺼짐은
폰 웹 UI(`Common/web_control.py`, 8080)의 토글로 하고, 이건 프로세스를
죽이지 않는다 — `Common/multiprocess_kb.py`의 `ServoActive` 플래그만
바꾼다. 프로세스 자체를 끝내야 할 때(코드 업데이트 등)만 SSH로
`sudo systemctl stop spotmicro-gait`.

## 커밋 메시지

diff 는 무엇을 바꿨는지 말해준다. 커밋 메시지에는 **왜** 바꿨는지를 적는다.
특히 기구 상수(`Kinematics/kinematics.py` 등)를 바꿀 때는 무엇으로 어떻게 쟀는지,
다른 후보값이 있었다면 왜 그것을 택하지 않았는지 근거를 남긴다.
