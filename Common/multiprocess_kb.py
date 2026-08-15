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
control_offset = {'IDstepLength': 0.0, 'IDstepWidth': 0.0, 'IDstepAlpha': 0.0, 'StartStepping': False }

class KeyInterrupt(): 

    def __init__(self): 
        # How many times Keys Pushed
        self.key_status = Queue()
        self.key_status.put(key_value_default)
        
        # Calculate Offset based on Key Status
        self.command_status = Queue()
        self.command_status.put(control_offset)

        # Offsets for Robot Control
        # Search calcRbStep for Usage
        self.X_STEP = 10.0
        self.Y_STEP = 5.0
        self.YAW_STEP = 3.0

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