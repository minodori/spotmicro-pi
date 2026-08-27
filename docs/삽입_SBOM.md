# 붙임1 SBOM — 복사용 (확인된 버전)

> **가안의 붙임1 표를 통째로 이것으로 바꾸십시오.** 지금 들어 있는 값은 여덟 개 중
> 다섯이 틀렸고 `matplotlib` 이 빠져 있습니다.
>
> CTO 가 커밋 `2517c0c` 로 `pyproject.toml` 과 `uv.lock` 을 만들었습니다. 아래는
> 그 락파일에서 직접 읽은 값입니다.

본 프로젝트가 직접 선언한 의존성입니다. 전이 의존성을 포함한 전체 목록(220개)은
저장소의 `uv.lock` 이 정본이며 `uv export --no-hashes` 로 언제든 다시 만들 수 있습니다.

| 번호 | 라이브러리명 | 버전 | 라이선스 | 공식 저장소 URL | 사용 목적 및 주요 기능 |
|---|---|---|---|---|---|
| 1 | mujoco | 3.11.0 | Apache-2.0 | https://github.com/google-deepmind/mujoco | 물리 시뮬레이션. 실측 상수에서 생성한 MJCF 모델을 구동하고 검증 항목을 실행 |
| 2 | stable-baselines3 | 2.9.0 | MIT | https://github.com/DLR-RM/stable-baselines3 | PPO 강화학습. 보행 정책 학습과 평가 |
| 3 | gymnasium | 1.3.0 | MIT | https://github.com/Farama-Foundation/Gymnasium | 강화학습 환경 인터페이스 |
| 4 | torch | 2.13.0+cpu | BSD-3-Clause 외 | https://github.com/pytorch/pytorch | 정책 신경망. CPU 빌드로 고정해 GPU 를 요구하지 않는다 |
| 5 | numpy | 2.5.2 | BSD-3-Clause 외 | https://github.com/numpy/numpy | 수치 연산. 기구학과 관측·보상 계산 |
| 6 | tensorboard | 2.21.0 | Apache-2.0 | https://github.com/tensorflow/tensorboard | 학습 로그 기록 |
| 7 | matplotlib | 3.11.1 | PSF 계열 (matplotlib License) | https://github.com/matplotlib/matplotlib | 기구학 시각화. `Kinematics/kinematics.py` 가 그릴 때만 불러온다 |
| 8 | imageio | 2.37.4 | BSD-2-Clause | https://github.com/imageio/imageio | 시뮬레이션 렌더링 영상 저장 |
| 9 | imageio-ffmpeg | 0.6.0 | BSD-2-Clause | https://github.com/imageio/imageio-ffmpeg | mp4 인코딩 |
| 10 | adafruit-circuitpython-servokit | 1.3.24 | MIT | https://github.com/adafruit/Adafruit_CircuitPython_ServoKit | 서보 12개 각도 명령 (로봇에서만) |
| 11 | adafruit-circuitpython-pca9685 | 3.4.22 | MIT | https://github.com/adafruit/Adafruit_CircuitPython_PCA9685 | PCA9685 ×2 PWM 드라이버 제어 (로봇에서만) |
| 12 | keyboard | 0.13.5 | MIT | https://github.com/boppreh/keyboard | 실물 보행 키보드 조작 (로봇에서만) |
| 13 | psutil | 7.2.2 | BSD-3-Clause | https://github.com/giampaolo/psutil | 로봇 구동 중 자원 사용량 확인 (로봇에서만) |

10번부터 13번은 라즈베리파이에서만 설치됩니다(`uv sync --extra robot`). 노트북에서는
필요하지 않고 설치되지도 않습니다.

전부 OSI 인증 허용적 라이선스이며 본 저장소의 GPL-3.0-or-later 와 호환됩니다.

라이선스 충돌을 한 건 실제로 제거했습니다. `stable-baselines3` 의 `[extra]` 옵션은
`ale-py` 를 함께 설치하는데 그 라이선스가 GPL-2.0-only 이고 GPL-3.0 과 호환되지
않습니다. 강화학습 코드 어디서도 쓰지 않으므로 `[extra]` 를 떼고 실제로 필요한
`tensorboard` 만 따로 명시했습니다. 락파일에 `ale-py` 가 없습니다.

`torch` 는 CPU 빌드로 고정했습니다. 기본 설치는 CUDA 빌드를 주며 그 경우 `nvidia` 로
시작하는 패키지 15개가 함께 잠깁니다. 본 프로젝트는 GPU 를 요구하지 않으므로 자재
명세서에도 CUDA 스택이 없어야 합니다. 고정 후 가상환경이 5.2GB 에서 1.1GB 로
줄었습니다.

---

# 참고 — 무엇이 바뀌었나

| 라이브러리 | 가안에 적힌 값 | 확인된 값 |
|---|---|---|
| mujoco | 3.4.0 | **3.11.0** |
| stable-baselines3 | 2.7.1 | **2.9.0** |
| gymnasium | 1.2.3 | **1.3.0** |
| numpy | 2.4.1 | **2.5.2** |
| tensorboard | 2.20.0 | **2.21.0** |
| matplotlib | 표에 없음 | **3.11.1 추가** |
| 전체 패키지 수 | 223개 | **220개** |

torch·imageio·imageio-ffmpeg·psutil 과 로봇용 4종은 원래 값이 맞았습니다.
