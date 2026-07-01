# SpotMicro Week 03 — Isaac Sim + Isaac Lab 설치 및 RL 훈련

> 작성일: 2026-06-30

---

## 1. 설치 구조

```
D:\Projects\Robots\
├── SpotMicroJetson-master\   ← 기존 SpotMicro 프로젝트 (URDF, 코드)
├── IsaacLab\                 ← Isaac Lab 소스코드 (GitHub clone)
└── isaac_env_4.5\            ← Python 가상환경 (Isaac Sim 4.5 pip 설치, ~20GB)
                                 버전명 포함: 여러 로봇 프로젝트가 공유, 추후 버전 업 시 혼동 방지
```

---

## 2. 설치 순서

### Step 1 — uv 가상환경 생성

```powershell
uv venv D:\Projects\Robots\isaac_env_4.5 --python 3.10
```

### Step 2 — Isaac Sim 4.5.0.0 설치

> ⚠️ 약 20GB, 1~2시간 소요. PC를 켜둬야 함.

```powershell
D:\Projects\Robots\isaac_env_4.5\Scripts\activate.ps1
pip install isaacsim==4.5.0.0 --extra-index-url https://pypi.nvidia.com
```

설치 확인:
```powershell
python -c "import isaacsim; print('OK')"
```

### Step 3 — Isaac Lab clone

```powershell
cd D:\Projects\Robots
git clone https://github.com/isaac-sim/IsaacLab.git
```

버전 고정 (4.5.0 호환 버전):
```powershell
cd IsaacLab
git checkout v2.3.2
```

### Step 4 — Isaac Lab 패키지 설치 (editable)

```powershell
$python = "D:\Projects\Robots\isaac_env_4.5\Scripts\python.exe"

& $python -m pip install -e D:\Projects\Robots\IsaacLab\source\isaaclab
& $python -m pip install -e D:\Projects\Robots\IsaacLab\source\isaaclab_assets
& $python -m pip install -e D:\Projects\Robots\IsaacLab\source\isaaclab_tasks
& $python -m pip install -e D:\Projects\Robots\IsaacLab\source\isaaclab_rl
```

설치 확인:
```powershell
& $python -c "import isaaclab; print('OK')"
```

---

## 3. Windows 필수 패치 (4개)

Isaac Sim 4.5.0은 Windows에서 버그가 있어 아래 패치가 필수.

### 패치 1 — DLL 로딩 순서

모든 Isaac Sim 스크립트 최상단에 `import torch`를 가장 먼저 추가.

파일: `D:\Projects\Robots\IsaacLab\scripts\reinforcement_learning\rsl_rl\train.py`
```python
# 파일 맨 위에 추가
import torch  # Must be imported before Isaac Sim to fix Windows DLL loading order
```

파일: `D:\Projects\Robots\IsaacLab\scripts\reinforcement_learning\rsl_rl\play.py`
```python
import torch  # Must be imported before Isaac Sim to fix Windows DLL loading order
```

### 패치 2 — 헤드리스 모드 URDF 임포터 누락

파일: `D:\Projects\Robots\IsaacLab\apps\isaacsim_4_5\isaaclab.python.headless.kit`

`[dependencies]` 섹션에 추가:
```
"isaacsim.asset.importer.urdf" = {}
"isaacsim.asset.importer.mjcf" = {}
```

### 패치 3 — set_merge_fixed_ignore_inertia API 누락

파일: `D:\Projects\Robots\IsaacLab\source\isaaclab\isaaclab\sim\converters\urdf_converter.py`

변경 전:
```python
import_config.set_merge_fixed_joints(self.cfg.merge_fixed_joints)
import_config.set_merge_fixed_ignore_inertia(self.cfg.merge_fixed_joints)
```

변경 후:
```python
import_config.set_merge_fixed_joints(self.cfg.merge_fixed_joints)
if hasattr(import_config, "set_merge_fixed_ignore_inertia"):
    import_config.set_merge_fixed_ignore_inertia(self.cfg.merge_fixed_joints)
```

### 패치 4 — /tmp 경로 오류 (Windows에 /tmp 없음)

파일: `D:\Projects\Robots\IsaacLab\source\isaaclab\isaaclab\sim\converters\asset_converter_base.py`

파일 상단에 추가:
```python
import tempfile
```

변경 전:
```python
self._tmp_dir = "/tmp/IsaacLab/..."
```
→ `/tmp/IsaacLab/`를 `os.path.join(tempfile.gettempdir(), "IsaacLab", ...)` 로 변경.

---

## 4. SpotMicro RL 환경 설정

### 4.1 로봇 설정 파일 생성

파일: `D:\Projects\Robots\IsaacLab\source\isaaclab_assets\isaaclab_assets\robots\spotmicro.py`

- URDF 경로: `D:\Projects\Robots\SpotMicroJetson-master\urdf\spotmicroai_gen.urdf.xml`
- 초기 높이: 0.20m
- 관절 초기값: shoulder=0.0, leg=0.8, foot=1.5
- 액추에이터: effort_limit=3.0, stiffness=25.0, damping=0.5

### 4.2 RL 환경 등록

경로: `D:\Projects\Robots\IsaacLab\source\isaaclab_tasks\isaaclab_tasks\manager_based\locomotion\velocity\config\spotmicro\`

필요 파일:
- `flat_env_cfg.py` — 보상 함수, 관찰 공간, 종료 조건
- `agents\rsl_rl_ppo_cfg.py` — PPO 하이퍼파라미터
- `__init__.py` — gym 태스크 등록

태스크 이름:
- 훈련: `Isaac-Velocity-Flat-SpotMicro-v0`
- 시각화: `Isaac-Velocity-Flat-SpotMicro-Play-v0`

### 4.3 핵심 보상 가중치 (reward hacking 방지용)

| 항목 | 값 | 설명 |
|------|-----|------|
| `flat_orientation_l2` | -5.0 | 누운 자세 강하게 패널티 |
| `base_height_l2` | -2.0 | 높이 유지 (목표: 0.18m) |
| `ang_vel_xy_l2` | -0.5 | 좌우 기울기 패널티 |
| `lin_vel_z_l2` | -2.0 | 공중 뜨기 패널티 |
| `track_lin_vel_xy_exp` | +1.5 | 전진 보상 |
| `track_ang_vel_z_exp` | +0.75 | 회전 보상 |

### 4.4 NaN 버그 패치 (rsl-rl)

파일: `isaac_env\Lib\site-packages\rsl_rl\modules\distribution.py`

`update()` 메서드에 `nan_to_num` 추가:
```python
std = self.std_param.nan_to_num(nan=self.std_range[0]).clamp(self.std_range[0], self.std_range[1])
```

---

## 5. 훈련 및 결과 확인

### 훈련 실행

```powershell
$python = "D:\Projects\Robots\isaac_env_4.5\Scripts\python.exe"
cd D:\Projects\Robots\IsaacLab
& $python scripts\reinforcement_learning\rsl_rl\train.py `
    --task Isaac-Velocity-Flat-SpotMicro-v0 `
    --num_envs 64 `
    --headless
```

소요 시간: 약 3시간 (10,000 iteration, RTX 3060)

### 결과 영상 녹화

```powershell
& $python scripts\reinforcement_learning\rsl_rl\play.py `
    --task Isaac-Velocity-Flat-SpotMicro-Play-v0 `
    --num_envs 1 `
    --headless `
    --video `
    --video_length 500
```

영상 저장 위치: `D:\Projects\Robots\IsaacLab\logs\rsl_rl\spotmicro_flat\<날짜>\videos\play\`

---

## 6. URDF 관절 정보

| 관절 패턴 | 범위 |
|-----------|------|
| `.*_shoulder` | [-0.548, 0.548] rad |
| `.*_leg` | [-2.666, 1.548] rad |
| `.*_foot` | [-0.1, 2.59] rad |

- `toe_link`는 질량 없어 `foot_link`로 병합됨 (`merge_fixed_joints=True`)
- 접촉 센서 패턴: `.*foot_link` (toe_link 아님)
