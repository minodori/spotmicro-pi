# SpotMicro Week 07 — Jetson Nano → Raspberry Pi 5 마이그레이션 (실전: OS 설치)

> 작성일: 2026-07-26

---

## 1. 준비물

- Raspberry Pi 5
- 128GB NVMe SSD + M.2 HAT (내장 PCIe 슬롯 장착용)
- 외장형 NVMe 케이스 (PC에서 이미지 플래싱 전용, 굽고 나서는 M.2 HAT로 옮겨 장착)

---

## 2. OS 선택 — Ubuntu Server 24.04 LTS (64-bit)

work05.md에서는 "Raspberry Pi OS"를 다음 단계로 잡았었지만, 실제로는 **Ubuntu Server 24.04 LTS (64-bit)**로 결정했다.

**Desktop이 아닌 Server를 선택한 이유**
- 서보 제어는 SSH로 접속해 Python 스크립트를 실행하는 헤드리스 운영 → GUI 불필요
- Desktop 환경(GNOME 등)이 상시 점유하는 RAM/CPU가 정책 추론(policy.pt, 50Hz 루프) 타이밍에 불필요한 부담
- 카메라/라이다 프리뷰, RViz 시각화 모두 work05.md에서 "현재 실물 배선과 무관 / 실제 ROS 노드 없음"으로 정리된 상태라 GUI를 RPi에서 쓸 이유가 없음

---

## 3. 외장 케이스로 플래싱 시 주의점: 부팅 순서 vs PCIe 링크 속도

외장 NVMe 케이스로 PC에 연결해 이미지를 굽는 경우, 두 설정의 적용 가능 여부가 다르다.

| 설정 | 외장 케이스(PC 연결) 상태에서 가능? | 이유 |
|------|-----------------------------------|------|
| PCIe 링크 속도 (`dtparam=pciex1_gen=3`) | ✅ 가능 | `/boot/firmware/config.txt`는 그냥 텍스트 파일이라 SSD가 어디 연결돼있든 미리 수정 가능 |
| 부팅 순서 (`BOOT_ORDER`) | ❌ 불가능 | RPi 5 보드에 내장된 SPI EEPROM에 저장되는 값이라, 실제 RPi 5 하드웨어에서만 설정 가능 |

→ PCIe 속도 설정은 굽는 시점에 미리 해둘 수 있지만, 부팅 순서는 SSD를 RPi 5에 연결한 뒤 `rpi-eeprom-config`로 확인/수정해야 한다.

**단, PCIe 속도 설정이 의미 있으려면 SSD가 내장 M.2 HAT(PCIe 슬롯)에 꽂혀야 한다.** 외장 케이스를 USB로 계속 사용할 계획이면 USB-attached storage(UASP)로 잡혀서 PCIe 설정 자체가 무의미해진다. (이번 작업은 굽는 용도로만 외장 케이스를 쓰고, 이후 M.2 HAT에 내장하는 방식으로 진행)

---

## 4. 부팅 순서 확인

```bash
lsblk
# root(/)가 nvme0n1pX 로 잡히면 NVMe 부팅 성공

sudo rpi-eeprom-config
# BOOT_ORDER=0xf461
```

`BOOT_ORDER=0xf461`은 SD → NVMe → USB 순으로 시도하도록 설정돼 있었다. SD카드가 아예 꽂혀있지 않은 상태였기 때문에 곧바로 NVMe로 부팅에 성공했다.

**주의할 시나리오:** 나중에 OS가 담긴 SD카드를 실수로 꽂아두면 순서상 SD가 먼저라 그쪽으로 부팅될 수 있다. NVMe를 무조건 최우선으로 고정하려면:
```bash
sudo rpi-eeprom-config --edit
# BOOT_ORDER 값 재배치
```
지금은 SD를 쓸 계획이 없어 현재 설정 그대로 두기로 함.

---

## 5. PCIe Gen3 실험 — 적용했으나 Gen2로 원복

### 5.1 Gen3 적용

```
# /boot/firmware/config.txt
[all]
dtparam=pciex1_gen=3
```
재부팅 후 실제 협상된 링크 속도 확인:
```bash
sudo lspci -vv | grep -A3 -i "LnkSta:"
```
```
LnkSta: Speed 8GT/s, Width x1        ← NVMe 링크, Gen3로 상향 확인
LnkSta: Speed 5GT/s, Width x4        ← RP1 사우스브릿지(USB/이더넷), Gen2 x4 고정, 설정과 무관
```

### 5.2 실측 — 속도 차이 없음

| 상태 | `hdparm -Tt` buffered disk reads |
|------|-----------------------------------|
| Gen2 (기본) | 430.62 → 735.40 MB/sec (측정 변동) |
| Gen3 (적용 후) | 736.38 MB/sec |

Gen3로 링크를 올려도 실측 속도는 Gen2 최고치와 사실상 동일 → **병목이 PCIe 링크가 아니라 SSD 자체의 순차읽기 한계(또는 hdparm의 싱글스레드 측정 한계)** 였던 것으로 판단.

### 5.3 결론 — Gen2로 원복

RPi 5의 외장 PCIe 커넥터(M.2 HAT용) Gen3 동작은 **공식 지원 대상이 아님** (신호 무결성 문제로 데이터 커럽션 위험 가능). 실측 이득이 없는 상황에서 위험을 감수할 이유가 없어 Gen2로 되돌림.

```bash
# /boot/firmware/config.txt 에서 dtparam=pciex1_gen=3 삭제 후 재부팅
```

---

## 6. Migration 전 필수 설치 체크리스트

```bash
# 시스템 기본
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y i2c-tools python3-venv python3-pip git build-essential

# I2C 확인 (config.txt에 dtparam=i2c_arm=on 은 기본 포함되어 있음)
ls /dev/i2c-*        # /dev/i2c-1 확인

# 레포 클론 (브랜치 지정 필수)
git clone -b minho https://github.com/minodori/SpotMicroJetson.git ~/SpotMicroJetson
cd ~/SpotMicroJetson

# 가상환경은 레포 폴더 안에 생성 (.gitignore에 .venv/ 이미 등록되어 있음)
python3 -m venv .venv
source .venv/bin/activate

pip install numpy adafruit-blinka adafruit-circuitpython-servokit psutil keyboard
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

**`JetsonNano/requirements.txt`를 그대로 쓰지 않는 이유:** `numpy==1.13.3`, `Adafruit-PCA9685==1.0.1` 등 2018년 Jetson Python 환경 기준 고정 버전이라 Python 3.12(Ubuntu 24.04 기본) 환경에서 빌드 실패 가능성이 높음. `Adafruit-SSD1306`은 work05.md에서 확인된 죽은 코드 의존성이라 설치 불필요.

> **정정 (2026-08-15)**: 초기 작성 시 `keyboard`도 죽은 의존성으로 분류했으나, 실제로는 [Common/multiprocess_kb.py:68](../../Common/multiprocess_kb.py#L68)의 `keyboard.is_pressed()`가 보행 제어의 키 입력을 담당하는 **활성 의존성**이다. 보행 테스트(`start_automatic_gait.py`)에 반드시 필요.
>
> 다만 Linux에서 `keyboard` 패키지는 `/dev/input` 접근 때문에 **root 권한이 필요**하다 (import 시점에 실패). 따라서 보행 스크립트는 sudo로 실행해야 하며, venv를 쓰는 경우 venv의 python을 절대경로로 지정해야 한다:
> ```bash
> sudo ~/SpotMicroJetson/.venv/bin/python start_automatic_gait.py
> ```
> `getch`는 활성 코드에서 사용처가 없어 여전히 불필요.

---

## 7. 다음 단계

- [ ] PCA9685 배선 후 `i2cdetect -y 1`로 `0x40`, `0x41` 응답 확인
- [ ] `servo_controller.py`의 `board.SCL_1` → `board.SCL` 수정 (work05.md 4.2절)
- [ ] `JetsonNano/examples/test_servos_cali.py`로 서보 개별 동작 테스트 (work06.md 조립 절차와 연계)
- [ ] MPU6050 연결 및 데이터 확인
- [ ] 보행 알고리즘 실행 테스트
