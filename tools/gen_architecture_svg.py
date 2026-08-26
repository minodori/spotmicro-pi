"""보고서 '시스템 구성 및 아키텍처' 그림을 생성한다.

    python tools/gen_architecture_svg.py

docs/media/architecture.svg 를 쓴다. PNG 가 필요하면

    libreoffice --headless --convert-to png --outdir docs/media docs/media/architecture.svg

그림이 말해야 하는 것은 세 가지다.

  1. 값마다 고칠 곳이 한 군데이고, 시뮬레이션 모델은 거기서 생성된다
  2. 규칙 기반과 강화학습이 같은 상수에서 갈라져 같은 서보 인터페이스로 합류한다
     - 그래서 두 방식을 같은 하드웨어에서 직접 비교할 수 있다
  3. 검증 게이트 8종을 통과하지 못하면 학습이 시작되지 않는다
"""
import pathlib

F = "Noto Sans CJK KR, Noto Sans CJK HK, sans-serif"
MONO = "Noto Sans Mono CJK KR, monospace"

INK = "#1c1c1e"       # 본문
MUTE = "#6b6b70"      # 보조 설명
LINE = "#3a3a3e"      # 화살표
SRC = "#0f5c8c"       # 단일 출처 계열
RULE = "#1f6f4a"      # 규칙 기반 계열
RL = "#6a3fa0"        # 강화학습 계열
GATE = "#b3261e"      # 검증 게이트
HW = "#8a5a00"        # 하드웨어

W, H = 1000, 822
o = []
a = o.append


def box(x, y, w, h, stroke, fill="#ffffff", rx=6, sw=1.6, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"'
      f' stroke="{stroke}" stroke-width="{sw}"{d}/>')


def text(x, y, s, size=14, fill=INK, anchor="middle", weight="400", font=F):
    a(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{fill}"'
      f' font-weight="{weight}" text-anchor="{anchor}">{s}</text>')


def arrow(x1, y1, x2, y2, stroke=LINE, sw=1.8, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    a(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}"'
      f' stroke-width="{sw}" marker-end="url(#ah)"{d}/>')


def path(d, stroke=LINE, sw=1.8, head=True, dash=None):
    m = ' marker-end="url(#ah)"' if head else ""
    ds = f' stroke-dasharray="{dash}"' if dash else ""
    a(f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{sw}"{m}{ds}/>')


a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
a('<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6"'
  f' markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{LINE}"/>'
  '</marker></defs>')
a(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

# ── 1. 측정값의 집 ───────────────────────────────────────────────────────────
box(30, 28, 940, 132, SRC, "#f4f9fd", rx=10)
text(50, 54, "① 측정값의 집 — 값마다 고칠 곳이 정확히 한 군데", 15, SRC, "start", "600")

srcs = [
    (52, "Kinematics/kinematics.py", "링크 기하 (캘리퍼스 실측)", "l1 56 · l2 20 · l3 110 · l4 135 · L 185 · W 78"),
    (356, "Common/servo_map.py", "관절 범위 · 부호 · 영점", "12개 인덱스 ↔ 다리·관절 대응"),
    (660, "rl/gen_mjcf.py:48", "링크 질량", "총 2.20 kg (실측)"),
]
for x, name, role, detail in srcs:
    box(x, 68, 288, 78, SRC)
    text(x + 144, 92, name, 14, SRC, "middle", "600", MONO)
    text(x + 144, 112, role, 13, INK)
    text(x + 144, 132, detail, 11.5, MUTE)

# 갈라지는 지점
path(f"M 500,160 L 500,186", head=False)
path("M 500,186 L 260,186 L 260,214", sw=1.8)
path("M 500,186 L 742,186 L 742,214", sw=1.8)

# ── 2. 두 경로 ───────────────────────────────────────────────────────────────
# 규칙 기반
box(30, 218, 452, 300, RULE, "#f4faf7", rx=10)
text(50, 244, "② 규칙 기반 보행 — 실물 검증 완료", 15, RULE, "start", "600")

box(56, 262, 400, 56, RULE)
text(256, 285, "역기구학 (legIK / bodyIK)", 14, INK, "middle", "600")
text(256, 305, "발끝 목표 좌표 → 관절 각도 12", 12, MUTE)

arrow(256, 318, 256, 344)

box(56, 346, 400, 50, RULE)
text(256, 366, "보행 궤적 생성", 14, INK, "middle", "600")
text(256, 385, "보폭 −80 · 높이 90 · 주기 1300 · 듀티 0.32", 11.5, MUTE, "middle", "400", MONO)

box(56, 424, 400, 76, MUTE, "#ffffff", dash="5 4")
text(256, 448, "폰 웹 브라우저 실시간 튜닝", 13.5, INK, "middle", "600")
text(256, 467, "보폭 · 높이 · 주기 · 듀티 · 다리별 트림", 11.5, MUTE)
text(256, 486, "네 발 지지율과 무릎 각속도를 함께 표시, 정격 초과 시 경고", 11, MUTE)
path("M 256,424 L 256,400", sw=1.5, dash="5 4")

# 강화학습
box(512, 218, 458, 300, RL, "#f9f6fc", rx=10)
text(532, 244, "③ 강화학습 — 파이프라인 · 이식 판정", 15, RL, "start", "600")

box(538, 262, 406, 50, RL)
text(741, 282, "rl/gen_mjcf.py  →  rl/mjcf/spotmicro.xml", 13, INK, "middle", "600", MONO)
text(741, 300, "URDF 를 변환하지 않고 상수에서 생성한다", 11.5, MUTE)

arrow(741, 312, 741, 330)

box(538, 332, 406, 46, GATE, "#fdf4f3")
text(741, 351, "검증 게이트 8종  ·  make verify", 13.5, GATE, "middle", "700")
text(741, 369, "하나라도 실패하면 학습이 시작되지 않는다", 11.5, GATE)

arrow(741, 378, 741, 396)

box(538, 398, 406, 50, RL)
text(741, 418, "PPO 학습 (MuJoCo · Stable-Baselines3)", 13, INK, "middle", "600")
text(741, 436, "관측 enc 45차원  vs  hist 69차원 을 같은 조건에서 비교", 11.5, MUTE)

arrow(741, 448, 741, 466)

box(538, 468, 406, 46, RL)
text(741, 487, "정책  checkpoints/policy.zip", 13, INK, "middle", "600", MONO)
text(741, 505, "관절 각도 변위 12 출력 · 50 Hz 추론", 11.5, MUTE)

# ── 3. 합류 ──────────────────────────────────────────────────────────────────
path("M 256,500 L 256,556 L 480,556", sw=2.0, head=False)
path("M 741,514 L 741,556 L 522,556", sw=2.0, head=False)
path("M 500,556 L 500,586", sw=2.0)

box(250, 590, 500, 52, INK, "#f6f6f7", rx=8)
text(500, 613, "같은 서보 인터페이스 — 관절 각도 12", 15, INK, "middle", "700")
text(500, 632, "두 방식을 같은 하드웨어에서 직접 비교할 수 있다", 12, MUTE)

arrow(500, 642, 500, 670)

# ── 4. 하드웨어 ──────────────────────────────────────────────────────────────
box(30, 672, 940, 122, HW, "#fdfaf3", rx=10)
text(50, 698, "④ 실물", 15, HW, "start", "600")

hw = [
    (60, 250, "Raspberry Pi 4B 4GB", "Ubuntu 24.04 · aarch64"),
    (356, 250, "PCA9685 ×2", "I2C 0x40 / 0x41 · 쓰기 전용"),
    (652, 288, "서보 12개", "DS3235 ×9 · CLS6336HV ×2 · Futaba ×1  (6V)"),
]
for x, w, name, detail in hw:
    box(x, 710, w, 54, HW)
    text(x + w / 2, 732, name, 13.5, INK, "middle", "600")
    text(x + w / 2, 751, detail, 11, MUTE)
arrow(316, 737, 350, 737)
arrow(612, 737, 646, 737)

# 되돌아오는 화살표가 없다는 것 자체가 설계 제약이다
text(500, 783, "화살표가 한 방향뿐이다. 관절 위치를 되읽을 수 없어 표준 관측의 절반이 "
                "실물에 없고, 그래서 ③ 이 enc 와 hist 를 나눠 비교한다.", 11.5, GATE)

a("</svg>")

out = pathlib.Path(__file__).resolve().parent.parent / "docs" / "media" / "architecture.svg"
out.write_text("\n".join(o), encoding="utf-8")
print(f"{out}  ({out.stat().st_size:,} bytes)")
