#!/usr/bin/env bash
# 로컬 코드를 CM4 로 밀어넣는다.
#
#   ./sync.sh        전송
#   ./sync.sh -n     dry-run (뭐가 갈지만 보여주고 전송 안 함)
#
# rsync 는 달라진 파일만 보낸다. -a 가 타임스탬프를 보존하므로
# 두 번째 실행부터는 실제로 바뀐 파일만 목록에 나온다.
set -euo pipefail

REMOTE=${SPOT_REMOTE:-minodori@192.168.0.240}
DEST=${SPOT_DEST:-Projects/SpotMicroJetson/}

rsync -avz --itemize-changes "$@" \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  JetsonNano Kinematics Common \
  "$REMOTE:$DEST"
