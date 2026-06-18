# SpotMicro 서보모터 & 파트 분석

> 작성일: 2026-06-06

---

## 1. 파트 출력 (3D 프린팅)

SpotMicro의 모든 구조 파트는 FDM 3D 프린터로 출력한다. 구동부(다리, 조인트)는 PETG, 바디(몸체)는 PLA를 권장한다.

### 출력 파트 목록

| 파트 | 소재 | 비고 |
|------|------|------|
| 바디 상판/하판/측판 | PLA | Body B/T/Side |
| 숄더 브라켓 (L/R × 2) | PETG | 어깨 관절 |
| 어퍼 레그 (L/R × 2) | PETG | 위 다리 |
| 로어 레그 (L/R × 2) | PETG | 아래 다리 |
| 서보 마운트 × 12 | PETG | 구동부 |

### 출력 파트 사진

**[신규 출력 파트]**

![새로 출력한 파트 전체](images/Parts_new.jpg)

**[원본 참고 파트]**

![원작자(KDY) 출력 파트](images/Parts_original.jpg)

### 사전 조립 상태

![사전 조립 (서보 미장착)](images/Pre-assembly_new.jpg)

### 조립 완성 참고 (원본)

![원본 조립 완성품](images/Assembly_original.jpg)

---

## 2. 서보모터 사양 비교

> 기준일: 2026-06-06 · 가격 기준: 알리익스프레스

### 2.1 주요 모델 비교표

| 항목 | MG996R | JX PDI-HV5523MG | JX CLS6336HV | DS3218 PRO | SPT5435LV-180 |
|------|--------|-----------------|--------------|------------|----------------|
| **사용 프로젝트** | KDY (원작자) | mike4192 | 한양대 Road Balance | 커뮤니티 일반 | 커뮤니티 일반 |
| **[토크]** | | | | | |
| 토크 @ 저전압 | 9.4 kg·cm (4.8V) | 19.2 kg·cm (6.0V) | 27.8 kg·cm (6.6V) | 28.5 kg/cm (5V) | 29 kg/cm (5V) |
| 토크 @ 고전압 | 11 kg·cm (6.0V) | 23 kg·cm (8.4V) | 35.6 kg·cm (7.4V) | 38 kg/cm (6.8V) | 35 kg/cm (6.8V) |
| **[속도]** | | | | | |
| 속도 @ 저전압 | 0.19 sec/60° (4.8V) | 0.18 sec/60° (6.0V) | 0.14 sec/60° (6.6V) | 0.11초/60° (5V) | 0.16/60° (5V) |
| 속도 @ 고전압 | 0.15 sec/60° (6.0V) | 0.16 sec/60° (8.4V) | 0.11 sec/60° (7.4V) | 0.09초/60° (6.8V) | 0.14초/60° (6.8V) |
| **[전기 사양]** | | | | | |
| 동작전압 | 4.8V ~ 7.2V | 6.0V ~ 8.4V | 6.0V ~ 7.4V | 4.8V ~ 6.8V | 4.8V ~ 6.8V |
| 권장전압 | 6V | 8.4V | 7.4V | 6.8V | 6.8V |
| 모터타입 | 브러시 DC | 브러시 DC (iron core) | 코어리스 DC | 브러시 DC | 브러시 DC |
| 신호타입 | PWM | Digital PWM | Digital PWM | Digital PWM | Digital PWM |
| 데드밴드 | 5 μs | 2 μs | 1 μs | 3 μs | 4 μs |
| **[기구 사양]** | | | | | |
| 각도 | 180° | 120° | 120°, 180° | 180°, 270° | 180° |
| 기어 | 메탈 | 메탈 (알루미늄) | 메탈 (CNC 알루미늄) | 메탈 | 메탈 |
| 크기 (mm) | 40.7 × 19.7 × 42.9 | 40.5 × 20.2 × 38 | 40.5 × 20.2 × 40 | 40 × 20 × 38.5 | 40.5 × 20 × 40 |
| 무게 | 55 g | 55.6 g | - | 60 g | 60 g |
| **[가격 (알리 기준)]** | | | | | |
| 개당 가격 | ₩3,200 | ₩16,000 | ₩49,000 | ₩22,000 | ₩25,000 |
| **12개 합계** | **₩38,400** | **₩192,000** | **₩588,000** | **₩264,000** | **₩300,000** |
| **[SpotMicro 적합성]** | | | | | |
| 토크 충분 여부 | ❌ 부족 | ✅ 충분 | ✅ 매우 충분 | ✅ 충분 | ✅ 충분 |
| 가성비 | ⚠️ 싸지만 부족 | ✅ 양호 | ⚠️ 고가 | ✅ 최고 | ✅ 최고 |
| 모델 수정 불필요 | ✅ (KDY 원작) | ✅ (mike4192) | ✅ (한양대) | ⚠️ 유사 사이즈 | ⚠️ 유사 사이즈 |
| **권장 여부** | ❌ 비추 | ✅ 추천 | ✅ 고성능 추천 | ✅ 가성비 추천 | ✅ 가성비 추천 |

### 2.2 구매 검색어

| 모델 | 알리 검색어 | 개당 가격 | 판매사 |
|------|------------|----------|--------|
| MG996R | MG996R servo | ₩3,200 | TowerPro Clone |
| JX PDI-HV5523MG | JX PDI-HV5523MG | ₩16,000 | X Servo |
| JX CLS6336HV | JX CLS6336HV | ₩49,000 | JX Servo |
| DS3230 Pro | DS3218 PRO 180 degree | ₩15,000 | DSServo |
| YP3235MG | DS3218 PRO 180 degree | ₩28,000 | QYRC Servo |
| YPinervo | DS3218 PRO 180 degree | ₩21,000 | GXServo |
| SPT5435LV-180 | DS3218 PRO 180 degree | ₩25,000 | SPT Servo |
| TD8135MG | TD8135MG | ₩25,000 | READYTOSKY, DIYmall |

---

## 3. 서보모터 상세 사양

### 3.1 MG996R

![MG996R 외관](images/MG996R_specs.jpg)

![MG996R 도면](images/MG996R_drawings.jpg)

- 원작자(KDY) 사용 모델이지만 **토크 부족으로 현재는 비추천**
- 브러시 DC, PWM 신호, 데드밴드 5μs (정밀도 낮음)
- 저렴하지만 SpotMicro 구동에는 토크가 부족 (11 kg·cm @ 6V)

---

### 3.2 JX PDI-HV5523MG

![JX PDI-HV5523MG 외관](images/image_511899841_9.jpg)

![JX PDI-HV5523MG 스펙](images/PDI-HV5523MG_specs.jpg)

![JX PDI-HV5523MG 도면](images/PDI-HV5523MG_drawings.jpg)

- mike4192 프로젝트 사용 모델
- Iron core 브러시 DC, Digital PWM, 데드밴드 2μs
- 23 kg·cm @ 8.4V — 충분한 토크
- **CLS6336HV와 도면 크기 거의 동일** → 모델 수정 불필요

---

### 3.3 JX CLS6336HV

![JX CLS6336HV 외관](images/CLS6336HV .jpg)

![JX CLS6336HV 스펙](images/CLS6336HV _specs.jpg)

![JX CLS6336HV 도면](images/CLS6336HV _drawings.jpg)

![JX CLS6336HV 도면 치수](images/image_511899841_14.jpg)

- 한양대 Road Balance 팀 사용 모델
- **코어리스 DC 모터** — 응답성 뛰어남
- CNC 알루미늄 기어, 35.6 kg·cm @ 7.4V — 매우 충분한 토크
- 데드밴드 1μs — 가장 높은 정밀도
- 단점: **개당 ₩49,000으로 고가** (12개 합계 ₩588,000)

---

### 3.4 DS3230 Pro

![DS3230 Pro 외관](images/DS3230Pro.jpg)

![DS3230 Pro 스펙](images/DS3230Pro_specs.jpg)

![DS3230 Pro 도면](images/DS3230Pro_drawings.jpg)

- 커뮤니티 가성비 추천 모델
- 38 kg/cm @ 6.8V — 가장 높은 토크
- **개당 ₩15,000 (12개 ₩180,000) — 최고 가성비**
- 180° / 270° 두 가지 각도 버전 존재 → **180° 버전 구매 필수**

---

### 3.5 SPT5435LV-180

![SPT5435LV-180 외관](images/SPT5435LV-180.jpg)

![SPT5435LV-180 스펙](images/SPT5435LV-180_specs.jpg)

![SPT5435LV-180 도면](images/SPT5435LV-180_drawings.jpg)

- 커뮤니티 가성비 추천 모델
- 35 kg/cm @ 6.8V — 충분한 토크
- 개당 ₩25,000 (12개 ₩300,000)

---

### 3.6 기타 검토 모델

| 모델 | 이미지 | 가격 | 비고 |
|------|--------|------|------|
| YP3235MG | ![YP3235MG](images/YP3235MG.jpg) | ₩28,000 | QYRC, 35kg |
| YPinervo | ![YPinervo](images/YPinervo.jpg) | ₩21,000 | GXServo |
| TD8135MG | ![TD8135MG](images/TD8135MG.jpg) | ₩25,000 | READYTOSKY |
| TD8120MG | ![TD8120MG](images/TD8120MG.png) | ₩22,000 | TD-8325MG, 25kg |

**YP3235MG 상세 스펙**

![YP3235MG 스펙](images/YP3235MG_specs.jpg)

![YP3235MG 도면](images/YP3235MG_drawings.jpg)

**YPinervo 상세 스펙**

![YPinervo 스펙](images/YPinervo_specs.jpg)

![YPinervo 도면](images/YPinervo_drawings.jpg)

**TD8135MG 상세 스펙**

![TD8135MG 스펙](images/TD8135MG_specs.jpg)

![TD8135MG 도면](images/TD8135MG_drawings.jpg)

---

## 4. 도면 크기 비교

SpotMicro 3D 모델의 서보 마운트 홀은 기준 서보 치수에 맞게 설계되어 있다. 교체 서보의 **몸통 두께(48~49.5mm 범위)** 가 핵심 호환 기준이다.

### 4.1 MG996R vs JX CLS6336HV

![MG996R vs CLS6336HV 도면 비교](images/MG996R_vs_CLS6336HV.png)

- MG996R 몸통 두께: **48mm** (빨간 박스)
- CLS6336HV 몸통 두께: **49.5mm** (빨간 박스)
- 차이: +1.5mm → **모델 수정 없이 사용 가능**

### 4.2 JX PDI-HV5523MG vs DS3230

![PDI-HV5523MG vs DS3230 도면 비교](images/PDI-HV5523MG_vs_DS3230.png)

- PDI-HV5523MG 두께: **48mm**
- DS3230 두께: **49.5mm**
- 두 모델 모두 유사 사이즈 → 교체 시 소폭 조정 가능

### 4.3 YP3235MG vs SPT5435LV-180

![YP3235MG vs SPT5435LV-180 도면 비교](images/YP3235MG_vs_SPT5435LV-180.png)

- YP3235MG 두께: **47.9mm** (좌)
- SPT5435LV-180 두께: **49mm** (우)

---

## 5. 서보 혼 비교

서보 혼(Horn)은 서보 출력축에 장착되는 연결 부품이다. 서보 교체 시 혼의 형상과 장착 홀 위치가 다리 링크 파트와 호환되어야 한다.

### 5.1 숄더(Shoulder) 혼 비교

**MG996R vs CLS6336HV**

![숄더 혼 비교 — MG996R(좌) vs CLS6336HV(우)](images/Shoulder_Horn_MG996R_vs_CLS6336HV.png)

- 좌: MG996R 혼 (어두운 색)
- 우: CLS6336HV 혼 (밝은 색)
- CLS6336HV 혼이 **약 30mm 더 큼** → 링크 파트 재설계 필요

### 5.2 레그(Leg) 혼 비교

**MG996R vs CLS6336HV**

![레그 혼 비교 — MG996R(좌,파랑) vs CLS6336HV(우,노랑)](images/Leg_Horn_MG996R_vs_CLS6336HV.png)

- 혼 상단 구멍 위치가 다름 (빨간 박스 표시)
- 레그 링크 파트 홀 위치도 달라지므로 **파트 수정 또는 신규 출력 필요**

### 5.3 CLS6336HV 크기 비교

![CLS6336HV가 MG996R보다 30mm 더 큰 링크 파트 비교](images/CLS6336HV_largerthan_MG996Rby_30mm.png)

- 상단 링크(어퍼 레그) 파트의 길이 차이 확인
- CLS6336HV 적용 시 어퍼 레그 파트가 **30mm 더 길어짐**

---

## 6. 연결도 (Wiring Diagram)

### 6.1 수정된 연결도 (Minho 수정본)

![SpotMicro 전체 연결도 (Minho 수정)](images/Wiring_new.jpg)

**구성 요소:**
- LiPo 배터리 → 전원 스위치 → UBEC 2개 (서보용 6V/10A, RPi용 5V/5A)
- PCA9685 × 2 (서보 드라이버, 각 16채널 → 총 12개 서보 제어)
- 서보모터 × 12 (각 다리 3개 × 4다리)
- Raspberry Pi 5 (메인 컴퓨터)
- 배터리 잔량 표시기
- I2C LCD 디스플레이
- 소형 스피커 (선택)

> Reference from https://robertchoi.gitbook.io/spotmicro — Modified by Minho

### 6.2 원본 참고 연결도 (Robert Choi GitBook)

![기본적인 전체 회로 구성 (Robert Choi)](images/Wiring_robertchoi_gitbook.jpg)

**참고 링크:**
- GitBook: https://robertchoi.gitbook.io/spotmicro/undefined-1
- Cirkit Designer: https://app.cirkitdesigner.com/project/831f0835-5052-4e85-9442-0e19f2be4248

---

## 7. BOM (부품 목록)

> 가격 기준: 알리익스프레스 / 핀둬둬

| 카테고리 | 부품명 | 사양 | 수량 | 단가 (원) | 합계 (원) | 구매처 | 비고 |
|----------|--------|------|-----:|----------:|----------:|--------|------|
| 서보모터 | DS3218 PRO | 20kg·cm, 6.8V, 180°, 메탈기어 | 12 | 15,000 | 180,000 | 알리/핀둬둬 | DS3218 PRO servo 검색 |
| 서보드라이버 | PCA9685 | 16ch PWM, I2C | 1 | 3,000 | 3,000 | 알리/핀둬둬 | |
| 컴퓨터 | Raspberry Pi 5 | 4GB | 1 | 178,000 | 178,000 | 국내(아이씨뱅큐 등) | |
| 배터리 | LiPo 2S~3S | 3300mAh, 25C 이상, XT60 | 1 | 15,000 | 15,000 | 알리/핀둬둬 | |
| 전원변환 | UBEC (RPi 5) | 5V/5A | 1 | 5,000 | 5,000 | 알리/핀둬둬 | 라즈파이 전원용 |
| 전원변환 | UBEC (서보) | 6V/10A | 1 | 15,000 | 15,000 | 알리/핀둬둬 | 서보 전원용 |
| 베어링 | 볼베어링 | 8×16×5mm, F688ZZ | 16 | 500 | 8,000 | 알리/핀둬둬 | |
| 볼트/너트 | M2/M3 볼트너트 세트 | 각종 사이즈 | 1 | 10,000 | 10,000 | 알리/핀둬둬 | |
| 필라멘트 | PETG | 1kg | 1 | 15,000 | 15,000 | 알리/핀둬둬 | 구동부 |
| 필라멘트 | PLA | 1kg | 1 | 15,000 | 15,000 | 알리/핀둬둬 | Body |
| | | | | **총계** | **444,000** | | |
| | | | | **소계 (구입 필요)** | **218,000** | | 서보+LiPo+UBEC(서보)+베어링 |
| | | | | **소계 (기 보유)** | **226,000** | | PCA9685+RPi5+UBEC(RPi)+볼트너트+필라멘트 |

---

## 8. 참고 사이트

| 분류 | 사이트명 | URL | 비고 |
|------|---------|-----|------|
| 문서/가이드 | SpotMicroAI 공식문서 | https://spotmicroai.readthedocs.io/en/latest/ | BOM, 조립, SW 가이드 |
| 제작 | mike4192/spotMicro | https://github.com/mike4192/spotMicro | ROS, 라즈베리파이3B, Ubuntu 16.04 |
| 제작 | Thingiverse KDY0523 | https://www.thingiverse.com/thing:3445283 | 원작자(김덕연, KDY) STL 파일 |
| SNS | dykim_works | https://www.instagram.com/dykim_works/ | 김덕연 인스타 |
| Demo | Spot Micro Walking Demo | https://www.youtube.com/watch?v=Cr1ZshV-gqw | |
| 문서/가이드 | Spot Micro 하루에 입문 | https://robertchoi.gitbook.io/spotmicro | |
| 강의자료 | SpotMicro for G Camp | https://puzzling-cashew-c4c.notion.site/SpotMicro-for-G-Camp-c541934a4bad4ad48d1e37ab94c10de8 | 한양대학교 Road Balance팀 |
| 문서/가이드 | SpotMicroAI - Road Balance version | https://github.com/Road-Balance/SpotMicroJetson.git | 한양대학교 Road Balance팀 |
| 문서/가이드 | SeoulWorkShop | https://www.youtube.com/watch?v=XBYq_FJbdTk&list=PLDAyxeaWPd36ol0wfXV4KST0x8v7KWFwO | 한양대학교 Road Balance팀 |
| 문서/가이드 | Ductility Blog | https://ductility.github.io/2021/01/12/Spot_Micro.html | 정대게킬러(성균관대, AIDEN) |
| Github | Spot mini-mini | https://github.com/OpenQuadruped/spot_mini_mini | |
