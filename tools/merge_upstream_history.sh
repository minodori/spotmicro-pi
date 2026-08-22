#!/usr/bin/env bash
# oss_spotmicro 에 orocapangyo 개발 이력을 조상으로 기록한다.
#
#   bash tools/merge_upstream_history.sh https://github.com/<본인>/oss_spotmicro.git
#
# push 는 하지 않는다. 브랜치만 만들고 멈춘다 — 사람이 확인하고 올린다.
#
# --- restore_oss_history.sh 와 무엇이 다른가 --------------------------------
#
# 그 스크립트는 `git read-tree -m -u oroca/master` 로 워킹트리를 orocapangyo
# 상태와 일치시킨다. 2026-08-20 에는 맞았다 — 그때 oss_spotmicro 는
# orocapangyo 의 8/05 스냅샷이었고 우리 작업은 다른 저장소에 있었다.
# PR #1·#2 로 우리 작업이 들어온 지금 실행하면 rl/, Makefile, CONTRIBUTING.md,
# .github/, checkpoints/, RaspberryPi/ 가 전부 사라진다.
#
# 여기서는 `-s ours` 만 쓴다. 두 부모를 기록하되 트리는 현재 것을 그대로 둔다.
#
# --- 검증한 것 (2026-08-22, 버리는 클론에서) --------------------------------
#
#   커밋      5 -> 331           orocapangyo 325개가 조상이 됨
#   파일      293 -> 293         트리 차이 0 줄
#   기여자    3명 -> 8명 이상    kimsooyoung 69, gm2256 62, iru-han 50 ...
#   push      fast-forward       force push 불필요
#
# --- 해결되지 않는 것 --------------------------------------------------------
#
#   git blame 은 그대로다. Simulation/spotmicroai.py 337줄이 병합 전후 모두
#   robertchoi(squash 커밋)로 남는다. `-s ours` 는 트리를 안 건드리므로
#   blame 이 따라갈 다른 경로가 생기지 않는다. 이것을 고치려면 이력을 다시
#   써야 하고(graft/filter-repo), 기존 SHA 가 전부 바뀐다.
#
#   따라서 GPL 저작자 표시는 blame 이 아니라 NOTICE/LICENSE 문서가 담당한다.
#   보고서나 NOTICE 에 "blame 에 원작자가 나온다" 고 쓰면 사실과 다르다.
#
# --- 대가 --------------------------------------------------------------------
#
#   전체 클론이 161MB -> 682MB 가 된다 (STL·이미지 이력이 따라온다).
#   `git clone --depth 1` 은 영향받지 않는다.
#
# --- 포크가 낡았을 때 --------------------------------------------------------
#
#   PR 을 보낼 포크를 그냥 클론하면 안 된다. 2026-08-22 에 minodori/oss_spotmicro
#   는 커밋 1개·파일 207개로 PR #1·#2 머지 전 상태였고, 그 위에서 병합하면
#   두 PR 의 내용이 전부 삭제로 나오는 브랜치가 만들어진다.
#
#   상위 저장소에서 클론해 병합하고, 포크는 push 대상으로만 쓴다:
#     git clone https://github.com/robertchoi/oss_spotmicro.git
#     git remote add fork git@github.com:<본인>/oss_spotmicro.git
#     ...병합...
#     git push fork history-restore
# =============================================================================
set -euo pipefail

TARGET="${1:?사용법: bash $0 <oss_spotmicro 저장소 URL>}"
OROCA="${OROCA:-https://github.com/orocapangyo/SpotMicroJetson.git}"
DIR="${DIR:-oss_spotmicro_history}"
BRANCH="${BRANCH:-history-restore}"

[ -e "$DIR" ] && { echo "이미 있습니다: $DIR"; exit 1; }

echo "==> 클론: $TARGET"
git clone --quiet "$TARGET" "$DIR"
cd "$DIR"

echo "==> 업스트림 이력 가져오기: $OROCA"
git remote add oroca "$OROCA"
git fetch --quiet oroca master

before_c=$(git rev-list --count HEAD)
before_f=$(git ls-files | wc -l)
base=$(git rev-parse --abbrev-ref HEAD)

echo "==> 병합 (트리는 건드리지 않음)"
git checkout --quiet -b "$BRANCH"
git merge --quiet -s ours --allow-unrelated-histories oroca/master \
  -m "chore: record the upstream development history as an ancestor

This repository began as a single squashed import, so the 325 commits that
produced the inherited code were not part of its history. The contest rules
weigh individual contribution (제6조5항), and none of that work was visible.

Merged with -s ours: both parents are recorded and the tree is untouched, so
this fast-forwards and needs no force push. It does not change git blame -
the squashed commit still owns those lines. Attribution is carried by NOTICE
and LICENSE, not by blame."

echo
echo "  커밋   $before_c -> $(git rev-list --count HEAD)"
echo "  파일   $before_f -> $(git ls-files | wc -l)"
echo "  트리   $(git diff --stat "$base" HEAD | wc -l) 줄 차이 (0 이어야 정상)"
echo "  기여자 $(git shortlog -sn HEAD | wc -l) 명"
echo
echo "확인한 뒤 직접 올리십시오:"
echo "    cd $DIR && git push origin $BRANCH"
echo "    -> GitHub 에서 robertchoi/oss_spotmicro 의 main 으로 PR"
