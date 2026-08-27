#!/usr/bin/env bash
# =============================================================================
#  출품 저장소(robertchoi/oss_spotmicro)로 보낼 브랜치를 다시 만든다.
#
#  왜 필요한가
#  ---------------------------------------------------------------------------
#  minodori/SpotMicroJetson 과 robertchoi/oss_spotmicro 는 공통 조상이 없다
#  (git merge-base 가 비어 있다). 그래서 브랜치를 그대로 밀 수 없고, 저쪽
#  main 을 부모로 삼아 이쪽 트리를 통째로 얹은 커밋 하나를 만든다.
#
#  저쪽 이력(PR #1, #2)은 그대로 남고, 이쪽 318 커밋의 근거는
#  minodori/SpotMicroJetson 과 트리에 실려 가는 docs/결정.md 에 남는다.
#
#  이 스크립트가 필요한 이유는 트리가 계속 바뀌기 때문이다. 제출 전에 보고서를
#  고치거나 GIF 를 넣으면 이 브랜치를 다시 만들어야 하고, 손으로 하면
#  commit-tree 의 부모를 틀리기 쉽다.
#
#  push 는 하지 않는다. 명령만 출력한다 — 접수번호가 걸린 저장소로 가는 길이라
#  마지막 한 줄은 사람이 친다.
#
#  사용법:  bash tools/make_submit_branch.sh [브랜치이름]     기본 pr3-final
# =============================================================================
set -euo pipefail

BRANCH="${1:-pr3-final}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRDIR="${SPOT_PR_DIR:-$HOME/Projects/oss_spotmicro_pr}"
UPSTREAM_URL="https://github.com/robertchoi/oss_spotmicro.git"

cd "$HERE"

if [ -n "$(git status --porcelain)" ]; then
  echo "커밋되지 않은 변경이 있습니다. 먼저 정리하십시오:"
  git status --short
  exit 1
fi

# 저쪽 main 을 최신으로. 리모트가 없으면 만든다.
git remote get-url oss >/dev/null 2>&1 || git remote add oss "$UPSTREAM_URL"
git fetch -q oss
BASE="$(git rev-parse oss/main)"
echo "출품 저장소 main : $(git log --oneline -1 "$BASE")"
echo "우리 트리        : $(git log --oneline -1 minho)"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
cat > "$TMP" <<'MSG'
Bring the submission repository up to the report

The registered URL is this repository and 구동및시연 tells a judge to clone it
and run make verify, so what is here has to be what the report describes.

The two histories have no common ancestor, so this lands as a single commit
whose tree is minodori/SpotMicroJetson at minho. The full history, and the
reasoning behind each change, stays there and in docs/결정.md, which ships in
this tree.

JetsonNano/ is gone because the board is a Raspberry Pi and the directory was
renamed; the mujoco_menagerie submodule goes with it, used only by one study
script that handles its absence.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG

SHA="$(git commit-tree "$(git rev-parse minho^{tree})" -p "$BASE" -F "$TMP")"
git branch -f submit "$SHA"
echo "커밋 생성 : $(git rev-parse --short "$SHA")  (부모 = 출품 main)"

# PR 클론으로 옮긴다. 그쪽 origin 이 minodori/oss_spotmicro 포크다.
if [ -d "$PRDIR/.git" ]; then
  git -C "$PRDIR" fetch -q "$HERE" submit
  git -C "$PRDIR" branch -f "$BRANCH" FETCH_HEAD
  echo "PR 클론 브랜치 : $PRDIR  ->  $BRANCH"
else
  echo "PR 클론이 없습니다: $PRDIR  (SPOT_PR_DIR 로 지정 가능)"
  exit 1
fi

cat <<HINT

다음은 사람이 합니다.

  cd $PRDIR
  git push origin $BRANCH

  https://github.com/robertchoi/oss_spotmicro/compare/main...minodori:oss_spotmicro:$BRANCH?expand=1

그다음 robert 님이 머지합니다.
HINT
