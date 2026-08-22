#!/usr/bin/env bash
# =============================================================================
#  PR #1 만들기 — minho 작업을 robertchoi/oss_spotmicro 로 보내기
#
#  왜 브랜치를 통째로 push 하지 않는가
#  ---------------------------------------------------------------------------
#  minodori/SpotMicroJetson 의 minho 브랜치와 oss_spotmicro 의 main 은 서로
#  다른 시점에서 갈라져 공통 조상이 없다. 브랜치를 통째로 밀면
#
#    - Robert 의 urdf/spot_micro.xml (MuJoCo 모델), pyproject.toml, uv.lock 이 삭제되고
#    - Robert 가 지운 Simulation/isaac_*.py 가 되살아난다
#
#  그래서 oss_spotmicro 의 main 에서 브랜치를 따고, 내 작업 파일만 골라 얹는다.
#
#  안전성: 기존 로컬 저장소를 수정하지 않는다. 새 폴더에 클론해서 작업하고,
#          push 는 하지 않는다 (명령만 출력).
#
#  사용법:  bash make_pr1.sh
# =============================================================================
set -euo pipefail

SRC="${SRC:-$HOME/Projects/SpotMicroJetson}"     # 내 작업이 있는 로컬 저장소
BRANCH="${BRANCH:-minho}"                        # 가져올 브랜치
FORK="${FORK:-https://github.com/minodori/oss_spotmicro.git}"
WORK="${WORK:-$HOME/Projects/oss_spotmicro_pr}"  # 작업 폴더 (새로 만듦)

# ---------------------------------------------------------------------------
# PR 에 담을 경로. Robert 의 파일과 겹치지 않는 것만 고른다.
# ---------------------------------------------------------------------------
INCLUDE=(
  study/minho          # 개발 일지 work01~11
  Common               # 보행 파라미터, 키보드/웹 조작
  Kinematics           # 역기구학 (실측 링크 길이 반영본)
  JetsonNano           # 서보 제어 (PCA9685 채널 매핑 수정 포함)
  Docs                 # 배선도 .fzz — 아래에서 docs/hardware 로 옮긴다
)

# 위 경로 안에 있어도 PR 에서 빼야 하는 것들
EXCLUDE_GLOBS=(
  '*/__pycache__/*'                              # 컴파일 캐시
  '*.pyc'
  'Docs/*.docx' 'Docs/*.pdf' 'Docs/*.md'         # 결과보고서 초안, 미팅 안건 (내부 문서)
  'Docs/Untitled Sketch 2.fzz'                   # 미사용 스케치
  'study/minho/images/w02_RightLeg_Test.mp4'     # 25.8MB, 참조하는 문서 없음(CDN 으로 교체됨)
  'study/minho/images/SpotMicro_new.xlsx'        # 9.8MB, 참조하는 문서 없음
)

echo "==> 소스   : $SRC ($BRANCH 브랜치)"
echo "==> 포크   : $FORK"
echo "==> 작업폴더: $WORK"
echo

# --- 사전 점검 -------------------------------------------------------------
[ -d "$SRC/.git" ] || { echo "오류: $SRC 가 git 저장소가 아닙니다"; exit 1; }
git -C "$SRC" rev-parse --verify "$BRANCH" >/dev/null 2>&1 \
  || { echo "오류: $BRANCH 브랜치가 없습니다"; exit 1; }

DIRTY=$(git -C "$SRC" status --porcelain -- "${INCLUDE[@]}" 2>/dev/null | grep -v '^??' | wc -l)
if [ "$DIRTY" -gt 0 ]; then
  echo "!! 커밋되지 않은 변경이 $DIRTY 건 있습니다. 이 내용은 PR 에 포함되지 않습니다."
  git -C "$SRC" status --short -- "${INCLUDE[@]}" | grep -v '^??' | sed 's/^/     /'
  echo
  read -rp "그래도 계속할까요? 먼저 커밋하려면 n 을 누르세요 [y/N] " ans
  [ "$ans" = "y" ] || { echo "중단했습니다. $SRC 에서 커밋 후 다시 실행하세요."; exit 1; }
  echo
fi

# --- 포크 클론 -------------------------------------------------------------
rm -rf "$WORK"
echo "==> 포크 클론 중 (수 분 걸릴 수 있습니다)"
git clone --quiet "$FORK" "$WORK"
cd "$WORK"

# 포크가 오래됐을 수 있으므로 원본 main 을 기준으로 삼는다
git remote add upstream https://github.com/robertchoi/oss_spotmicro.git
git fetch --quiet upstream main
git checkout --quiet -B minho-work upstream/main
echo "==> 기준: upstream/main ($(git rev-parse --short HEAD))"

# --- 내 작업 파일 복사 -----------------------------------------------------
echo "==> 작업 파일 복사"
TMP=$(mktemp -d)
git -C "$SRC" archive "$BRANCH" "${INCLUDE[@]}" | tar -x -C "$TMP"

for g in "${EXCLUDE_GLOBS[@]}"; do
  find "$TMP" -path "$TMP/$g" -delete 2>/dev/null || true
done
find "$TMP" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

cp -r "$TMP"/. .
rm -rf "$TMP"

# 배선도는 docs/hardware 로 정리해서 넣는다
if [ -f "Docs/circuit_diagram.fzz" ]; then
  mkdir -p docs/hardware
  mv Docs/circuit_diagram.fzz  docs/hardware/circuit_diagram_v1.0.fzz
  mv Docs/circuit_diagram2.fzz docs/hardware/circuit_diagram_v1.1.fzz 2>/dev/null || true
fi
rmdir Docs 2>/dev/null || true

# 이미 추적 중인 캐시 파일 정리
git ls-files | grep -E '(^|/)(__pycache__/|\.DS_Store$)' \
  | while read -r f; do git rm -q --cached "$f"; done || true

# --- 커밋 -----------------------------------------------------------------
if git diff --quiet && git diff --cached --quiet && [ -z "$(git status --porcelain)" ]; then
  echo "변경사항이 없습니다. 이미 반영되어 있는 것 같습니다."; exit 0
fi

git add -A
git commit -q -m "Add minho's development journal and hardware control updates

Brings this repository up to date with the work done in
minodori/SpotMicroJetson.

Development journal (study/minho/work01-11)
  Weekly record of the build: servo selection and comparison, right-leg
  assembly, Jetson Nano to Raspberry Pi 5 migration, a power design that
  failed and why, the PCA9685 daisy-chain rework, servo pin mapping, and
  the measurements needed to fit components to the mounting plate.

Hardware control
  The copy in this repository was a snapshot taken on 2026-08-05 and was
  missing later fixes, most importantly:
    - PCA9685 board #2 channel mapping
    - DS3230 / DS3235 pulse width calibration
    - I2C pin names for the Raspberry Pi 5
    - link lengths measured from the assembled robot, and the kinematic
      model corrected to match
    - gait tuning from a phone instead of the keyboard

Wiring diagrams
  Docs/*.fzz -> docs/hardware/, versioned by revision.

Not included: internal working drafts, build caches, and two large media
files that no document references."

# --- 결과 -----------------------------------------------------------------
echo
echo "============================================================"
echo " 완료 — 아직 push 하지 않았습니다"
echo "============================================================"
git show --stat --oneline HEAD | head -25
echo "  ..."
echo
echo "추가/수정된 파일 수: $(git show --name-only --format= HEAD | wc -l)"
echo "Robert 파일 보존 확인:"
for f in urdf/spot_micro.xml pyproject.toml uv.lock; do
  git cat-file -e HEAD:"$f" 2>/dev/null && echo "  OK    $f" || echo "  없음! $f"
done
echo "Isaac 스크립트 되살아나지 않았는지:"
for f in Simulation/isaac_hello.py Simulation/isaac_spotmicro.py; do
  git cat-file -e HEAD:"$f" 2>/dev/null && echo "  되살아남! $f" || echo "  OK    $f (없음)"
done
echo
echo "------------------------------------------------------------"
echo " 다음 단계"
echo "------------------------------------------------------------"
echo "  1) 내용 확인:  cd $WORK && git show --stat HEAD"
echo "  2) push     :  cd $WORK && git push origin minho-work"
echo "  3) PR 생성  :  https://github.com/robertchoi/oss_spotmicro/compare/main...minodori:minho-work"
echo "------------------------------------------------------------"
