# STL/kinetiq — 본 팀이 설계한 3D 프린팅 파트

상위 `STL/`, `STEP_Files/`, `Parts/` 는 Thingiverse `thing:3445283`(KDY0523,
**CC BY 3.0**) 에서 상속받은 것이고, 이 디렉터리에는 본 팀이 새로 만든 파트를 둡니다.

| 파트 | 상태 | 근거 문서 | 라이선스 |
|---|---|---|---|
| 서보 테스트용 거치대 (2020 프로파일) | [`study/minho/stl/Spot_Stand.stl`](../../study/minho/stl/Spot_Stand.stl) | [work04](../../study/minho/work04.md) | 독립 창작 — GPL-3.0 |
| 보드·파워 모듈 마운팅 플레이트 | 설계 중 | [work10](../../study/minho/work10.md) 실측 | 기존 `plate.stl` 파생 — **CC BY 3.0 승계** |

> 기존 파트를 수정한 것은 원저작물의 **CC BY 3.0 을 승계**하고, 독립적으로 새로
> 설계한 것에는 저장소 라이선스(GPL-3.0)를 적용합니다.

---

## 본 팀이 실제로 출력한 상속 파트

**아래 파일은 이 디렉터리에 있지 않습니다.** 링크만 걸어 둡니다. 복사하면 두 벌이
어긋나고, KDY0523 의 CC BY 3.0 파트가 본 팀 설계 디렉터리에 섞이면 라이선스 경계가
흐려집니다.

**어느 세트를 출력할지가 이 저장소에서 가장 헷갈리는 지점입니다.**

```
Parts/        Jetson Nano 판.  urdf/ 가 이쪽을 참조하지만 본 팀은 쓰지 않습니다
STL/files/    KDY0523 원본 판.  본 팀은 Raspberry Pi 4B 구성이라 이쪽을 출력했습니다
```

### 몸통 — 8점

| 파일 | 수량 | 소재 |
|---|---:|---|
| [`F_shoulder.stl`](../files/F_shoulder.stl) | 1 | PLA |
| [`R_shoulder.stl`](../files/R_shoulder.stl) | 1 | PLA |
| [`L_side_plate.stl`](../files/L_side_plate.stl) | 1 | PLA |
| [`R_side_plate.stl`](../files/R_side_plate.stl) | 1 | PLA |
| [`T_cover.stl`](../files/T_cover.stl) | 1 | PLA |
| [`B_cover.stl`](../files/B_cover.stl) | 1 | PLA |
| [`F_cover.stl`](../files/F_cover.stl) | 1 | PLA |
| [`R_cover.stl`](../files/R_cover.stl) | 1 | PLA |

### 다리 — 16점 (다리 4개 × 4파트)

| 파일 | 수량 | 소재 |
|---|---:|---|
| [`L_arm_joint.stl`](../files/L_arm_joint.stl) · [`R_arm_joint.stl`](../files/R_arm_joint.stl) | 각 2 | PETG |
| [`L_arm.stl`](../files/L_arm.stl) · [`R_arm.stl`](../files/R_arm.stl) | 각 2 | PETG |
| [`L_arm_cover.stl`](../files/L_arm_cover.stl) · [`R_arm_cover.stl`](../files/R_arm_cover.stl) | 각 2 | PETG |
| [`L_wrist.stl`](../files/L_wrist.stl) · [`R_wrist.stl`](../files/R_wrist.stl) | 각 2 | PETG |

하중을 받는 다리는 PETG, 동체는 PLA 로 출력했습니다.

### 출력하지 않은 것

| 파일 | 이유 |
|---|---|
| [`foot.stl`](../files/foot.stl) | TPU 가 필요합니다. 대신 **미끄럼 방지 패드 3mm** 를 붙였습니다 |
| `F_cover_orig.stl` | `F_cover.stl` 의 원본판 |
| `non-mega_*.stl` 3종 | Arduino Mega 를 쓰지 않는 구성용 대체판 |
| `L/R_ultra_sonic.stl` | 초음파 센서를 달지 않습니다 |
| `plate.stl` | 어느 코드도 참조하지 않는 파트 ([work10 §2](../../study/minho/work10.md)) |

**발을 출력하지 않은 것이 실측값에 그대로 반영돼 있습니다.**
[`Kinematics/kinematics.py:39`](../../Kinematics/kinematics.py) 의 `l4` 주석이
*"STL 원피팅 131 + 미끄럼방지 패드 3"* 이고, 그래서 `l4 = 135` 입니다.

### 이름이 헷갈리는 곳

두 세트에 같은 부품이 다른 이름으로 있습니다.

| 부위 | `STL/files/` (KDY) | `Parts/` (Jetson) |
|---|---|---|
| 대퇴 | `L_arm` | `larm` |
| 하퇴 | `L_wrist` | `lfoot` |
| 어깨 브래킷 | `L_arm_joint` | `lshoulder` |
| 측면판 | `L_side_plate` | `jetson_sidepart` |

**`Parts/lfoot` 은 발이 아니라 하퇴 전체(150mm)입니다.** 이름만 보면 반대로
읽히니 주의하십시오.

### 라이선스

이 절의 파일은 전부 **KDY0523 의 CC BY 3.0** 입니다. 본 팀이 형상을 수정하지
않았고 그대로 출력했습니다. 상세는 [`NOTICE`](../../NOTICE) 4장을 보십시오.
