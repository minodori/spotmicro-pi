"""시연 영상용 전체 자막 카드. 1920x1080.

    python tools/gen_video_cards.py

docs/media/ 에 두 장을 쓴다.

  cut3_purpose.svg   3번 — 목적 카드. 이 영상이 무엇을 말하는지 먼저 선언한다
  cut20_three.svg    20번 — 시뮬이 실물을 맞히는가. 세 줄 표

캡컷에서 글자를 얹는 대신 이미지로 만든 이유가 있다. 줄 간격과 강조 위치를 매번
손으로 맞추면 카드마다 달라지고, 여러 번 나올 때 산만해진다. 여기서 한 번 정해
두면 편집에서는 넣고 길이만 늘리면 된다.
"""
import pathlib

F = "Noto Sans CJK KR, sans-serif"
MONO = "Noto Sans Mono CJK KR, monospace"
BG = "#0d0d10"
INK = "#ffffff"
DIM = "#8b8b95"
ACC = "#4aa3ff"
OK = "#3ecf8e"
W, H = 1920, 1080
DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs" / "media"


def svg(body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'width="{W}" height="{H}"><rect width="{W}" height="{H}" fill="{BG}"/>'
            + "".join(body) + "</svg>")


def t(x, y, s, size, fill=INK, anchor="middle", weight="500", font=F):
    return (f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{fill}"'
            f' font-weight="{weight}" text-anchor="{anchor}">{s}</text>')


def mark(x=90, y=88):
    """좌상단 워드마크. 템플릿과 같은 자리."""
    return [t(x, y, "K I N E T I Q", 30, DIM, "start", "600"),
            f'<line x1="{x}" y1="{y+18}" x2="{x+218}" y2="{y+18}" stroke="{DIM}" stroke-width="2"/>']


# ── 3번. 목적 카드 ──────────────────────────────────────────────────────────
o = mark()
o += [t(960, 330, "상용 4족보행 로봇은 수천만 원입니다", 60, DIM),
      t(960, 415, "설계와 코드가 공개된 대안이 있습니다", 60, DIM),
      t(960, 590, "저희는 그것을 그대로 따라 만들었지만", 62, INK),
      t(960, 675, "걷지 않았습니다", 76, INK, weight="700"),
      t(960, 830, "왜 걷지 않는지 알아내", 58, ACC),
      t(960, 905, "누구나 재현할 수 있게 만들었습니다", 58, ACC, weight="600")]
(DOCS / "cut3_purpose.svg").write_text(svg(o), encoding="utf-8")

# ── 20번. 세 층 일치 ────────────────────────────────────────────────────────
o = mark()
o += [t(960, 200, "시뮬레이션이 실물을 맞히는가", 62, INK, weight="700"),
      t(960, 262, "세 가지로 확인했습니다", 36, DIM)]

rows = [("발끝 좌표", "시뮬 순기구학 vs 제어 코드", "0.0000 mm", OK),
        ("무릎 각속도", "실물 323 vs 시뮬 318 °/s", "2 %", OK),
        ("전진 속도", "같은 궤적을 재생, 두 설정", "8 % 이내", OK)]
for i, (label, how, val, col) in enumerate(rows):
    y = 400 + i * 175
    o += [f'<line x1="240" y1="{y-58}" x2="1680" y2="{y-58}" stroke="#26262e" stroke-width="2"/>',
          t(300, y, label, 52, INK, "start", "600"),
          t(300, y + 48, how, 32, DIM, "start"),
          t(1620, y + 8, val, 60, col, "end", "700")]

o += [f'<line x1="240" y1="{400+3*175-58}" x2="1680" y2="{400+3*175-58}" stroke="#26262e" stroke-width="2"/>',
      t(960, 990, "실물이 들어가는 것은 아래 두 줄입니다", 34, DIM)]
(DOCS / "cut20_three.svg").write_text(svg(o), encoding="utf-8")

for n in ("cut3_purpose", "cut20_three"):
    p = DOCS / f"{n}.svg"
    print(f"  {p.relative_to(DOCS.parent.parent)}  ({p.stat().st_size:,} bytes)")
