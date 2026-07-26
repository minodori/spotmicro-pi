# SpotMicro Week 06 — 서보 조립 시 초기 각도 설정

> 작성일: 2026-07-26

---

## 1. 핵심 원칙: 조립 시 90° 세팅

서보를 조립할 때는 **90°(전기적 중립)로 설정한 뒤 혼(Horn)을 결합**하는 것이 기본 원칙이다.  
180° 범위 서보에서 90°는 정중앙이므로 양방향으로 ±90°의 최대 운동 범위를 확보할 수 있다.

---

## 2. "직립 중립"은 관절마다 다르다

서보를 90°에서 조립했다고 해서, 로봇이 직립 자세를 취할 때 모든 서보가 90°에 있는 것은 아니다.  
`JetsonNano/servo_controller.py`의 offset 배열이 이를 보여준다.

```python
# [FL_무릎, FL_엉덩, FL_어깨, FR_무릎, FR_엉덩, FR_어깨,
#  RL_무릎, RL_엉덩, RL_어깨, RR_무릎, RR_엉덩, RR_어깨]
self._servo_offsets = [170, 85, 90, 1, 95, 90, 172, 90, 90, 1, 90, 95]
```

| 관절 | offset 범위 | 의미 |
|------|-------------|------|
| **어깨 (roll/abduction)** | ≈ 90 | 다리 수직 하방 = 좌우 대칭 중립 → 90°가 실제 중립 |
| **엉덩이 (hip/upper leg)** | 85 ~ 95 | 대퇴부 직하방 ≈ 90° 근방 |
| **무릎 (knee/lower leg)** | 170 또는 1 | 좌/우 서보가 **거울 대칭으로 반전 장착** |

---

## 3. 무릎(lower) 서보 offset이 극단값인 이유

`angleToServo()` 함수를 보면 좌/우 무릎은 부호가 반대다.

```python
# FL Lower (왼쪽): 빼기
self._val_list[0] = self._servo_offsets[0] - self._thetas[0][2]  # offset=170

# FR Lower (오른쪽): 더하기
self._val_list[3] = self._servo_offsets[3] + self._thetas[1][2]  # offset=1
```

왼쪽과 오른쪽 무릎 서보는 물리적으로 **반대 방향으로 장착**되어 있기 때문에, 같은 "다리 완전히 편 상태(theta=0)"가:
- 왼쪽 무릎: 서보 **170°**
- 오른쪽 무릎: 서보 **1°**

에 해당한다. 즉 서보를 90°로 조립하고 혼을 달면, 그 상태는 "무릎이 약 80° 구부러진 중간 자세"가 된다.

---

## 4. 실제 직립 자세 = IK가 계산한 각도

`servo_controller.py` 하단의 직립 목표 좌표:

```python
legEndpoints = np.array([[100,-100,87.5,1], [100,-100,-87.5,1],
                          [-100,-100,87.5,1], [-100,-100,-87.5,1]])
thetas = kn.initIK(legEndpoints)
```

발끝이 엉덩이 관절 아래 **100mm** 위치일 때, IK가 계산한 theta 값이 "직립 서보 각도"다.  
이 때 무릎은 완전히 펴지지 않고 **약간 굽혀진 상태**다.

> 다리를 완전히 펴면 역운동학(IK)이 특이점(Singularity)에 빠지고, 충격 흡수 능력도 사라지기 때문에 실제 보행 로봇은 무릎을 항상 약간 구부린 상태로 유지한다.

---

## 5. 조립 권장 순서

1. **서보를 90°로 설정** (전기적 중립, 최대 범위 확보)
2. 각 관절을 아래 기준 자세에서 혼 결합:

   | 관절 | 혼 결합 기준 자세 | 서보 각도 |
   |------|-------------------|-----------|
   | 어깨 (shoulder/roll) | 다리가 몸체에서 수직 하방 | 90° 그대로 |
   | 엉덩이 (hip/upper) | 대퇴부 직하방 | 90° 근방 |
   | 무릎 (knee/lower) | **좌/우 장착 방향 확인 후** 하퇴부 직하방(다리 완전히 편 상태) | 좌: ~170°, 우: ~1° |

3. 조립 후 `JetsonNano/examples/test_servos_cali.py`로 실측 조정
4. 측정값을 `servo_controller.py`의 `_servo_offsets` 배열에 기록

---

## 6. 관련 파일

| 파일 | 역할 |
|------|------|
| `JetsonNano/servo_controller.py` | `_servo_offsets` 배열, `angleToServo()` 매핑 로직 |
| `JetsonNano/servo_controller_fix.py` | 표준 기준값 (모두 90°/1°/180°) |
| `JetsonNano/examples/test_servos_cali.py` | 서보별 각도 수동 조정 (1도 단위 스위프) |
| `JetsonNano/examples/test_servos_offset.py` | 오프셋 테스트 (기준: 90°) |
| `Kinematics/kinematics.py` | IK 계산 (`legIK`, `initIK`) |
