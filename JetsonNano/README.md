# JetsonNano/ — 여기에는 더 이상 코드가 없습니다

로봇 코드는 **[`../RaspberryPi/`](../RaspberryPi/)** 로 옮겼습니다.

## 왜 이름이 남아 있었나

이 저장소는 Jetson Nano 를 대상으로 하던 시절의 이름을 물려받았습니다.
실제 대상 보드는 **Raspberry Pi Compute Module 4 8GB** 입니다. Jetson Nano →
Raspberry Pi 5 → CM4 로 두 번 옮겼고([work05](../study/minho/work05.md),
[work07](../study/minho/work07.md), [work11](../study/minho/work11.md)),
폴더 이름만 따라오지 못했습니다.

처음 클론한 사람이 `JetsonNano/` 를 보고 Jetson 용 코드라고 읽는 것이 문제였습니다.
이름이 사실과 다르면 그것 자체가 결함입니다.

## 무엇이 어디로

| 파일 | 어디로 |
|---|---|
| `start_automatic_gait.py` | `../RaspberryPi/` — 보행 진입점 |
| `servo_controller.py` | `../RaspberryPi/` — PCA9685 12채널 |
| `spotmicroai.py` | `../RaspberryPi/` — 로봇용. PyBullet 을 걷어낸 판이라 `Simulation/` 의 동명 파일과 다릅니다 |
| `rc.local` | `../RaspberryPi/` |
| `examples/` | `../RaspberryPi/examples/` — `servo_check.py` 등 캘리브레이션 도구 |

## 무엇을 지웠는가

지운 이유를 적어 둡니다. 이 저장소는 이력이 squash 되어 있어 `git log` 로
되짚을 수 없습니다.

| 지운 것 | 이유 |
|---|---|
| `servo_controller_fix.py`<br>`servo_controller_modify.py`<br>`servo_controller_modify2.py` | 2026-07-26 업스트림 변형본. 어디서도 import 하지 않습니다. 실제로 도는 것은 `RaspberryPi/servo_controller.py` 하나입니다 |
| `multiprocess_kb.py` | 죽은 사본. 보행 진입점은 `Common/multiprocess_kb.py` 를 import 합니다 (`Simulation/` 도 같은 것을 씁니다) |
| `motor_test.py` | 참조하는 곳 없음 |
| `requirements.txt` | `numpy==1.13.3` 등 Jetson 시절 고정값. CM4 는 Python 3.12 를 씁니다 |
| `fonts/` (8.9MB) | Jetson 시절 OLED 표시용. 지금 코드가 쓰지 않습니다 |
| `legacy/` | Jetson 부팅·모드·OLED·MPU6050 코드. import 하는 곳 없음 |

## 업스트림

원본은 [FlorianWilk/SpotMicroAI](https://github.com/FlorianWilk/SpotMicroAI) 이고
**2020-04-04 이후 갱신이 멈췄습니다.** 기구 설계 원작은 김덕연(KDY0523),
그 사이 계보는 [`NOTICE`](../NOTICE) 2 장에 있습니다.
