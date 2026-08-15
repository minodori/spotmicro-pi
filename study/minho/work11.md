# SpotMicro Week 11 — RPi 5 고장 & Compute Module 4 전환

> 작성일: 2026-08-15

---

## 1. 배경

work07.md에서 RPi 5 + NVMe 부팅까지 완료하고 work08~10.md로 전원·핀맵·플레이트 작업을 이어가던 중, **조립 과정에서 RPi 5가 부팅 불능 상태**가 되었다. 대체 보드로 보유 중이던 **Compute Module 4 8GB**로 전환했고, 그 과정에서 RPi 5와 다른 함정이 여러 개 나왔다.

관련 문서: [work05.md](work05.md) 마이그레이션 비교 · [work07.md](work07.md) RPi 5 OS 설치 · [work08.md](work08.md) 전원 설계 · [work09.md](work09.md) 채널 핀맵

---

## 2. RPi 5 고장 증상

| 항목 | 내용 |
|------|------|
| 증상 | 빨간 LED만 점등, 초록 LED 미점등 → 부팅 시퀀스 진입 실패 |
| 리커버리 이미지 | 시도했으나 동일 (변화 없음) |
| 발생 시점 | 로봇 조립 작업 중 |

### 2.1 주의 — work08.md의 전원 문제와 증상이 동일하다

[work08.md §2.1](work08.md)에 기록된 벅 컨버터 소프트 스타트 문제가 **정확히 같은 증상**(빨간불 O, 초록불 X)을 낸다. 부트로더 자체가 시작을 못 하면 부팅 매체가 무엇이든 무관하므로, 리커버리 이미지가 안 먹히는 것도 전원 문제로 설명된다.

따라서 하드웨어 사망으로 단정하려면 아래 조건에서 재현되어야 한다.

- 공식 5V/5A USB-C PD 어댑터 (로봇 전원 계통 완전 분리)
- NVMe / M.2 HAT / PCA9685 배선 / USB 전부 탈거
- 보드 단독 + 전원만

> **이번에는 이 격리 테스트를 하지 않고 CM4로 전환했다.** RPi 5가 실제로 죽었는지는 미확정 상태다. 추후 시간이 나면 위 조건으로 재확인할 것.

### 2.2 조립 중 손상 가능 경로

- 서보 7.4V가 GPIO 핀에 접촉 (3.3V 핀에 7.4V 인가 시 SoC 즉시 손상)
- PCA9685의 V+ 와 VCC 혼동 배선
- 금속 프레임에 보드 뒷면 접촉으로 인한 쇼트
- 전원 인가 상태에서 M.2 HAT FFC 케이블 착탈

---

## 3. CM4 환경 실측

SSH(`192.168.0.240`)로 접속해 확인한 값이다.

| 항목 | 값 |
|------|-----|
| 보드 | Raspberry Pi Compute Module 4 Rev 1.1 |
| RAM | 8GB (7.6Gi 인식) |
| 스토리지 | **eMMC 32GB** (`mmcblk0`) — Lite 아님, SD 불필요 |
| OS | Ubuntu 24.04.4 LTS |
| 커널 | 6.8.0-1060-raspi (aarch64) |
| ROS2 | Jazzy (기설치) |
| Python | 3.12.3 |
| 온도 | 42.4°C (idle) |
| 저전압 이력 | **0 (없음)** |

### 3.1 IO 보드 & 전원

- IO 보드: RPi 5와 동일한 외형·포트 구성의 서드파티 캐리어. **전원 입력은 USB-C 뿐** (12V 배럴잭 없음)
- 현재 급전: `LiPo 11.1V → UBEC 5V/5A → GPIO 헤더 4번 핀`

work08.md의 전원 아키텍처(UBEC 5V = 로직, 300W 벅 7.4V = 서보, GND 공통)는 **그대로 유효**하다.

**CM4가 RPi 5보다 유리한 점**: 소비전력이 낮고(대략 5W vs 8W), BCM2711은 RPi 5의 PMIC(DA9091)처럼 까다로운 300ms 내 4.75V 안정화를 요구하지 않는다. work08.md에서 겪은 부팅 실패 문제가 재발할 여지가 작다.

> **USB-C 급전 관련**: UBEC은 PD 컨트롤러가 없는 단순 레귤레이터라 전압 협상 자체가 일어나지 않는다. VBUS에 5V가 그대로 실릴 뿐이므로 "다른 전압으로 협상될" 위험은 없다. 다만 CC 저항 유무가 케이블/보드마다 달라 안 켜질 수 있어, 현재는 GPIO 5V 급전을 유지 중이다.
>
> GPIO 5V 핀은 보드의 입력 보호 회로를 우회하므로, 대신 **UBEC 출력에 인라인 퓨즈(3~5A)** 와 **CM4 근처 벌크 커패시터(470~1000µF)** 를 두는 편이 실질적인 보호가 된다.

### 3.2 비상 정지 설계

전체 전원을 끊으면 CM4가 강제 종료되어 eMMC 파일시스템 손상 위험이 있다. **E-stop은 서보 V+ 라인에만 거는 것이 옳다.**

```
LiPo 11.1V ─┬─ UBEC 5V ────────→ CM4              (항상 유지)
            └─ 300W Buck 7.4V ─→ [E-stop] → PCA9685 V+  (차단 대상)
```

구동계만 끊고 연산부는 살리는 것이 로봇공학의 표준 관행이다. 서보가 풀려도 로봇을 공중에 매달아 둔 상태면 안전하다.

---

## 4. CM4 전환 시 걸린 함정 4가지

RPi 5에서는 없던 문제들이라 별도로 기록한다.

### 4.1 Blinka가 `RPi.GPIO`를 추가로 요구

CM4는 BCM2711이라 Blinka가 `raspi_4b` 보드 모듈로 인식하고, 이 경로는 `RPi.GPIO`에 의존한다. RPi 5(BCM2712)에는 없던 의존성이다.

```
ModuleNotFoundError: No module named 'RPi'
RuntimeError: The platform library 'RPi' was not found.
```

```bash
pip install RPi.GPIO
```

설치 후 정상 인식:
```
chip: BCM2XXX
board: RASPBERRY_PI_CM4
SCL: 3    SDA: 2      ← work05.md 핀맵과 동일, 코드 수정 불필요
```

### 4.2 `i2c-tools` 설치가 udev 그룹을 덮어쓴다

Ubuntu 기본 규칙 `/lib/udev/rules.d/60-gpio.rules`는 `/dev/i2c-*` 를 `dialout` 그룹으로 두지만, `i2c-tools` 패키지가 설치하는 `60-i2c-tools.rules`가 파일명 순서상 나중에 적용되어 그룹을 `i2c`로 바꾼다.

```
설치 전: crw-rw---- root dialout /dev/i2c-1
설치 후: crw-rw---- root i2c     /dev/i2c-1
```

→ `dialout`만 추가하면 `Permission denied`. **두 그룹 모두 추가**해야 한다.

```bash
sudo usermod -aG dialout,i2c $USER
```

### 4.3 그룹 추가는 재로그인해야 적용된다

리눅스 그룹 멤버십은 로그인 시점에 고정된다. `usermod` 이전에 열어둔 SSH 세션에서는 계속 `Permission denied`가 난다.

```bash
exit && ssh ...        # 재로그인
# 또는
newgrp i2c             # 새 셸이 뜨므로 venv 재활성화 필요
```

### 4.4 `input()`에서 방향키가 안 먹는다

대화형 스크립트에서 오타 수정이 안 되고 `^[[D` 같은 이스케이프 시퀀스가 그대로 찍힌다. `readline` 모듈을 import하면 해결된다.

```python
import readline  # noqa: F401  input() 편집 기능 활성화
```

---

## 5. 환경 구축 절차 (실제 수행한 순서)

```bash
# 1. 권한
sudo usermod -aG dialout,i2c minodori     # 이후 재로그인 필수
sudo apt install -y i2c-tools python3-venv

# 2. 레포
git clone -b minho https://github.com/minodori/SpotMicroJetson.git ~/Projects/SpotMicroJetson
cd ~/Projects/SpotMicroJetson

# 3. 가상환경 (.gitignore에 .venv/ 등록되어 있음)
python3 -m venv .venv
.venv/bin/pip install numpy adafruit-blinka adafruit-circuitpython-servokit psutil keyboard
.venv/bin/pip install RPi.GPIO          # CM4 전용 - §4.1
```

### 5.1 검증 결과

```bash
i2cdetect -y 1
```
```
40: 40 41 -- -- ...
70: 70 -- -- -- ...     ← All-Call (정상)
```

ServoKit 초기화까지 성공, 두 보드 모두 PWM 50Hz 설정 확인.

> work08.md에서는 `70: 70 71`로 두 개가 보였으나 이번엔 `70` 하나만 나온다. 0x70은 두 보드 공통 All-Call 주소이고 0x71(SUBADR1)은 기본 비활성이므로 동작상 문제는 없다.

---

## 6. 서보 채널 실측 — 인덱스와 채널 번호 혼동

### 6.1 두 번호 체계

혼동이 실제 배선 오류로 이어졌으므로 명확히 구분해 둔다.

| 구분 | 범위 | 의미 |
|------|------|------|
| **서보 인덱스** | 0~11 | 12개 관절의 논리 번호. `_servo_offsets`, `_val_list`, IK 결과가 공유하는 순서 |
| **보드 채널** | CH0~CH5 | 각 PCA9685의 물리 헤더 번호. 보드가 2개라 각각 0부터 다시 셈 |

둘을 잇는 것이 `servo_controller.py`의 `_channel_map`이다.

```
인덱스 6 (RL-Lower) → 0x41 보드 CH3 → 좌측 보드 앞에서 4번째 헤더
```

**인덱스 6,7,8을 "앞에서 7,8,9번째 헤더"로 오해**해 RL 다리를 CH6~CH8에 연결했던 것이 이번 배선 오류의 원인이었다. 코드는 CH0~CH5만 사용하므로 해당 채널은 전혀 동작하지 않았다.

### 6.2 채널 스캔 결과 (재배선 전)

`servo_check.py scan`으로 12채널을 순차 구동해 실측했다.

| 보드/채널 | 실측 | 기대값 | 판정 |
|-----------|------|--------|------|
| 0x41 CH0~2 | fl-lower / fl-upper / fl-shoulder | FL 3개 | ✅ 일치 |
| 0x41 CH3~5 | — | RL 3개 | 미연결 (CH6~8에 배선) |
| 0x40 CH0~3 | — | FR 3개 + RR-Lower | 미연결 |
| 0x40 CH4 | rr-shoulder | RR-Upper | ⚠️ 뒤바뀜 |
| 0x40 CH5 | rr-upper | RR-Shoulder | ⚠️ 뒤바뀜 |

**결론**: `_channel_map`(work09.md §4의 좌/우 분리)은 옳고, FL 다리가 그 규칙대로 배선되어 있었다. 소프트웨어 remap이 아니라 **배선을 코드 기준에 맞추는 방향**으로 재작업하기로 결정. 7채널이 어차피 비어 있어 물리 교체 부담이 작기 때문이다.

### 6.3 배선 기준표

```
     로봇 앞쪽 ↑                          로봇 앞쪽 ↑
0x41 (배터리 좌측) — 왼쪽 다리        0x40 (배터리 우측, 반전 장착) — 오른쪽 다리
  CH0   FL-Lower                        CH13  FR-Lower
  CH1   FL-Upper                        CH14  FR-Upper
  CH2   FL-Shoulder                     CH15  FR-Shoulder
  CH13  RL-Lower                        CH0   RR-Lower
  CH14  RL-Upper                        CH1   RR-Upper
  CH15  RL-Shoulder                     CH2   RR-Shoulder
  CH3~CH12  비워둠                       CH3~CH12  비워둠
   ↑ CH0 이 앞쪽                          ↑ CH15 가 앞쪽
```

규칙 세 가지:
1. 각 보드는 **자기 쪽 다리 2개**만 담당 (좌측 = FL+RL, 우측 = FR+RR)
2. 다리 하나는 **Lower → Upper → Shoulder** 순
3. **각 다리에 물리적으로 가까운 헤더**를 쓴다. 보드 장착 방향에 따라 어느 블록이 앞다리인지 달라진다

커넥터 방향은 work09.md §7 기준 **PWM(노랑) / V+(빨강) / GND(갈색)**.

### 6.4 CH3~5 → CH13~15 변경, 그리고 우측 보드 반전

최초 계획은 각 보드에서 앞다리 CH0~2, 뒷다리 CH3~5를 쓰는 것이었으나 **실제 배선 시 뒷다리까지 선 길이가 부족**했다. 뒷다리는 보드에서 물리적으로 멀기 때문이다. PCA9685의 16개 채널은 전기적으로 완전히 동일하므로, 보드 끝단(CH13~15)을 써서 배선 여유를 확보했다.

추가로 **우측 PCA9685(0x40)는 좌측과 반대 방향으로 장착**되어 있음을 확인했다. 즉 이 보드는 CH15 쪽이 로봇 앞을 향한다. 따라서 우측 보드만 블록 배정을 뒤집어 **앞다리(FR)에 CH13~15, 뒷다리(RR)에 CH0~2**를 할당했다.

> 배선을 코드에 억지로 맞추지 않고, **배선이 짧아지는 쪽으로 꽂은 뒤 `_channel_map`을 거기에 맞추는** 방식을 택했다. 채널 간 전기적 차이가 없으므로 이쪽이 합리적이다.

### 6.5 재배선 후 전수 검증 (완료)

`servo_check.py scan`으로 12채널 전부 재측정한 결과, **코드의 `_channel_map`과 100% 일치**함을 확인했다.

| 보드/채널 | 실측 관절 | 서보 인덱스 |
|-----------|-----------|:-----------:|
| 0x41 CH0 / CH1 / CH2 | FL Lower / Upper / Shoulder | 0, 1, 2 |
| 0x41 CH13 / CH14 / CH15 | RL Lower / Upper / Shoulder | 6, 7, 8 |
| 0x40 CH13 / CH14 / CH15 | FR Lower / Upper / Shoulder | 3, 4, 5 |
| 0x40 CH0 / CH1 / CH2 | RR Lower / Upper / Shoulder | 9, 10, 11 |

→ 배선 검증 완료. 다음은 오프셋 캘리브레이션 단계.

> ⚠️ **함정**: 기존 코드는 `set_pulse_width_range(500, 2500)`을 `for ch in range(6)`으로만 적용했다. 이대로 CH13~15를 쓰면 뒷다리 서보가 기본값(750~2250µs)으로 남아 **같은 각도를 명령해도 앞다리와 다르게 움직인다.** `_channel_map`에 등록된 채널 전부를 순회하도록 수정했다.
>
> ```python
> for kit_obj, ch in self._channel_map.values():
>     kit_obj.servo[ch].set_pulse_width_range(500, 2500)
> ```

---

## 6.6 오프셋 캘리브레이션 (완료)

`servo_check.py cal` 로 12개 관절을 기준 자세에 맞춰 실측했다.

**기준 자세 = IK 의 `theta=0`**: 어깨관절부터 발끝까지 하나의 수직 직선.

| 관절 | 측정 기준 | 목표 | 눈으로 확인 |
|------|-----------|:----:|-------------|
| Shoulder | 정면도에서 다리 축과 수직선 사이 | 0° | 발끝이 어깨관절 바로 아래 |
| Upper | 측면도에서 대퇴부와 수평면 사이 | 90° | 무릎관절이 엉덩관절 바로 아래 |
| Lower | 대퇴부-하퇴부 내각 | 180° | 발끝이 무릎관절 바로 아래 |

> 이것은 **직립 자세가 아니다.** 실제로 서 있을 때는 IK 가 무릎을 굽힌다 (work06.md §4). 여기서는 각도 0 의 기준점만 잡는다.

### 실측 결과

```python
# 기존 (Jetson 시절 다른 개체)
self._servo_offsets = [170, 85, 90, 1, 95,  90, 172, 90, 90, 1, 90, 95]
# CM4 이식 후 실측
self._servo_offsets = [150, 81, 79, 1, 95, 105, 164, 81, 82, 1, 80, 81]
```

| idx | 관절 | 기존 → 실측 | idx | 관절 | 기존 → 실측 |
|:---:|------|:-----------:|:---:|------|:-----------:|
| 0 | FL-Lower | 170 → **150** | 6 | RL-Lower | 172 → **164** |
| 1 | FL-Upper | 85 → **81** | 7 | RL-Upper | 90 → **81** |
| 2 | FL-Shoulder | 90 → **79** | 8 | RL-Shoulder | 90 → **82** |
| 3 | FR-Lower | 1 → 1 | 9 | RR-Lower | 1 → 1 |
| 4 | FR-Upper | 95 → 95 | 10 | RR-Upper | 90 → **80** |
| 5 | FR-Shoulder | 90 → **105** | 11 | RR-Shoulder | 95 → **81** |

**오프셋은 좌우 대칭일 필요가 없다.** 혼(horn)이 스플라인에 물린 위치는 서보마다 다르고, 오프셋은 그 물리적 장착 상태를 담는 값이다. 해당 각도에서 관절이 기준 자세이면 그 값이 맞다.

**FR-Lower / RR-Lower 가 하한 1° 인 것은 설계상 정상**이다. `angleToServo()` 에서 우측 무릎은 `offset + theta` 로 위쪽으로만 움직인다 (좌측은 `offset - theta` 로 아래쪽). 좌우 무릎이 거울 대칭 장착이라 각각 가동 범위의 반대쪽 끝에서 출발한다.

---

## 6.7 `servoRotate()` 이중 보정 버그 (수정)

캘리브레이션 값을 반영하는 과정에서 발견했다. `servoRotate()` 에 아래 변환이 살아있었다.

```python
self._val_list[x] = (self._val_list[x] - 26.36) * (1980/1500)
```

### 정체

ServoKit 기본 펄스 범위(750~2250µs, 폭 1500)를 실제 서보 범위(460~2440µs, 폭 1980)로 맞추던 보정이다. 역산하면 정확히 일치한다.

```
θ_cmd = -290×180/1500 + θ×(1980/1500) = 1.32θ - 34.8
코드:  (θ - 26.36)×1.32               = 1.32θ - 34.8
```

### 문제

현재 코드는 이미 `set_pulse_width_range(500, 2500)` 으로 범위를 명시하므로 **보정이 이중으로 걸린다.** 그 결과 오프셋 자체가 범위를 벗어난다.

```
FL-Lower offset 170 → (170-26.36)×1.32 = 189.6 → "Over 180!!"  → 179 클램프
FR-Lower offset   1 → (1-26.36)×1.32   = -33.5 → "Under 0!!"   → 1 클램프
```

**자기 기준값조차 재현하지 못하는 상태**였다. `servo_controller_modify.py:102` 와 `modify2.py:114` 에서 같은 줄이 주석 처리되어 있고, `servo_controller_fix.py` 는 `min_pulse=460, max_pulse=2440` 을 직접 지정하는 방식으로 대체한 것도 같은 판단으로 보인다.

→ **변환식 제거.** 이제 캘리브레이션한 raw 각도가 그대로 서보에 전달된다.

### 남은 이슈 — 클램프 시 서보 미구동

```python
if (self._val_list[x] > 180):
    self._val_list[x] = 179
    continue          # 클램프 값을 계산해놓고 서보에 쓰지 않는다
```

`continue` 가 서보 명령을 건너뛰므로, 범위를 벗어난 관절은 179 로 제한되는 것이 아니라 **이전 위치에 멈춘다.** 보행 중이면 다리 하나만 얼어붙는다. 변환식 제거 후에는 클램프가 발동할 일이 거의 없어 일단 현행 유지하고, 실제 보행에서 `Over 180!!` 로그가 나오는지 보고 판단한다.

---

## 7. 검증 도구 `servo_check.py`

배선 확인용으로 작성한 헬퍼. [JetsonNano/examples/servo_check.py](../../JetsonNano/examples/servo_check.py)

```bash
cd ~/Projects/SpotMicroJetson
P=.venv/bin/python

$P JetsonNano/examples/servo_check.py map        # 인덱스 -> 보드/채널 표
$P JetsonNano/examples/servo_check.py 5 sweep    # 인덱스 5를 90+-20도 3회 왕복
$P JetsonNano/examples/servo_check.py 5 90       # 인덱스 5를 90도로
$P JetsonNano/examples/servo_check.py raw 40 15  # 보드/채널 직접 지정
$P JetsonNano/examples/servo_check.py scan       # 12채널 순차 스윕 (실측)
$P JetsonNano/examples/servo_check.py scan 4     # 4번째 채널부터 재개
```

레포 상대 import가 없는 독립 실행형이라 실행 위치와 무관하게 동작한다.

**안전성**: 모든 스윕은 90°에서 시작해 90°로 복귀한다. work06.md의 조립 원칙(서보를 90° 전기적 중립에서 혼 결합)에 따라 90°는 모든 관절에서 가동 범위 한가운데이므로, 무릎의 offset이 170°/1°라도 끝단에 부딪히지 않는다.

---

## 8. 코드 변경 이력 (이번 주)

| 커밋 | 내용 |
|------|------|
| `07016a8` | `_channel_map` 도입 — Front/Rear 분리를 Left/Right 분리로 변경 (배터리 좌우 실장 배치에 맞춤). work09.md 채널표·모터 모델 매핑 정정 |
| `8e8f01c` | `test_servos_cali.py`를 동일 라우팅으로 동기화. `start_automatic_gait.py`의 미사용 `import keyboard` 제거 |

> `keyboard` 패키지 자체는 여전히 필요하다. [Common/multiprocess_kb.py:68](../../Common/multiprocess_kb.py#L68)의 `keyboard.is_pressed()`가 보행 키 입력을 담당한다. Linux에서 이 패키지는 import 시점에 root 권한을 요구하므로 보행 스크립트는 sudo로 실행해야 한다 (work07.md §6 정정 참조).

---

## 9. 다음 단계

- [x] 재배선 완료 후 `servo_check.py scan`으로 12채널 전수 검증 (§6.5)
- [x] `_servo_offsets` 실측 캘리브레이션 (§6.6)
- [x] `servoRotate()` 이중 보정 버그 수정 (§6.7)
- [ ] `servo_controller.py` 단독 실행 → 직립 자세 확인 (**로봇 공중 매단 상태로**)
- [ ] 서보 12개 동시 구동 시 UBEC 5V sag 측정 (`vcgencmd get_throttled` — CM4는 `video` 그룹 필요)
- [ ] `start_automatic_gait.py` 보행 테스트 (sudo 실행)
- [ ] `servo_check.py`를 레포에 편입할지 결정
- [ ] RPi 5 격리 전원 테스트로 실제 고장 여부 확정 (§2.1)
