"""보행 파라미터 조정용 웹 UI.

로봇을 보면서 조작해야 하는데 터미널을 동시에 볼 수 없다는 문제를 푼다.
폰으로 http://<로봇IP>:8080 에 접속하면 손에 들고 조작할 수 있다.

제어 루프(39Hz)는 건드리지 않는다. 데몬 스레드로 HTTP 서버를 띄우고
기존 command_status 큐를 키보드 입력과 같이 쓴다.
표준 라이브러리만 사용하므로 로봇에 추가 패키지가 필요 없다.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from Common.gait_params import DEFAULTS
from Common.multiprocess_kb import TWIST_WARN_RATIO

LEGS = ("FL", "FR", "RL", "RR")

PAGE = """<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SpotMicro</title><style>
*{box-sizing:border-box}
body{margin:0;padding:10px;font:15px/1.4 system-ui,sans-serif;background:#15171c;color:#e8e8ea}
h2{margin:4px 0 10px;font-size:16px;font-weight:600}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px}
.leg{background:#22252c;border-radius:10px;padding:10px;text-align:center}
.leg .n{font-size:12px;color:#9aa0aa}
.leg .v{font-size:26px;font-weight:700;margin:2px 0 6px;font-variant-numeric:tabular-nums}
button{font:inherit;color:#e8e8ea;background:#333842;border:0;border-radius:8px;
 padding:12px 0;width:46%;font-size:19px;font-weight:700;cursor:pointer;touch-action:manipulation}
button:active{background:#4a5261}
.row{display:flex;gap:8px;align-items:center;margin:8px 0}
.row label{width:74px;color:#9aa0aa;font-size:13px}
.row input[type=range]{flex:1}
.row .rv{width:56px;text-align:right;font-variant-numeric:tabular-nums}
.bar{display:flex;gap:8px;margin:10px 0}
.bar button{width:auto;flex:1;padding:14px 0}
.pad{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:10px 0}
.pad button{width:100%;padding:16px 0;font-size:17px}
.stop{background:#7a2b2b}
.warn{background:#6b4a13;border-radius:8px;padding:8px;margin:8px 0;font-size:13px;display:none}
.hint{color:#7d838d;font-size:12px;margin:-4px 0 10px 82px}
.hint2{color:#7d838d;font-size:12px;margin:-4px 0 10px 2px}
.sub{font-weight:400;color:#9aa0aa;font-size:13px}
.st{background:#22252c;border-radius:10px;padding:10px;font-size:13px;color:#9aa0aa}
.st b{color:#e8e8ea;font-variant-numeric:tabular-nums}
</style></head><body>

<h2>다리별 트림 (mm)</h2>
<div class="grid" id="legs"></div>
<div class="warn" id="warn"></div>

<h2>기울기 <span class="sub" id="tilt"></span></h2>
<div class="bar">
 <button onclick="cmd({mode:'pitch',delta:1})">앞으로 숙임</button>
 <button onclick="cmd({mode:'pitch',delta:-1})">뒤로 젖힘</button>
</div>
<div class="hint2">무게중심이 뒤로 쏠려 있으면 앞으로 숙여 앞다리에 하중을 옮긴다. 1mm 당 약 0.7%p.</div>
<div class="bar">
 <button onclick="cmd({mode:'roll',delta:1})">왼쪽 낮춤</button>
 <button onclick="cmd({mode:'roll',delta:-1})">오른쪽 낮춤</button>
</div>

<div class="bar">
 <button onclick="cmd({reset:'trim'})">트림 0 으로</button>
 <button onclick="cmd({reset:'all'})">전체 기본값</button>
</div>

<div class="row"><label>몸통 높이</label>
 <input type="range" id="height" step="1"><span class="rv" id="heightv"></span></div>
<div class="hint">어깨축~발바닥 = 140 + 이 값. 무릎내각 110도가 96, 120도가 108, 130도가 118.</div>
<div class="row"><label>발 들어올림</label>
 <input type="range" id="Sh" step="1"><span class="rv" id="Shv"></span></div>
<div class="hint">스윙 중 발이 지면에서 뜨는 높이. 작으면 발이 끌리고, 크면 무릎이 궤적을 못 따라간다.</div>

<h2>보행</h2>
<div class="pad">
 <div></div>
 <button onclick="step('w')">전진</button>
 <div></div>
 <button onclick="step('a')">◀ 좌</button>
 <button class="stop" onclick="cmd({stop:1})">정지</button>
 <button onclick="step('d')">우 ▶</button>
 <div></div>
 <button onclick="step('s')">후진</button>
 <div></div>
</div>
<div class="bar">
 <button onclick="step('q')">↺ 좌회전</button>
 <button onclick="step('e')">우회전 ↻</button>
</div>
<div class="hint2">누를 때마다 누적된다. 전후 10mm, 좌우 10mm, 회전 3도.
 회전은 스윙 구간에 보정이 빠져 있어 발이 튄다 (3도당 약 4mm). 작게 쓸 것.</div>

<div class="st">
 보폭 <b id="sl">-</b>mm &nbsp; 좌우 <b id="sw">-</b>mm &nbsp; 회전 <b id="sa">-</b>°<br>
 <b id="mode">-</b> &nbsp; 대각 차이 <b id="spread">-</b>mm
</div>

<script>
const L=["FL","FR","RL","RR"];
document.getElementById("legs").innerHTML=L.map((n,i)=>
 `<div class="leg"><div class="n">${n}</div><div class="v" id="t${i}">0</div>
  <button onclick="leg('${n}',1)">▲</button>
  <button onclick="leg('${n}',-1)">▼</button></div>`).join("");

async function post(b){
 try{const r=await fetch("/cmd",{method:"POST",body:JSON.stringify(b)});draw(await r.json());}
 catch(e){}
}
const cmd=post;
const leg=(n,d)=>post({leg:n,delta:d});
const step=k=>post({key:k});

function draw(s){
 if(!s||!s.IDtrim)return;
 s.IDtrim.forEach((v,i)=>document.getElementById("t"+i).textContent=(v>0?"+":"")+v.toFixed(0));
 const t0=s.IDtrim;
 const twist=((t0[0]+t0[3])-(t0[1]+t0[2]))/4, gap=Math.abs(twist)*2;
 document.getElementById("spread").textContent=gap.toFixed(1);
 const w=document.getElementById("warn");
 let msg="";
 if(s.ikFail) msg="IK 도달 불가 - 서보 명령이 중단됩니다. 몸통을 낮추거나 보폭을 줄이세요.";
 else if(s.blocked&&s.blocked.length) msg="범위 초과로 전송 못 한 관절이 있습니다 ("+s.blocked.length+"개). 그 관절은 얼어붙습니다.";
 else if(gap>s.Sh*s.twistRatio) msg="대각 차이가 큽니다 ("+gap.toFixed(1)+"mm). 높은 대각 쌍이 접지하지 못할 수 있습니다.";
 w.style.display=msg?"block":"none";
 w.textContent=msg;
 const t=s.IDtrim;
 const pitch=((t[0]+t[1])-(t[2]+t[3]))/4, roll=((t[0]+t[2])-(t[1]+t[3]))/4;
 document.getElementById("tilt").textContent=
  `앞뒤 ${pitch>0?"+":""}${pitch.toFixed(1)}  좌우 ${roll>0?"+":""}${roll.toFixed(1)} mm`;
 document.getElementById("sl").textContent=s.IDstepLength.toFixed(0);
 document.getElementById("sw").textContent=(s.IDstepWidth*2).toFixed(0);
 document.getElementById("sa").textContent=s.IDstepAlpha.toFixed(0);
 document.getElementById("mode").textContent=s.StartStepping?"보행중":"정지";
 for(const k of ["height","Sh"]){
  const el=document.getElementById(k);
  if(s.ranges&&s.ranges[k]){el.min=s.ranges[k][0];el.max=s.ranges[k][1];}
  if(document.activeElement!==el)el.value=s[k];
  document.getElementById(k+"v").textContent=(+s[k]).toFixed(0);
 }
}
for(const k of ["height","Sh"]){
 document.getElementById(k).addEventListener("input",e=>{
  document.getElementById(k+"v").textContent=e.target.value;
  post({param:k,value:+e.target.value});
 });
}
setInterval(async()=>{try{draw(await(await fetch("/state")).json())}catch(e){}},400);
</script></body></html>"""


def startWebControl(keyInputs, port=8080):
    """HTTP 서버를 데몬 스레드로 띄운다. 실패해도 보행은 계속된다."""

    def state():
        s = keyInputs.snapshot()
        s['twistRatio'] = TWIST_WARN_RATIO
        # 슬라이더 범위를 여기서 내려준다. HTML 에 적어두면 DEFAULTS 와 어긋난다.
        s['ranges'] = {k: [lo, hi] for k, (_, lo, hi) in DEFAULTS.items() if lo is not None}
        s.update(getattr(keyInputs, 'runtime', {}))   # 제어 루프가 갱신하는 실시간 상태
        for k in DEFAULTS:
            s.setdefault(k, DEFAULTS[k][0])
        return s

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass        # 요청 로그가 화면과 gait.log 를 오염시키지 않도록 끈다

        def _send(self, body, ctype):
            data = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path.startswith("/state"):
                self._send(json.dumps(state()), "application/json")
            elif self.path == "/" or self.path.startswith("/index"):
                self._send(PAGE, "text/html; charset=utf-8")
            else:
                self.send_error(404)

        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(n) or b"{}")
            except (ValueError, TypeError):
                self.send_error(400)
                return

            if 'leg' in req and req['leg'] in LEGS:
                keyInputs.trimAdjust(req['leg'], 1 if req.get('delta', 1) > 0 else -1)
            elif 'param' in req:
                keyInputs.setParam(req['param'], req.get('value', 0))
            elif req.get('mode') in ('pitch', 'roll'):
                keyInputs.trimAdjust(req['mode'], 1 if req.get('delta', 1) > 0 else -1)
            elif req.get('reset') in ('trim', 'all'):
                keyInputs.resetParams(req['reset'])
            elif req.get('key') in ('w', 'a', 's', 'd', 'q', 'e'):
                keyInputs.keyCounter(req['key'])
                keyInputs.calcRbStep()
            elif req.get('stop'):
                keyInputs.resetStatus()
                keyInputs.calcRbStep()
            self._send(json.dumps(state()), "application/json")

    try:
        srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    except OSError as e:
        print(f"웹 UI 를 열지 못했다 (포트 {port}): {e}")
        return None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
