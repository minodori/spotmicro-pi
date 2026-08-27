"""시연 영상 11번 컷 — 파이프라인 도식. 1920x1080.

    python tools/gen_pipeline_cut.py

docs/media/cut11_pipeline.svg 를 쓴다. PNG 가 필요하면

    libreoffice --headless --convert-to png --outdir docs/media docs/media/cut11_pipeline.svg

보고서의 architecture.png 를 그대로 쓰지 않는 이유가 있다. 그쪽은 1000x822 에 네
구획이 들어가 있어 종이에서는 읽히지만 폰 화면에서 10초 안에는 못 읽는다. 영상은
한 화면에 한 가지만 말해야 한다.

여기서 말하는 것은 하나다 — **전에는 세 곳에 따로 있었고 지금은 한 곳에서 갈라진다.**
왼쪽을 흐리게 두고 오른쪽을 선명하게 해서 대비로 읽히게 한다.
"""
import pathlib

F = "Noto Sans CJK KR, sans-serif"
MONO = "Noto Sans Mono CJK KR, monospace"

BG = "#0d0d10"       # 어두운 배경. 영상 다른 컷과 톤을 맞춘다
DIM = "#5a5a62"      # 이전 구조
DIMBOX = "#2a2a30"
LIVE = "#ffffff"     # 지금 구조
ACC = "#4aa3ff"      # 갈라지는 화살표
OK = "#3ecf8e"       # 검증

W, H = 1920, 1080
o = []
a = o.append


def box(x, y, w, h, stroke, fill="none", sw=3, rx=10, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"'
      f' stroke="{stroke}" stroke-width="{sw}"{d}/>')


def text(x, y, s, size, fill, anchor="middle", weight="500", font=F, op=1.0):
    a(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{fill}"'
      f' font-weight="{weight}" text-anchor="{anchor}" opacity="{op}">{s}</text>')


a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
a('<defs>'
  f'<marker id="ad" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5"'
  f' orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{DIM}"/></marker>'
  f'<marker id="al" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5"'
  f' orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{ACC}"/></marker>'
  '</defs>')
a(f'<rect width="{W}" height="{H}" fill="{BG}"/>')

# ── 왼쪽. 이전 구조 ─────────────────────────────────────────────────────────
text(430, 150, "이전", 52, DIM, weight="700")
text(430, 205, "세 곳에 따로 적혀 있었다", 34, DIM)
text(430, 252, "몸통 · 대퇴 · 하퇴", 26, DIM, op=0.75)

for i, (label, val) in enumerate((("URDF", "186 · 120.4 · 135"),
                                  ("발끝 목표", "140 · — · —"),
                                  ("역기구학", "140 · 100 · 100"))):
    y = 320 + i * 150
    box(180, y, 500, 110, DIM, DIMBOX, sw=2)
    text(430, y + 45, label, 34, DIM, weight="600")
    text(430, y + 85, val, 30, DIM, font=MONO)

text(430, 850, "서로 이어져 있지 않다", 30, DIM)
text(430, 898, "한 곳만 고치면 나머지는 그대로", 30, DIM)

# 가운데 구분선
a(f'<line x1="{W//2}" y1="120" x2="{W//2}" y2="960" stroke="#26262e" stroke-width="2"/>')

# ── 오른쪽. 지금 구조 ───────────────────────────────────────────────────────
text(1440, 150, "지금", 52, LIVE, weight="700")
text(1440, 205, "한 곳에서 갈라진다", 34, ACC)

box(1160, 280, 560, 120, ACC, "#12243a", sw=4)
text(1440, 328, "실측값 한 곳", 42, LIVE, weight="700")
text(1440, 372, "Kinematics/kinematics.py", 26, ACC, font=MONO)

# 갈라지는 화살표
a(f'<path d="M 1440,400 L 1440,470" fill="none" stroke="{ACC}" stroke-width="4"/>')
a(f'<path d="M 1240,470 L 1640,470" fill="none" stroke="{ACC}" stroke-width="4"/>')
a(f'<path d="M 1240,470 L 1240,530" fill="none" stroke="{ACC}" stroke-width="4" marker-end="url(#al)"/>')
a(f'<path d="M 1640,470 L 1640,530" fill="none" stroke="{ACC}" stroke-width="4" marker-end="url(#al)"/>')

box(1060, 545, 360, 105, LIVE, "none", sw=3)
text(1240, 590, "역기구학", 34, LIVE, weight="600")
text(1240, 628, "실물 제어", 26, DIM)

box(1460, 545, 360, 105, LIVE, "none", sw=3)
text(1640, 585, "시뮬레이션 모델", 32, LIVE, weight="600")
text(1640, 623, "자동 생성", 26, DIM)

a(f'<path d="M 1640,650 L 1640,720" fill="none" stroke="{OK}" stroke-width="4" marker-end="url(#al)"/>')
box(1460, 735, 360, 105, OK, "#0f2a20", sw=4)
text(1640, 780, "검증 8항목", 34, OK, weight="700")
text(1640, 818, "기하 0.0000 mm", 26, OK, font=MONO)

text(1440, 900, "사람이 옮겨 적는 단계가 없다", 32, LIVE)

a("</svg>")

out = pathlib.Path(__file__).resolve().parent.parent / "docs" / "media" / "cut11_pipeline.svg"
out.write_text("\n".join(o), encoding="utf-8")
print(f"{out}  ({out.stat().st_size:,} bytes)")
