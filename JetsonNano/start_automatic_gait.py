"""
Simulation of SpotMicroAI and it's Kinematics 
Use a keyboard to see how it works
Use keyboard-Button to switch betweek walk on static-mode
"""
from os import system, name 
import sys
sys.path.append("..")

import matplotlib.animation as animation
import numpy as np
import socket
import time
import math
import datetime as dt
import random

import Kinematics.kinematics as kn
import spotmicroai
import servo_controller

from multiprocessing import Process
from Common.gait_params import gaitPhases, supportRatio
from Common.multiprocess_kb import (KeyInterrupt, keyboardAvailable,
                                    trimModes, TWIST_WARN_RATIO)
from Common.web_control import startWebControl
from Kinematics.kinematicMotion import KinematicMotion, TrottingGait

rtime=time.time()

def reset():
    global rtime
    rtime=time.time()    

robot=spotmicroai.Robot(False,False,reset)
controller = servo_controller.Controllers()

# TODO: Needs refactoring
speed1=240
speed2=170
speed3=300

speed1=322
speed2=237
speed3=436

stepLength=0
stepHeight=72

walk=False

# 서보 인덱스 -> 관절 이름 (범위 초과 경고 표시용). servo_controller 의 순서와 동일.
JOINT_NAMES = ["FL-Lower", "FL-Upper", "FL-Shoulder", "FR-Lower", "FR-Upper", "FR-Shoulder",
               "RL-Lower", "RL-Upper", "RL-Shoulder", "RR-Lower", "RR-Upper", "RR-Shoulder"]

def resetPose():
    # TODO: globals are bad
    global joy_x, joy_z, joy_y, joy_rz, joy_z
    joy_x, joy_y, joy_z, joy_rz = 128, 128, 128, 128

# define our clear function
def consoleClear():
    """화면을 지운다.

    예전에는 system('clear') 로 셸을 fork 했는데, `| tee` 로 파이프하면
    파이썬 stdout 이 블록 버퍼링이 되는 반면 자식 프로세스는 즉시 출력하므로
    지우기와 출력의 순서가 어긋난다. 화면이 읽을 수 없게 되는 원인이었다.
    같은 스트림에 이스케이프 시퀀스를 직접 써서 순서를 보장한다.
    (루프 fork 가 사라져 CPU 도 덜 쓴다.)
    """
    sys.stdout.write("\x1b[H\x1b[2J\x1b[3J")



trotting=TrottingGait()

# 무릎 각속도 실측. 예전에는 Sh*pi/t3 로 예측했는데 그 식에는 보폭 Sl 이 없다.
# 스윙 중 무릎은 발을 Sh 만큼 올리는 동시에 보폭만큼 되돌려야 하므로 Sl 이 크면
# 각속도도 커진다. Sl 을 -70 에서 -160 으로 키우면 실제로는 349 -> 580 도/s 가
# 되는데 예측식은 같은 값을 계속 보여준다. 위험 구간에 들어가는데 화면은 조용하다.
#
# 그래서 명령한 관절각의 차분을 직접 잰다. 한 주기 동안의 최대값을 들고 있는다
# (스윙은 주기의 일부라 순간값만 보면 대부분 0 이 나온다).
_slewHist = []

def kneeSlew(jointAngles, now, window):
    """무릎(theta3) 각속도의 최근 window(초) 내 최대값, 도/s."""
    global _slewHist
    knees = [float(j[2]) for j in jointAngles]
    if _slewHist:
        t0, prev = _slewHist[-1][0], _slewHist[-1][1]
        dt = now - t0
        if 0 < dt < 0.5:
            rate = max(abs(k - p) for k, p in zip(knees, prev)) / dt * 180.0 / math.pi
            _slewHist.append((now, knees, rate))
        else:
            _slewHist.append((now, knees, 0.0))
    else:
        _slewHist.append((now, knees, 0.0))
    _slewHist = [h for h in _slewHist if now - h[0] <= window][-400:]
    return max((h[2] for h in _slewHist if len(h) > 2), default=0.0)

# 정지(준비) 자세. 보행 궤적의 기본 발 위치와 같은 값을 쓴다.
# 예전에는 여기에 iXf=120 / spurWidth=robot.W/2+20 (=80) 을 따로 적어서
# TrottingGait 의 Fo/Ro/Spf/Spr 과 어긋났고, 보행을 시작하는 순간 발이
# 앞뒤 20mm, 좌우 7~18mm 튀었다. 한 곳에서 가져오도록 바꿨다.
Lp = np.array([[ trotting.Fo, -100,  trotting.Spf, 1],
               [ trotting.Fo, -100, -trotting.Spf, 1],
               [-trotting.Ro, -100,  trotting.Spr, 1],
               [-trotting.Ro, -100, -trotting.Spr, 1]])

motion=KinematicMotion(Lp)
resetPose()

def main(id, command_status, keyInputs=None):
    jointAngles = []
    while True:
        # 화면 지우기는 루프 "시작"에서 한다. 끝에서 지우면 방금 찍은 출력이
        # 곧바로 사라져 화면에 남는 시간이 거의 없다 (키를 감각으로 눌러야 했다).
        consoleClear()

        # stdin 모드에서는 별도 프로세스가 없으므로 여기서 키를 읽는다
        if keyInputs is not None:
            keyInputs.pollStdin()

        xr = 0.0
        yr = 0.0

        # Reset when robot pose become strange
        # robot.resetBody()
    
        ir=xr/(math.pi/180)
        
        d=time.time()-rtime

        # calculate robot step command from keyboard inputs
        result_dict = command_status.get()
        print(result_dict)
        command_status.put(result_dict)

        # 실시간 조정되는 값들. ~/.spotmicro_gait.json 에 저장되어 재시작해도 유지된다.
        #
        # height: bodyPosition 의 y 로 40+height 가 들어간다.
        #   어깨축~발바닥 수직거리 = 140+height,  Upper축~발 거리 H = 120+height.
        #   무릎 내각은 내각 110도 -> height 96,  120도 -> 108,  130도 -> 118.
        #   범위와 기본값은 Common/gait_params.py 의 DEFAULTS 가 정한다.
        height = result_dict.get('height', 110.0)
        trotting.Sh = result_dict.get('Sh', 20.0)

        # 궤적 타이밍. 주기 Tt 와 스윙 비율 duty 로 받아 t1/t3 으로 환산한다.
        # t1/t3 을 따로 노출하면 하나만 만졌을 때 전진 속도와 네발지지 비율이 같이
        # 움직여 무엇이 원인인지 알 수 없다 (work11 6.16.1 이 그 함정이었다).
        # 보행 중이 아니어도 매 루프 갱신한다 - 상태판이 현재 값을 보여야 한다.
        duty = result_dict.get('duty', 0.143)
        trotting.t1, trotting.t3 = gaitPhases(result_dict)

        # 다리별 y 트림 (조립 오차 보정). 보행 중에는 positions() 안에서 적용되고
        # 정지 자세는 고정 배열이라 여기서 직접 더한다. 순서 0 FL, 1 FR, 2 RL, 3 RR
        trim = result_dict.get('IDtrim', [0.0] * 4)

        # wait 3 seconds to start
        if result_dict['StartStepping']:
            currentLp = trotting.positions(d-3, result_dict)
            robot.feetPosition(currentLp)
        else:
            standLp = np.array(Lp, dtype=float)
            for i in range(4):
                standLp[i][1] += trim[i]
            robot.feetPosition(standLp)
        #roll=-xr
        roll=0
        robot.bodyRotation((roll,math.pi/180*((joy_x)-128)/3,-(1/256*joy_y-0.5)))
        bodyX=50+yr*10
        robot.bodyPosition((bodyX, 40+height, -ir))

        # Get current Angles for each motor
        jointAngles = robot.getAngle()
        print(jointAngles)
        
        # 파라미터 조합(몸통 높이 x 트림 x 보폭)이 도달 불가 영역에 들어갔는지
        # 계산 결과로 직접 확인한다. 조합이 많아 정적 범위로는 다 막을 수 없다.
        blocked = []
        ikFail = len(jointAngles) and bool(np.isnan(np.asarray(jointAngles)).any())

        # First Step doesn't contains jointAngles
        if len(jointAngles) and not ikFail:
            # Real Actuators
            blocked = controller.servoRotate(jointAngles) or []

        if keyInputs is not None:
            keyInputs.runtime['blocked'] = blocked
            keyInputs.runtime['ikFail'] = bool(ikFail)
            
            # # Plot Robot Pose into Matplotlib for Debugging
            # TODO: Matplotplib animation
            # kn.initFK(jointAngles)
            # kn.plotKinematics()

        robot.step()

        # 상태판은 루프 마지막에 찍는다. 화면 맨 아래에 남으므로 촬영 중에도 읽힌다.
        # 경고는 대각(twist) 성분만 본다. 앞뒤/좌우 오프셋은 몸통이 그쪽으로
        # 기울면 네 발이 다 닿지만, 대각은 흔들리는 탁자와 같아 닿을 수 없다.
        pitchT, rollT, twistT = trimModes(trim)
        twistGap = abs(twistT) * 2            # 두 대각선의 높이차
        warn = ("  <-- 대각 차이 과다. 높은 쌍이 접지 못 할 수 있다"
                if twistGap > trotting.Sh * TWIST_WARN_RATIO else "")
        print("=" * 64)
        print(f" 보폭 {result_dict['IDstepLength']:+6.0f}mm   "
              f"{'보행중' if result_dict['StartStepping'] else '정지'}"
              f"   (w 전진 / s 후진, 1회 10mm, 음수가 전진)")
        print(f" 트림 mm   FL {trim[0]:+5.0f}   FR {trim[1]:+5.0f}      "
              f"i(FL) o(FR)   소문자 = 올림")
        print(f"           RL {trim[2]:+5.0f}   RR {trim[3]:+5.0f}      "
              f"k(RL) l(RR)   대문자 = 내림")
        print(f" 앞뒤 {pitchT:+.1f}   좌우 {rollT:+.1f}   대각 {twistT:+.1f}"
              f"  (대각차 {twistGap:.1f}mm){warn}")
        print(f" 몸통높이 {height:.0f} (t 높임 / g 낮춤)    발들어올림 Sh {trotting.Sh:.0f} (r/f)")
        # 주기와 스윙 비율. 이 둘이 "얼마나 높이 드느냐" 와 "안 넘어지느냐" 를 정한다.
        #   네발지지가 낮을수록 대각 두 발로 버티는 시간이 길어진다. IMU 가 없으므로
        #   50% 아래로 내려가면 주저앉기 시작한다 (work11 6.16.1).
        #   슬루율은 무릎이 요구받는 각속도다. DS3235 무부하 정격이 545도/s 다.
        support = supportRatio(duty) * 100
        # 명령한 관절각에서 직접 잰다. 한 주기를 창으로 본다.
        slew = kneeSlew(jointAngles, time.time(),
                        (trotting.t1 + trotting.t3) / 1000.0) if len(jointAngles) else 0.0
        speed = abs(result_dict['IDstepLength']) / (trotting.t1 + trotting.t3) * 1000
        supportWarn = "  <-- 낮다. 대각 두 발로 버티는 시간이 길다" if support < 50 else ""
        slewWarn = ("  <-- 정격 초과!!" if slew > 545
                    else "  <-- 정격의 90%" if slew > 490 else "")
        print(f" 주기 {trotting.t1 + trotting.t3:.0f}ms (c 느리게 / v 빠르게)"
              f"   스윙비율 {duty:.2f} (b 늘림 / n 줄임)   t1/t3 {trotting.t1:.0f}/{trotting.t3:.0f}")
        print(f" 네발지지 {support:.0f}%{supportWarn}")
        print(f" 무릎슬루 {slew:.0f}도/s (실측, 정격 545){slewWarn}"
              f"      전진속도 {speed:.0f}mm/s (이론, 미끄러짐 0 가정)")
        print(" y/h 앞뒤기울기   u/j 좌우기울기   p 트림리셋   space 정지   Ctrl-C 종료")
        if ikFail:
            print(" !! IK 도달 불가 - 서보 명령 중단. 몸통을 낮추거나(g) 보폭을 줄여라")
        elif blocked:
            names = ", ".join(JOINT_NAMES[i] for i in blocked)
            print(f" !! 범위 초과로 전송 못 한 관절: {names}  (그 관절은 얼어붙는다)")
        print("=" * 64)
        # 이 flush 가 있어야 지우기와 출력의 순서가 보장된다 (파이프 실행 시 특히)
        sys.stdout.flush()


if __name__ == "__main__":
    KeyProcess = None
    savedTerm = None
    KeyInputs = KeyInterrupt()

    # 폰으로 로봇을 보면서 조작하기 위한 웹 UI. 데몬 스레드라 종료를 막지 않는다.
    # 실패해도(포트 사용 중 등) 키보드 조작은 그대로 된다.
    if startWebControl(KeyInputs):
        try:
            _ip = socket.gethostbyname(socket.gethostname())
        except OSError:
            _ip = "<로봇IP>"
        print(f"웹 UI: http://{_ip}:8080   (폰 브라우저로 접속)")

    try:
        # keyboard 라이브러리는 root 권한과 /dev/input 의 물리 키보드를 요구한다.
        # SSH 로 접속한 경우엔 sudo 로 실행해도 키가 전달되지 않으므로 stdin 을 쓴다.
        if keyboardAvailable():
            print("입력: 물리 키보드 (keyboard 라이브러리)")
            KeyProcess = Process(target=KeyInputs.keyInterrupt, args=(1, KeyInputs.key_status, KeyInputs.command_status))
            KeyProcess.start()
            main(2, KeyInputs.command_status)
        else:
            print("입력: stdin (이 터미널에서 w/a/s/d/q/e, space=정지, Ctrl-C 종료)")
            print("트림: i=FL o=FR k=RL l=RR 올림, 대문자(Shift)면 내림. 1회당 1mm.")
            print("      i o / k l 이 위에서 본 다리 배치다. 끌리는 다리를 올린다.")
            print("      y/h 앞뒤기울기   u/j 좌우기울기   t/g 몸통높이   r/f 발들어올림   p 리셋")
            time.sleep(1.5)
            savedTerm = KeyInputs.beginStdin()
            main(2, KeyInputs.command_status, KeyInputs)

        print("terminate KeyBoard Input process")
    except KeyboardInterrupt:
        print("중단")
    except Exception as e:
        print(e)
    finally:
        KeyInputs.endStdin(savedTerm)
        if KeyProcess is not None and KeyProcess.is_alive():
            KeyProcess.terminate()
        print("Done... :)")