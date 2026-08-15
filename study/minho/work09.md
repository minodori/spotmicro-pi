# SpotMicro Week 09 — PCA9685 & 서보 모터 핀맵 정리

> 작성일: 2026-08-11

---

## 1. 목적

work08.md에서 정리한 PCA9685 데이지 체인 구성 이후, 실제 코드에서 어떤 서보 인덱스가 어느 PCA9685 보드의 몇 번 채널에 연결되어 있는지 명확히 정리한다. 조립·디버깅 시 배선 오류를 빠르게 잡기 위한 참조표.

관련 파일:
- [JetsonNano/servo_controller.py](../../JetsonNano/servo_controller.py) — 실제 제어 코드
- [JetsonNano/examples/test_servos_cali.py](../../JetsonNano/examples/test_servos_cali.py) — 채널별 캘리브레이션 테스트
- [study/minho/work08.md](work08.md) — 전원 & I2C 배선 변경 기록

---

## 2. 전체 시스템 구성

```
RPi 5
 ├─ 3.3V ─┐
 ├─ GND  ─┤
 ├─ SDA  ─┤──→ PCA9685 #1 (0x40) ──→ PCA9685 #2 (0x41)   [I2C 데이지 체인]
 └─ SCL  ─┘        │                     │
                   ├ CH0~CH5             ├ CH0~CH5        [서보 신호]
                   │                     │
                   V+ ← 300W Buck 7.4V   V+ ← 300W Buck 7.4V   [서보 전원 공유]
                   GND ← 공통 GND        GND ← 공통 GND
```

- **로직 전원 (RPi, PCA9685 VCC)**: UBEC 5V → RPi 5V → PCA9685 VCC (3.3V 로직)
- **파워 전원 (V+)**: 300W Buck 7.4V → 두 PCA9685의 V+ 터미널
- **GND 공통**: 로직/파워 GND 모두 한 점에서 묶음

---

## 3. 서보 인덱스 규칙

코드([servo_controller.py:30](../../JetsonNano/servo_controller.py#L30))에서 사용하는 12개 서보 인덱스는 아래 순서로 고정되어 있다.

| 인덱스 | 다리 | 관절 | 약칭 | 서보 모델 |
|--------|------|------|------|-----------|
| 0 | Front Left  | Lower (Knee/무릎)    | FL-Lower    | DS3235 |
| 1 | Front Left  | Upper (Thigh/허벅지) | FL-Upper    | DS3235 |
| 2 | Front Left  | Shoulder (Hip/힙)    | FL-Shoulder | CLS6322HV |
| 3 | Front Right | Lower                | FR-Lower    | DS3235 |
| 4 | Front Right | Upper                | FR-Upper    | DS3235 |
| 5 | Front Right | Shoulder             | FR-Shoulder | CLS6322HV |
| 6 | Rear Left (Back Left)   | Lower    | RL-Lower    | DS3235 |
| 7 | Rear Left               | Upper    | RL-Upper    | DS3235 |
| 8 | Rear Left               | Shoulder | RL-Shoulder | DS3235 |
| 9 | Rear Right (Back Right) | Lower    | RR-Lower    | DS3235 |
| 10 | Rear Right             | Upper    | RR-Upper    | CLS6336HV |
| 11 | Rear Right             | Shoulder | RR-Shoulder | DS3230 |

각 다리는 3자유도(3-DOF): **Shoulder(힙 회전)** → **Upper(허벅지)** → **Lower(무릎)** 순서로 관절이 이어진다.

> **정정 사항**: 기존 표는 관절-모델 대응이 역순으로 기재되어 있었다 (예: idx 0~2가 CLS6322HV, DS3235, DS3235 순). 실제 조립 의도는 하중이 크게 걸리는 Lower/Upper에 DS3235를, 상대적으로 부하가 적은 Shoulder에 가장 약한 모터(CLS6322HV, RR은 DS3230)를 배치하는 것이었다. 위 표는 이를 반영해 정정함.

---

## 4. PCA9685 채널 매핑

> **변경 사항**: 기존엔 Front/Rear 기준(0x40=앞다리, 0x41=뒷다리)으로 나눠져 있었으나, 실제 실장 구조(배터리가 세로로 중앙 배치, PCA9685 두 개가 배터리 좌/우에 배치)와 맞지 않아 배선이 보드마다 배터리를 가로질러야 했다. **Left/Right 기준**(0x40=우측 보드→오른쪽 다리, 0x41=좌측 보드→왼쪽 다리)으로 변경해 각 보드가 자기 쪽 다리만 담당하도록 재배선함. 서보 인덱스(§3)의 의미는 그대로 유지되고, 인덱스가 어느 보드/채널로 나가는지만 바뀌었다.

[servo_controller.py](../../JetsonNano/servo_controller.py)의 `_channel_map`:

```python
self._channel_map = {
    0: (self._kit2, 0),  1: (self._kit2, 1),  2: (self._kit2, 2),   # FL -> 0x41 CH0~2   (좌측 앞단)
    3: (self._kit, 13),  4: (self._kit, 14),  5: (self._kit, 15),   # FR -> 0x40 CH13~15 (우측 반전 -> 끝단이 앞쪽)
    6: (self._kit2, 13), 7: (self._kit2, 14), 8: (self._kit2, 15),  # RL -> 0x41 CH13~15 (좌측 끝단)
    9: (self._kit, 0),   10: (self._kit, 1),  11: (self._kit, 2),   # RR -> 0x40 CH0~2   (우측 반전 -> 앞단이 뒤쪽)
}
```

즉 두 보드 모두 **CH0~2 + CH13~15** 만 쓰고 CH3~12는 비어있다. 다만 **어느 블록이 앞다리인지는 보드마다 다르다.**

> **채널 선택 기준은 배선 길이다.** 각 보드에서 그 다리에 물리적으로 가까운 헤더를 쓴다.
> - **좌측 보드(0x41)**: CH0 이 앞쪽 → 앞다리 CH0~2, 뒷다리 CH13~15
> - **우측 보드(0x40)**: **반전 장착**이라 CH15 가 앞쪽 → 앞다리 CH13~15, 뒷다리 CH0~2
>
> PCA9685의 16개 채널은 전기적으로 완전히 동일하므로, 배선이 짧아지는 쪽으로 꽂고 코드를 거기에 맞추면 된다.
>
> ⚠️ **펄스 폭 설정 주의**: `set_pulse_width_range(500, 2500)`을 `range(6)`으로 돌리면 CH13~15가 기본값(750~2250µs)으로 남아 **같은 각도 명령에 다리마다 다르게 움직인다.** 반드시 `_channel_map`에 등록된 채널 전부에 적용할 것.

### 4.1 PCA9685 #1 (I2C 주소 `0x40`) — 우측 다리 (Right Legs, 반전 장착)

| 채널 | 서보 인덱스 | 다리 위치 | 관절 | 초기 오프셋 |
|:----:|:-----------:|-----------|------|:----------:|
| CH13 | 3  | Front Right | Lower    | 1°   |
| CH14 | 4  | Front Right | Upper    | 95°  |
| CH15 | 5  | Front Right | Shoulder | 90°  |
| CH0  | 9  | Rear Right | Lower    | 1°   |
| CH1  | 10 | Rear Right | Upper    | 90°  |
| CH2  | 11 | Rear Right | Shoulder | 95°  |
| CH3~CH12 | — | (미사용) | — | — |

### 4.2 PCA9685 #2 (I2C 주소 `0x41`) — 좌측 다리 (Left Legs)

| 채널 | 서보 인덱스 | 다리 위치 | 관절 | 초기 오프셋 |
|:----:|:-----------:|-----------|------|:----------:|
| CH0  | 0  | Front Left  | Lower    | 170° |
| CH1  | 1  | Front Left  | Upper    | 85°  |
| CH2  | 2  | Front Left  | Shoulder | 90°  |
| CH13 | 6  | Rear Left  | Lower    | 172° |
| CH14 | 7  | Rear Left  | Upper    | 90°  |
| CH15 | 8  | Rear Left  | Shoulder | 90°  |
| CH3~CH12 | — | (미사용) | — | — |

> **오프셋 값 출처**: [servo_controller.py:30](../../JetsonNano/servo_controller.py#L30)
> ```python
> self._servo_offsets = [170, 85, 90, 1, 95, 90, 172, 90, 90, 1, 90, 95]
> ```
> Lower 관절이 170°/172°/1°/1° 등 극단값인 이유: 서보 혼(horn)의 실장 방향과 링키지 기구학상의 원점 방향이 다르기 때문. work06.md의 조립 기록 참조.

---

## 5. RPi 5 ↔ PCA9685 #1 배선 (I2C + 로직 전원)

| RPi 5 물리핀 | 신호 | PCA9685 #1 핀 | 비고 |
|:------------:|------|:-------------:|------|
| Pin 1  | 3.3V     | VCC | 로직 전원 (PCA9685 IC 자체 구동, 서보에는 사용 X) |
| Pin 3  | GPIO 2 (SDA1) | SDA | I2C 데이터 |
| Pin 5  | GPIO 3 (SCL1) | SCL | I2C 클록 |
| Pin 6  | GND      | GND | 공통 GND |

- I2C 버스는 RPi 5 기본 버스 1(`/dev/i2c-1`) 사용
- OE(Output Enable) 핀은 미연결(내부 풀다운으로 항상 Active)

---

## 6. PCA9685 #1 ↔ PCA9685 #2 데이지 체인

PCA9685 보드는 좌/우 양쪽에 동일한 4핀 헤더(VCC/GND/SDA/SCL)가 있어 그대로 이어붙이면 된다.

| PCA9685 #1 (Right 헤더) | → | PCA9685 #2 (Left 헤더) |
|:-----------------------:|:--:|:----------------------:|
| VCC | → | VCC |
| GND | → | GND |
| SDA | → | SDA |
| SCL | → | SCL |

- V+ (서보 전원) 터미널은 데이지 체인이 아니라 **각 보드마다 300W Buck 7.4V에서 개별 배선**.
  → 두 보드가 각각 6개 서보를 구동하므로 V+ 전류를 분산하기 위함.

### 6.1 두 번째 PCA9685의 주소 설정
- A0 점퍼 패드 납땜(Short) → 주소 `0x41`
- A1~A5는 그대로(오픈) 유지

---

## 7. 서보 커넥터 방향 (PCA9685 3핀 헤더)

각 PCA9685의 CH0~CH15 3핀 헤더 순서 (보드 상단 라벨 기준):

```
  ┌─────┐
  │ PWM │ ← 노란색/오렌지 (신호)
  │ V+  │ ← 빨간색 (7.4V 서보 전원)
  │ GND │ ← 갈색/검정 (GND)
  └─────┘
```

- DS3230/DS3235 서보 표준 3핀 커넥터와 방향 일치
- 역방향 삽입 시 서보 소손 위험 → 결선 전 반드시 색상 확인

---

## 8. 빠른 검증 절차

### 8.1 I2C 주소 감지
```bash
i2cdetect -y 1
```
정상 출력 (work08.md에서 확인됨):
```
40: 40 41 -- -- -- -- ...
70: 70 71 -- -- -- -- ...    ← All-Call 주소 (자동 응답, 정상)
```

### 8.2 채널별 개별 동작
```bash
cd JetsonNano/examples
python3 test_servos_cali.py
```
- 프롬프트에서 `0~11` 입력 → 위 §4 매핑대로 해당 서보만 움직이면 배선 OK
- 예: `0` 입력 시 FL-Lower만 움직여야 함. 다른 다리가 움직이면 채널 뒤바뀜.

---

## 9. 요약 카드 (한 장 요약)

```
     로봇 앞쪽 ↑                              로봇 앞쪽 ↑
┌────── PCA9685 #2 (0x41, 좌측) ──────┐   ┌─── PCA9685 #1 (0x40, 우측/반전) ────┐
│ CH0 : FL-Lower    (idx 0,  offs 170)│   │ CH13: FR-Lower    (idx 3,  offs 1)  │
│ CH1 : FL-Upper    (idx 1,  offs 85) │   │ CH14: FR-Upper    (idx 4,  offs 95) │
│ CH2 : FL-Shoulder (idx 2,  offs 90) │   │ CH15: FR-Shoulder (idx 5,  offs 90) │
│ CH13: RL-Lower    (idx 6,  offs 172)│   │ CH0 : RR-Lower    (idx 9,  offs 1)  │
│ CH14: RL-Upper    (idx 7,  offs 90) │   │ CH1 : RR-Upper    (idx 10, offs 90) │
│ CH15: RL-Shoulder (idx 8,  offs 90) │   │ CH2 : RR-Shoulder (idx 11, offs 95) │
│ CH3~12: 미사용                       │   │ CH3~12: 미사용                       │
└─────────────────────────────────────┘   └─────────────────────────────────────┘
   CH0 이 앞쪽                                CH15 가 앞쪽 (보드 반전 장착)
       ▲                                        ▲
       │ I2C 데이지 체인                         │ I2C (RPi 5 Pin 3/5)
       │                                        │
       └────────────────────────────────────────┘
       V+ 7.4V ← 300W Buck (개별 배선)
       GND     ← 공통 GND
```

> 왼쪽 다리(FL/RL)는 좌측 보드(0x41), 오른쪽 다리(FR/RR)는 우측 보드(0x40)가 담당 — 배터리를 가로지르는 배선 없이 각 보드가 자기 쪽 다리만 처리.

---

## 10. 다음 단계

- [ ] 서보 12개 전부 조립 후 §8.2 절차로 채널 매핑 재검증
- [ ] 오프셋 값(§4)이 실제 기구학 원점과 일치하는지 정지 자세 촬영으로 확인
- [ ] MPU6050 I2C 연결 (같은 버스에 추가, 주소 `0x68`)
