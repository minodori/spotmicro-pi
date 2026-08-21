import sys
sys.path.append("..")

import Kinematics.kinematics as kn
import numpy as np
from Common.servo_map import SERVO_OFFSETS
from Common.servo_oe import OutputEnable, configurePCA
from adafruit_servokit import ServoKit
import board
import busio
import time

class Controllers:
    def __init__(self):

        print("Initializing Servos")
        self._i2c_bus0=(busio.I2C(board.SCL, board.SDA))
        print("Initializing ServoKit")
        self._kit = ServoKit(channels=16, i2c=self._i2c_bus0, address=0x40)
        self._kit2 = ServoKit(channels=16, i2c=self._i2c_bus0, address=0x41)

        # [0]~[2] : 왼쪽 앞 다리 // [3]~[5] : 오른쪽 앞 다리 // [6]~[8] : 왼쪽 뒷 다리 // [9]~[11] : 오른쪽 뒷 다리
        # 배터리 좌우에 놓인 물리 배치에 맞춰 PCA9685를 좌/우 다리로 분리 배선함
        # (0x40 = 배터리 우측 보드 -> 오른쪽 다리, 0x41 = 배터리 좌측 보드 -> 왼쪽 다리)
        # 채널은 배선이 짧아지는 쪽으로 고른다. 각 보드에서 물리적으로 가까운 헤더에 그 다리를 문다.
        # 좌측 보드(0x41)는 CH0 이 앞쪽, 우측 보드(0x40)는 반전 장착이라 CH15 가 앞쪽이다.
        # index -> (kit, 보드 채널)
        self._channel_map = {
            0: (self._kit2, 0),  1: (self._kit2, 1),  2: (self._kit2, 2),   # FL -> 0x41 CH0~2   (좌측 앞단)
            3: (self._kit, 13),  4: (self._kit, 14),  5: (self._kit, 15),   # FR -> 0x40 CH13~15 (우측 반전 -> 끝단이 앞쪽)
            6: (self._kit2, 13), 7: (self._kit2, 14), 8: (self._kit2, 15),  # RL -> 0x41 CH13~15 (좌측 끝단)
            9: (self._kit, 0),   10: (self._kit, 1),  11: (self._kit, 2),   # RR -> 0x40 CH0~2   (우측 반전 -> 앞단이 뒤쪽)
        }

        # OE(Output Enable)로 실제 릴리즈가 가능하도록 설정한다.
        # 이 로봇의 DS 계열 서보는 펄스를 끊어도(신호선 LOW) 마지막 목표값을 유지한다.
        # 신호선이 "뜬 상태" 여야만 힘이 빠지고, OUTNE=10 + OE HIGH 가 그 상태를 만든다.
        # 배선이 없거나 gpiod 가 없으면 조용히 무시되고 기존 동작 그대로다.
        for kit_obj in (self._kit, self._kit2):
            configurePCA(kit_obj._pca)
        self._oe = OutputEnable()
        self._oe.enable(True)
        if self._oe.available:
            print("OE 제어 활성 - 프로그램이 끝나면 서보가 자동 릴리즈된다")

        # DS3230 / DS3235 pulse width spec: 500-2500usec
        # 기본값(750-2250)으로 남는 채널이 없도록 실제 사용하는 채널 전부에 적용한다.
        for kit_obj, ch in self._channel_map.values():
            kit_obj.servo[ch].set_pulse_width_range(500, 2500)

        print("Done initializing")

        # centered position perpendicular to the ground
        # CM4 이식 후 실측값 (2026-08-15). 이전 Jetson 개체 값: [170,85,90,1,95,90,172,90,90,1,90,95]
        # RR-Lower(idx 9): 혼 이탈 후 삽입부를 갈아 완전 체결하며 5 -> 26 으로 바뀌었다.
        # 스플라인 한 칸만큼 안쪽으로 들어와 가동 한계 여유가 생겼다.
        # 값은 Common/servo_map.py 에 있다. 시뮬레이터도 같은 오프셋을 알아야 하는데
        # (관절 가동 범위가 여기서 유도된다) 이 파일은 adafruit/board 를 import 하므로
        # 로봇 밖에서 읽을 수 없다. 두 곳에 같은 표를 두면 반드시 어긋난다.
        self._servo_offsets = list(SERVO_OFFSETS)

        # self._servo_offsets = [179, 88, 81, 13, 87, 88, 179, 96, 91, 26, 81, 81]
        # self._servo_offsets = [150, 81, 79, 1, 95, 105, 164, 81, 82, 1, 80, 81]
        # self._servo_offsets = [90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90]

        self._val_list = np.zeros(12) #[ x for x in range(12) ]

        # All Angles for Leg 3 * 4 = 12 length
        self._thetas = []

    def getDegreeAngles(self, La):
        # radian to degree
        La *= 180/np.pi
        La = [ [ int(x) for x in y ] for y in La ]

        self._thetas = La

    # Angle mapping from radian to servo angles
    def angleToServo(self, La):

        self.getDegreeAngles(La)

        #FL Lower
        self._val_list[0] = self._servo_offsets[0] - self._thetas[0][2]
        #FL Upper
        self._val_list[1] = self._servo_offsets[1] - self._thetas[0][1]    
        #FL Shoulder
        self._val_list[2] = self._servo_offsets[2] + self._thetas[0][0]

        #FR Lower
        self._val_list[3] = self._servo_offsets[3] + self._thetas[1][2]
        #FR Upper
        self._val_list[4] = self._servo_offsets[4] + self._thetas[1][1]    
        #FR Shoulder
        self._val_list[5] = self._servo_offsets[5] - self._thetas[1][0]

        #BL Lower
        self._val_list[6] = self._servo_offsets[6] - self._thetas[2][2]
        #BL Upper
        self._val_list[7] = self._servo_offsets[7] - self._thetas[2][1]    
        #BL Shoulder, Formula flipped from the front
        self._val_list[8] = self._servo_offsets[8] - self._thetas[2][0]

        #BR Lower. 
        self._val_list[9] = self._servo_offsets[9] + self._thetas[3][2]
        #BR Upper
        self._val_list[10] = self._servo_offsets[10] + self._thetas[3][1]    
        #BR Shoulder, Formula flipped from the front
        self._val_list[11] = self._servo_offsets[11] + self._thetas[3][0]     

    def getServoAngles(self):
        return self._val_list

    def servoRotate(self, thetas):
        """서보에 각도를 쓴다. 범위를 벗어나 전송하지 못한 인덱스 목록을 반환한다.

        반환값은 보행 중 실시간 안전 표시에 쓴다. 파라미터(몸통 높이/트림/보폭)의
        조합에 따라 도달 불가 영역에 들어갈 수 있는데, 조합이 많아 정적 범위로는
        다 막을 수 없다. 실제 계산 결과를 보고 경고하는 편이 확실하다.
        """
        blocked = []
        self.angleToServo(thetas)
        #self.angleToServo(np.zeros((4,3)))
        for x in range(len(self._val_list)):

            if x>=0 and x<12:
                # (val-26.36)*(1980/1500) 변환은 set_pulse_width_range 가 없던 시절
                # ServoKit 기본 범위(750-2250)를 실제 서보 범위(460-2440)로 맞추던 보정이다.
                # 지금은 set_pulse_width_range(500, 2500) 으로 범위를 직접 지정하므로
                # 이 변환을 덧씌우면 이중 보정이 되어 offset 자체가 범위를 벗어난다.
                # (예: offset 170 -> 189.6 "Over 180!!", offset 1 -> -33.5 "Under 0!!")
                print(self._val_list[x])

                if (self._val_list[x] > 180):
                    print("Over 180!!")
                    self._val_list[x] = 179
                    blocked.append(x)
                    continue
                if (self._val_list[x] <= 0):
                    print("Under 0!!")
                    self._val_list[x] = 1
                    blocked.append(x)
                    continue
                kit_obj, ch = self._channel_map[x]
                kit_obj.servo[ch].angle = self._val_list[x]

        return blocked

    def releaseAll(self):
        """모든 서보의 PWM 을 끊어 유지 토크를 없앤다.

        프로세스가 끝나도 PCA9685 는 마지막 펄스폭을 계속 내보내므로, 서보는
        목표 각도를 물고 stall 전류를 먹는다. 테스트를 마쳤으면 풀어둘 것.
        angle = None 은 duty_cycle 을 0 으로 만들어 펄스 자체를 멈춘다.

        지면에 서 있는 상태에서 호출하면 그대로 주저앉는다.
        """
        for kit_obj, ch in self._channel_map.values():
            kit_obj.servo[ch].angle = None
        # 펄스만 끊으면 DS 계열은 마지막 목표값을 유지한다. OE 로 신호선을 놓아야
        # 실제로 힘이 빠진다.
        self._oe.release()


if __name__=="__main__":
    # 발끝을 엉덩관절 바로 아래(x=+-L/2=70), 몸통 높이 120mm, 폭은 shoulder theta=0 이 되는 87.5.
    # 기존 x=+-100 은 앞발을 관절보다 30mm 앞, 뒷발을 30mm 뒤로 뻗는 자세였다.
    # 다리 기구가 앞뒤 대칭이 아니라 뒤로 뻗는 쪽이 훨씬 큰 회전을 요구하고
    # (upper: 앞 -44도 vs 뒤 -85도), 그 결과 RR-Upper 가 범위를 벗어났다.
    legEndpoints=np.array([[70,-120,87.5,1],[70,-120,-87.5,1],[-70,-120,87.5,1],[-70,-120,-87.5,1]])
    thetas = kn.initIK(legEndpoints) #radians
    
    controller = Controllers()

    # Get radian thetas, transform to integer servo angles
    # then, rotate servos
    controller.servoRotate(thetas)

    # Get AngleValues for Debugging
    svAngle = controller.getServoAngles()
    print(svAngle)

    # #plot at the end
    kn.plotKinematics()