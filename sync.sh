#!/usr/bin/env bash
# 로컬 코드를 CM4 로 밀어넣는다.
#
#   ./sync.sh          전송
#   ./sync.sh -n       dry-run (뭐가 갈지만 보여주고 전송 안 함)
#   ./sync.sh --pull   CM4 에서 rsync 흔적을 지우고 git pull (아래 설명)
#
# rsync 는 달라진 파일만 보낸다. -a 가 타임스탬프를 보존하므로
# 두 번째 실행부터는 실제로 바뀐 파일만 목록에 나온다.
#
# --- rsync 와 git 이 부딪히는 지점 -------------------------------------
#
# CM4 에도 이 저장소의 git 사본이 있다. rsync 는 git 을 모르고 파일을 덮어쓰므로,
# 나중에 CM4 에서 git pull 하면 이렇게 거부당한다:
#
#     error: Your local changes to the following files would be overwritten
#     error: The following untracked working tree files would be overwritten
#
# 내용이 달라서가 아니다. 밀어넣은 파일이 대개 커밋한 것과 같은 내용인데도,
# git 은 그것을 "설명되지 않은 변경" 으로 본다. 지울 것이 없는데 멈춘 상태다.
#
# --pull 이 그 상황을 정리한다. 다만 무턱대고 지우지 않고, CM4 의 각 파일이
# origin 의 같은 파일과 내용이 같은지 먼저 확인한다. 하나라도 다르면
# 멈추고 목록을 보여준다 - 그 경우는 로봇에서 직접 고친 것이 있다는 뜻이고,
# 그건 사람이 판단해야 한다.
#
# 튜닝 중에는 ./sync.sh 로 즉시 반영하고, 세션이 끝나면 커밋한 뒤
# ./sync.sh --pull 로 CM4 의 git 을 맞춰두면 두 경로가 어긋나지 않는다.
set -euo pipefail

REMOTE=${SPOT_REMOTE:-minodori@192.168.0.240}
DEST=${SPOT_DEST:-Projects/SpotMicroJetson/}
DIRS="RaspberryPi Kinematics Common"

if [ "${1:-}" = "--pull" ]; then
  ssh "$REMOTE" "cd '$DEST' && bash -s" <<'REMOTE_EOF'
set -euo pipefail
git fetch --quiet origin
BR=$(git rev-parse --abbrev-ref HEAD)
echo "브랜치 $BR, origin/$BR 과 대조"

DIFFER=0
UNTRACKED=()
while IFS= read -r line; do
  [ -z "$line" ] && continue
  st="${line:0:2}"; f="${line:3}"
  if git cat-file -e "origin/$BR:$f" 2>/dev/null &&
     git show "origin/$BR:$f" | diff -q - "$f" >/dev/null 2>&1; then
    # 내용이 origin 과 같다. 되돌려도 잃을 것이 없다.
    [ "$st" = "??" ] && UNTRACKED+=("$f")
  else
    echo "   다름: $f"
    DIFFER=1
  fi
done < <(git status --porcelain)

if [ "$DIFFER" = "1" ]; then
  echo
  echo "중단. 위 파일은 origin 과 내용이 다릅니다 - 로봇에서 직접 고쳤을 수 있습니다."
  echo "확인:  git diff -- <파일>     무시하고 진행하려면 직접 git checkout/clean"
  exit 1
fi

echo "로컬 변경이 전부 origin 과 동일합니다. 되돌리고 pull 합니다."
git checkout -- .
# 대조에서 안전하다고 확인된 미추적 파일만 지운다.
# git clean -fd 는 로그·메모처럼 확인하지 않은 것까지 쓸어간다.
for f in "${UNTRACKED[@]:-}"; do [ -n "$f" ] && rm -f -- "$f"; done
git pull --ff-only
echo "완료: $(git log --oneline -1)"
REMOTE_EOF
  exit 0
fi

rsync -avz --itemize-changes "$@" \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  $DIRS \
  "$REMOTE:$DEST"

cat <<'HINT'

CM4 에서 git pull 이 필요해지면 ./sync.sh --pull 을 쓰세요.
rsync 가 남긴 변경을 origin 과 대조해 안전할 때만 정리하고 당겨옵니다.
HINT
