#!/usr/bin/env bash
# 팀 텔레그램 그룹으로 주고받는다. CTO/COO 에이전트 간 연락용.
#
#   tools/tg.sh send cto "내용"      보내기
#   tools/tg.sh recv                 새 메시지 읽기 (offset 자동 관리)
#   tools/tg.sh recv 60              long polling 60초
#
# 토큰은 저장소에 두지 않는다. ~/.spotmicro_telegram 에서 읽는다 —
# gait_params.py 가 ~/.spotmicro_gait.json 을 쓰는 것과 같은 이유로,
# 실행 환경에 속하는 값이지 코드가 아니다. 이 저장소는 공개된다.
#
#   $ cat ~/.spotmicro_telegram
#   TOKEN=123456:AA...
#   CHAT_ID=-5417939438
#   $ chmod 600 ~/.spotmicro_telegram
set -euo pipefail

CONF="${SPOT_TG_CONF:-$HOME/.spotmicro_telegram}"
[ -f "$CONF" ] || { echo "설정이 없습니다: $CONF (위 주석 참조)" >&2; exit 1; }
# shellcheck disable=SC1090
. "$CONF"
: "${TOKEN:?$CONF 에 TOKEN 이 없습니다}"
: "${CHAT_ID:?$CONF 에 CHAT_ID 가 없습니다}"

API="https://api.telegram.org/bot$TOKEN"
OFFSET_FILE="${SPOT_TG_OFFSET:-$HOME/.spotmicro_telegram.offset}"

case "${1:-}" in
send)
  who="${2:?send <cto|coo|mh> <내용>}"; shift 2
  curl -s "$API/sendMessage" -d "chat_id=$CHAT_ID" \
       --data-urlencode "text=[$who] $*" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print('보냄' if d.get('ok') else d)"
  ;;
recv)
  # 자기 태그가 붙은 것은 건너뛴다 (에코 방지). 걸러낸 뒤에도 offset 은 올린다 —
  # 안 올리면 같은 메시지를 매번 다시 받는다.
  off=$(cat "$OFFSET_FILE" 2>/dev/null || echo 0)
  curl -s "$API/getUpdates?offset=$off&timeout=${2:-0}" | python3 -c "
import json, sys, os
d = json.load(sys.stdin)
if not d.get('ok'):
    print(d); raise SystemExit(1)
r = d.get('result', [])
if r:
    open(os.path.expanduser('$OFFSET_FILE'), 'w').write(str(r[-1]['update_id'] + 1))
skip = os.environ.get('TG_SELF', '').lower()
n = 0
for u in r:
    m = u.get('message') or u.get('edited_message') or {}
    t = (m.get('text') or '').strip()
    if not t:
        continue
    if skip and t.lower().startswith(f'[{skip}]'):
        continue
    who = m.get('from', {}).get('first_name', '?')
    print(f'{t}    -- {who}')
    n += 1
print(f'(새 메시지 {n}건, 전체 {len(r)}건)' if r else '(새 메시지 없음)')
"
  ;;
*)
  sed -n '2,9p' "$0"; exit 1 ;;
esac
