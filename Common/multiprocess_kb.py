'''
Multiprocess Keyboard Interrupt Handler
You can get Keyboard inputs while running 
another endless Loops 
'''

import select
import sys
import termios
import time
import tty

import keyboard
from multiprocessing import Process, Queue

from Common.gait_params import DEFAULTS, loadParams, saveParams


def keyboardAvailable():
    """keyboard 라이브러리를 실제로 쓸 수 있는지 확인한다.

    import 는 통과하지만 첫 호출에서 root 권한을 요구하며 실패한다.
    또한 이 라이브러리는 /dev/input 의 물리 키보드를 직접 읽으므로
    SSH 세션의 키 입력은 sudo 로 실행해도 전달되지 않는다.
    """
    try:
        keyboard.is_pressed('w')
        return True
    except Exception:
        return False


# keyboard Initialisation
# Dictionary of keyboard controller buttons we want to include.
key_value_default = {'w': 0, 'a': 0, 's': 0, 'd': 0, 'q': 0, 'e': 0, 'move': False }
control_offset = {'IDstepLength': 0.0, 'IDstepWidth': 0.0, 'IDstepAlpha': 0.0, 'StartStepping': False,
                  'IDtrim': [0.0, 0.0, 0.0, 0.0]}

# 다리별 발끝 y 트림 (mm). 조립 오차로 다리 유효 길이가 다른 것을 보정한다.
# 양수 = 발끝을 몸통 쪽으로 = 다리를 짧게 = 스윙 중 지면 여유 증가.
# 다리 순서는 IK/서보 인덱스와 같다: 0 FL, 1 FR, 2 RL, 3 RR
#
# 4개 값을 직접 만지는 대신 아래 4개 모드로 조작한다. 이 4개가 4차원 트림
# 공간을 완전히 span 하므로 어떤 조합도 이들의 합으로 만들 수 있다.
TRIM_MODES = {
    # 다리 하나씩. 실제로 끌리는 것은 한 다리인 경우가 많다.
    'FL': (1, 0, 0, 0),
    'FR': (0, 1, 0, 0),
    'RL': (0, 0, 1, 0),
    'RR': (0, 0, 0, 1),
    # 묶음 조작
    'pitch': (1, 1, -1, -1),    # 앞뒤 기울기
    'roll':  (1, -1, 1, -1),    # 좌우 기울기
    # 네 발 동시(1,1,1,1)는 두지 않는다. 그건 몸통 높이이고 height 파라미터가
    # 그 역할을 한다 (t/g). 트림은 다리 사이의 "차이" 만 담당하게 둔다.
}
# mm. 개별 다리 트림의 한계. 계산 근거 (몸통높이 60, Sh 20, 보폭 60):
#   pitch +-10 -> 서보 여유 20도,  +-15 -> IK 도달 불가
#   roll  +-10 -> 여유 31도
#   twist +-10 -> 여유 20도
# 서보 여유로는 10 이 상한이다. 접지 조건은 아래 twist 경고가 따로 본다.
TRIM_MAX = 10.0
TRIM_MIN = -10.0

# 경고 기준은 "다리 간 최대-최소" 가 아니라 대각(twist) 성분이다.
#
#   앞뒤(pitch)/좌우(roll) 오프셋은 로봇이 그쪽으로 기울면 네 발이 다 닿는다. 문제 없다.
#   대각(twist) 오프셋만 다르다. 다리가 흔들리는 탁자와 같아서, 아무리 기울여도
#   네 점이 동시에 닿을 수 없다. 한 대각 쌍이 지면을 놓치면 반대 대각선으로 넘어진다.
#
# twist = ((FL+RR) - (FR+RL)) / 4 이고, 두 대각선의 높이차는 그 2배다.
# 그 높이차가 발 들어올림 Sh 에 육박하면 높은 쌍이 아예 접지하지 못한다.
TWIST_WARN_RATIO = 0.3      # 2*|twist| 가 Sh 의 이 비율을 넘으면 경고


def trimModes(trim):
    """다리별 트림을 pitch / roll / twist 성분으로 분해한다."""
    t = list(trim) + [0.0] * (4 - len(trim))
    return (((t[0] + t[1]) - (t[2] + t[3])) / 4.0,      # pitch (앞이 낮아짐)
            ((t[0] + t[2]) - (t[1] + t[3])) / 4.0,      # roll  (좌측이 낮아짐)
            ((t[0] + t[3]) - (t[1] + t[2])) / 4.0)      # twist (대각)

# 키 -> (모드, 부호).  기존 이동키(w a s d q e space)와 겹치지 않게 고른다.
#
# i o / k l 블록을 로봇을 위에서 본 다리 배치로 쓴다. 소문자가 올림, 대문자(Shift)가 내림.
#
#          앞
#     i(FL)   o(FR)          i I  =  FL 올림 / 내림
#     k(RL)   l(RR)          o O  =  FR,   k K = RL,   l L = RR
#          뒤
#
TRIM_KEYS = {
    'i': ('FL', +1), 'I': ('FL', -1),
    'o': ('FR', +1), 'O': ('FR', -1),
    'k': ('RL', +1), 'K': ('RL', -1),
    'l': ('RR', +1), 'L': ('RR', -1),
    'y': ('pitch', +1), 'h': ('pitch', -1),    # 앞뒤 기울기
    'u': ('roll', +1),  'j': ('roll', -1),     # 좌우 기울기
}

# 단일 파라미터 키 -> (이름, 증분). 범위는 gait_params.DEFAULTS 가 정한다.
#
# 증분은 "한 번 눌러서 실기에 변화가 보이되 넘어지지는 않는" 크기로 골랐다.
# Tt 100ms 는 1400 기준 7%, duty 0.01 은 네발지지를 2%p 움직인다.
PARAM_KEYS = {
    't': ('height', +1.0),  'g': ('height', -1.0),  # 몸통 높임 / 낮춤
    'r': ('Sh', +1.0),      'f': ('Sh', -1.0),      # 발 들어올림
    'c': ('Tt', +100.0),    'v': ('Tt', -100.0),    # 주기 (c = cycle). 느리게 / 빠르게
    'b': ('duty', +0.01),   'n': ('duty', -0.01),   # 스윙 비율. 높이 들기 / 안정성
}

class KeyInterrupt(): 

    def __init__(self):
        # How many times Keys Pushed
        self.key_status = Queue()
        self.key_status.put(key_value_default)

        # Calculate Offset based on Key Status
        # 저장해둔 튜닝값(트림/Sh/height)을 얹어서 시작한다.
        start = dict(control_offset)
        start.update(loadParams())
        self.command_status = Queue()
        self.command_status.put(start)

        # Offsets for Robot Control
        # Search calcRbStep for Usage
        self.X_STEP = 10.0
        self.Y_STEP = 5.0
        self.YAW_STEP = 3.0
        self.TRIM_STEP = 1.0    # mm, 키 한 번당

        # 제어 루프가 매 주기 갱신하는 읽기 전용 상태 (IK 실패, 범위 초과 관절 등).
        # 웹 UI 스레드가 같은 프로세스에서 읽는다. 큐를 쓰면 왕복이 늘어난다.
        self.runtime = {'blocked': [], 'ikFail': False}

    def trimAdjust(self, mode, sign):
        """다리별 y 트림을 모드 단위로 조정한다. 보행 중 실시간으로 호출된다."""
        d = self.command_status.get()
        trim = list(d.get('IDtrim', [0.0] * 4))
        pattern = TRIM_MODES[mode]
        for i in range(4):
            trim[i] = max(TRIM_MIN, min(TRIM_MAX,
                                        trim[i] + sign * self.TRIM_STEP * pattern[i]))
        d['IDtrim'] = trim
        self.command_status.put(d)
        saveParams(d)

    def resetParams(self, what='trim'):
        """what='trim' 이면 트림만 0 으로, 'all' 이면 저장된 값 전부를 기본값으로."""
        d = self.command_status.get()
        if what == 'all':
            for k, (dflt, _, _) in DEFAULTS.items():
                d[k] = list(dflt) if isinstance(dflt, list) else dflt
        else:
            d['IDtrim'] = [0.0] * 4
        self.command_status.put(d)
        saveParams(d)
        return d

    def trimReset(self):
        self.resetParams('trim')

    def setParam(self, name, value):
        """Sh / height 처럼 범위가 있는 단일 파라미터를 설정한다. 웹 UI 가 쓴다."""
        if name not in DEFAULTS:
            return None
        dflt, lo, hi = DEFAULTS[name]
        if lo is None:
            return None
        d = self.command_status.get()
        d[name] = max(lo, min(hi, float(value)))
        self.command_status.put(d)
        saveParams(d)
        return d[name]

    def adjustParam(self, name, delta):
        d = self.command_status.get()
        cur = d.get(name, DEFAULTS[name][0])
        self.command_status.put(d)
        return self.setParam(name, cur + delta)

    def snapshot(self):
        """현재 상태를 읽기만 한다 (큐를 비우지 않도록 즉시 되돌린다)."""
        d = self.command_status.get()
        self.command_status.put(d)
        return dict(d)

    def resetStatus(self):
        result_dict = self.key_status.get()
        self.key_status.put(key_value_default)

    def keyCounter(self, character):
        result_dict = self.key_status.get()
        result_dict[character] += 1
        result_dict['move'] = True
        self.key_status.put(result_dict)

    # Calculate Robot Velocity
    # Supports Linear X, Linear Y and Angular Yaw Control Now.
    def calcRbStep(self):
        result_dict = self.key_status.get()
        command_dict = self.command_status.get()
        command_dict['IDstepLength'] = self.X_STEP * result_dict['s'] - self.X_STEP * result_dict['w']
        command_dict['IDstepWidth'] = self.Y_STEP * result_dict['d'] - self.Y_STEP * result_dict['a']
        command_dict['IDstepAlpha'] = self.YAW_STEP * result_dict['q'] - self.YAW_STEP * result_dict['e']
        
        if result_dict['move']:
            command_dict['StartStepping'] = True
        else:
            command_dict['StartStepping'] = False

        self.key_status.put(result_dict)
        self.command_status.put(command_dict)

    # --- stdin 입력 (SSH 등 keyboard 라이브러리를 못 쓰는 환경) ---------------
    # multiprocessing 자식 프로세스는 stdin 이 /dev/null 로 닫히므로
    # (multiprocessing.util._close_stdin), 이 경로는 메인 프로세스에서 폴링한다.

    def beginStdin(self):
        """터미널을 cbreak 로 바꿔 Enter 없이 키를 읽는다. 원래 설정을 반환."""
        if not sys.stdin.isatty():
            return None
        old = termios.tcgetattr(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
        return old

    def endStdin(self, old):
        if old is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old)

    def pollStdin(self):
        """논블로킹으로 stdin 을 읽어 키 카운트를 갱신한다. 매 루프에서 호출."""
        while select.select([sys.stdin], [], [], 0)[0]:
            ch = sys.stdin.read(1)
            if ch == '':        # EOF - 안 그러면 select 가 계속 readable 을 반환해 무한 루프
                break
            if ch in ('w', 'a', 's', 'd', 'q', 'e'):
                self.keyCounter(ch)
            elif ch == ' ':
                self.resetStatus()
            elif ch in TRIM_KEYS:
                self.trimAdjust(*TRIM_KEYS[ch])
            elif ch in PARAM_KEYS:
                self.adjustParam(*PARAM_KEYS[ch])
            elif ch == 'p':
                self.trimReset()
        self.calcRbStep()

    # Activated when Key Pressed, Doesn't support Hotkey
    # Doesn't support more than two key pressing
    def keyInterrupt(self, id, key_status, command_status):
        
        was_pressed = False

        while True:
            if keyboard.is_pressed('w'):
                if not was_pressed:
                    self.keyCounter('w')
                    was_pressed = True
            elif keyboard.is_pressed('a'):
                if not was_pressed:
                    self.keyCounter('a')
                    was_pressed = True
            elif keyboard.is_pressed('s'):
                if not was_pressed:
                    self.keyCounter('s')
                    was_pressed = True
            elif keyboard.is_pressed('d'):
                if not was_pressed:
                    self.keyCounter('d')
                    was_pressed = True
            elif keyboard.is_pressed('q'):
                if not was_pressed:
                    self.keyCounter('q')
                    was_pressed = True
            elif keyboard.is_pressed('e'):
                if not was_pressed:
                    self.keyCounter('e')
                    was_pressed = True
            elif keyboard.is_pressed('space'):
                if not was_pressed:
                    self.resetStatus()
                    was_pressed = True
            else:
                was_pressed = False

            self.calcRbStep()

# Test Endless While Loop
def testWhile(id, command_status):
    while True:
        result_dict = command_status.get()
        print(result_dict)
        command_status.put(result_dict)
        time.sleep(1)

# Basic Usage
if __name__ == "__main__":
    try:
        KeyTest = KeyInterrupt()
        KeyProcess = Process(target=KeyTest.keyInterrupt, args=(1, KeyTest.key_status, KeyTest.command_status))

        KeyProcess.start()

        testWhile(2, KeyTest.command_status)
    except Exception as e:
        print(e)
    finally:
        print("Done... ")