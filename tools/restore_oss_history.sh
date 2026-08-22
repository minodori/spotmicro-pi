#!/usr/bin/env bash
# ⚠ 이 스크립트를 실행하지 마십시오. 낡았습니다. 이력 참고용으로만 둡니다.
#
# 2026-08-20 에 썼을 때 oss_spotmicro 는 orocapangyo 의 8/05 스냅샷이었고,
# 우리 작업은 minodori/SpotMicroJetson 에 따로 있었습니다. 그래서 [1/4] 의
# `git read-tree -m -u oroca/master` 로 트리를 통째로 맞추는 것이 맞았습니다.
#
# 그 뒤 PR #1·#2 로 우리 작업이 oss_spotmicro 에 들어왔습니다. 지금 실행하면
# rl/, Makefile, CONTRIBUTING.md, .github/, checkpoints/, RaspberryPi/ 이동이
# 전부 사라지고, [4/4] 가 우리 README 를 UPSTREAM_README 로 덮습니다.
#
# [2/4]~[4/4] 는 이미 다른 커밋으로 처리됐습니다. 지금 남은 것은 이력 기록뿐이고,
# 그것은 tools/merge_upstream_history.sh 한 줄이면 됩니다 — 트리를 건드리지
# 않고 상대 히스토리를 부모로만 기록합니다.

# =============================================================================
#  oss_spotmicro — 개발 히스토리 복원 (force push 불필요, PR 로 병합 가능)
#  팀 KINETIQ / 2026 오픈소스 개발자대회
#
#  현재 robertchoi/oss_spotmicro 의 main 은 커밋 1개
#  ("feat: initialize repository ...") 로 되어 있다. 세 가지 문제가 있다.
#
#    1. 저작자 표시 — upstream GPL 저작물 전체가 이 저장소에서 작성된 것처럼
#       git blame 에 남는다. README 는 FlorianWilk / KDY0523 을 크레딧하는데
#       커밋 히스토리는 정반대를 말한다.
#    2. 기여도 — 대회 운영규정 제6조5항은 개인별 기여도를 심사에 반영한다고
#       명시한다. orocapangyo 의 커밋 325개와 PR 48개가 여기엔 없다.
#    3. 최신성 — 2026-08-05 스냅샷이라 이후 수정이 빠져 있다. 특히
#       PCA9685 2번 보드 채널 매핑과 DS3230/DS3235 펄스폭 캘리브레이션.
#
#  ---------------------------------------------------------------------------
#  동작 원리
#  ---------------------------------------------------------------------------
#  히스토리를 '교체'하지 않고, 현재 커밋(142b142)을 조상으로 유지한 채
#  orocapangyo 히스토리를 병합한다. 따라서
#
#    - main 이 fast-forward 로 진행된다  -> force push 불필요
#    - 일반 PR 로 병합된다              -> 저장소 쓰기 권한 불필요
#    - 기존 커밋이 사라지지 않는다      -> 되돌릴 일이 없다
#
#  ---------------------------------------------------------------------------
#  사용법
#  ---------------------------------------------------------------------------
#    # (A) 저장소 소유자가 직접 실행하는 경우 — 가장 간단
#    bash restore_oss_history.sh https://github.com/robertchoi/oss_spotmicro.git
#    cd oss_spotmicro && git push origin history-restore:main
#
#    # (B) 포크에서 PR 을 보내는 경우
#    bash restore_oss_history.sh https://github.com/<본인>/oss_spotmicro.git
#    cd oss_spotmicro && git push origin history-restore
#    # -> GitHub 에서 robertchoi/oss_spotmicro 의 main 으로 PR 생성
# =============================================================================
set -euo pipefail

TARGET="${1:?사용법: bash $0 <oss_spotmicro 저장소 URL>}"
OROCA="https://github.com/orocapangyo/SpotMicroJetson.git"
DIR="${DIR:-oss_spotmicro}"

echo "==> 클론: $TARGET"
git clone --filter=blob:none "$TARGET" "$DIR"
cd "$DIR"

echo "==> orocapangyo 히스토리 가져오기"
git remote add oroca "$OROCA"
git fetch --filter=blob:none oroca master

BASE="$(git rev-parse HEAD)"
echo "==> 현재 main: $BASE"

echo "==> [1/4] 히스토리 병합 (현재 커밋을 조상으로 유지)"
git checkout -b history-restore "$BASE"
git merge --allow-unrelated-histories --no-commit -s ours oroca/master 2>/dev/null || true
# 트리를 orocapangyo 의 현재 상태와 정확히 일치시킨다.
# 이 저장소는 orocapangyo 의 구버전 스냅샷이므로 트리를 통째로 맞춰야 한다.
git read-tree -m -u oroca/master
git commit -q -m "chore: restore full development history

The initial commit of this repository imported the upstream tree as a
single squashed commit, which had three consequences:

  1. Attribution. Every file appeared to be authored here, even though
     most of the tree originates from FlorianWilk/SpotMicroAI (GPL-3.0)
     and the SpotMicro mechanical design by KDY0523 (CC BY 3.0).
  2. Contribution record. The 325 commits and 48 pull requests of
     collaboration in orocapangyo/SpotMicroJetson were not visible here.
  3. Staleness. The import was a snapshot taken on 2026-08-05, so later
     fixes were missing - notably the PCA9685 board #2 channel mapping
     and the DS3230/DS3235 pulse width calibration.

This merge brings in the complete history of orocapangyo/SpotMicroJetson
and sets the tree to its current state. The original squashed commit is
retained as a parent, so no history is rewritten and no force push is
required."

echo "==> [2/4] OS/빌드 아티팩트 추적 해제"
cat > .gitignore <<'EOF'
# Python
*.pyc
__pycache__/
*.egg-info/
.venv/
venv/
env/
.env

# Editors / OS
.vscode/settings.json
.vscode/c_cpp_properties.json
.DS_Store
Thumbs.db

# Training artifacts (checkpoints are published separately)
runs/
logs/
tensorboard/
EOF
git ls-files | grep -E '(^|/)\.DS_Store$' | while read -r f; do git rm -q --cached "$f"; done || true
git rm -rq --cached JetsonNano/__pycache__ Simulation/gym_spotmicroai.egg-info 2>/dev/null || true
git add .gitignore
git commit -q -m "chore: stop tracking OS and build artifacts

Remove .DS_Store, compiled __pycache__ bytecode and generated .egg-info
metadata from version control, and extend .gitignore so they do not come
back. Also ignore training run/log directories."

echo "==> [3/4] 출품 범위를 참가팀 기여로 한정"
git rm -rq study/Jonghyeon study/kyungho study/bangsajang-cmyk \
            study/kim study/shin_eunji study/archer
git commit -q -m "chore: scope working tree to the KINETIQ team's contributions

This repository is the contest entry of team KINETIQ (robert, iru-han,
minho). It is built on orocapangyo/SpotMicroJetson, a shared study-group
repository that also hosts work by members who are not part of the entry.

Their files are removed from the working tree so the scope of the entry is
unambiguous. They are NOT removed from the commit history: every commit and
every author remains intact and attributable, and the study-group repository
stays the canonical home of that work.

  kept     study/minho  study/robert  study/iru-han
  removed  study/Jonghyeon  study/kyungho  study/bangsajang-cmyk
           study/kim  study/shin_eunji  study/archer"

echo "==> [4/4] 문서 재배치"
mkdir -p docs/hardware
git mv Docs/circuit_diagram.fzz  docs/hardware/circuit_diagram_v1.0.fzz
git mv Docs/circuit_diagram2.fzz docs/hardware/circuit_diagram_v1.1.fzz
git rm -q "Docs/Untitled Sketch 2.fzz" \
          "Docs/2026 오픈소스 개발자대회 결과보고서_가안(Pony).docx" \
          "Docs/2026 오픈소스 개발자대회 결과보고서_가안(Pony).pdf" \
          "Docs/KINETIQ_목요일_팀미팅_안건.md"
git mv README.md docs/UPSTREAM_README.md
git commit -q -m "docs: reorganise hardware documents and preserve upstream README

- Docs/*.fzz -> docs/hardware/ (Fritzing wiring diagrams, versioned)
- README.md  -> docs/UPSTREAM_README.md (upstream text preserved verbatim
  before it is replaced by this project's own README)
- drop internal working drafts (report draft, meeting agenda) from the
  public repository; they are not part of the deliverable"

echo
echo "============================================================"
echo " 완료 — 아직 push 하지 않았습니다"
echo "============================================================"
git log --format='%h  %<(14)%an  %s' -5
echo
echo "커밋 수      : $(git rev-list --count HEAD)"
echo "추적 파일    : $(git ls-files | wc -l)"
echo "이전 main 이 조상인가 : $(git merge-base --is-ancestor "$BASE" HEAD && echo 'YES (force push 불필요)')"
echo
echo "기여자별 커밋:"
git shortlog -sn HEAD | head -10
echo
echo "------------------------------------------------------------"
echo " 다음 단계"
echo "------------------------------------------------------------"
echo "  소유자라면:  cd $DIR && git push origin history-restore:main"
echo "  포크라면  :  cd $DIR && git push origin history-restore"
echo "               -> GitHub 에서 main 으로 PR 생성"
echo "------------------------------------------------------------"
