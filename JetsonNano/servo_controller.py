import sys
sys.path.append("..")

import Kinematics.kinematics as kn
import numpy as np
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

        # DS3230 / DS3235 pulse width spec: 500-2500usec
        for ch in range(6):
            self._kit.servo[ch].set_pulse_width_range(500, 2500)
            self._kit2.servo[ch].set_pulse_width_range(500, 2500)

        print("Done initializing")

        # [0]~[2] : 왼쪽 앞 다리 // [3]~[5] : 오른쪽 앞 다리 // [6]~[8] : 왼쪽 뒷 다리 // [9]~[11] : 오른쪽 뒷 다리
        # 배터리 좌우에 놓인 물리 배치에 맞춰 PCA9685를 좌/우 다리로 분리 배선함
        # (0x40 = 배터리 우측 보드 -> 오른쪽 다리, 0x41 = 배터리 좌측 보드 -> 왼쪽 다리)
        # index -> (kit, 보드 채널)
        self._channel_map = {
            0: (self._kit2, 0), 1: (self._kit2, 1), 2: (self._kit2, 2),   # FL -> 0x41 CH0~2
            3: (self._kit, 0),  4: (self._kit, 1),  5: (self._kit, 2),    # FR -> 0x40 CH0~2
            6: (self._kit2, 3), 7: (self._kit2, 4), 8: (self._kit2, 5),   # RL -> 0x41 CH3~5
            9: (self._kit, 3),  10: (self._kit, 4), 11: (self._kit, 5),   # RR -> 0x40 CH3~5
        }
        # centered position perpendicular to the ground
        self._servo_offsets = [170, 85, 90, 1, 95, 90, 172, 90, 90, 1, 90, 95]
        #self._servo_offsets = [90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90]

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
        self.angleToServo(thetas)
        #self.angleToServo(np.zeros((4,3)))
        for x in range(len(self._val_list)):
            
            if x>=0 and x<12:
                self._val_list[x] = (self._val_list[x]-26.36)*(1980/1500)
                #print(self._val_list[x], end=' ')
                #if x%3 == 2: print()
                print(self._val_list[x])

                if (self._val_list[x] > 180):
                    print("Over 180!!")
                    self._val_list[x] = 179
                    continue
                if (self._val_list[x] <= 0):
                    print("Under 0!!")
                    self._val_list[x] = 1
                    continue
                kit_obj, ch = self._channel_map[x]
                kit_obj.servo[ch].angle = self._val_list[x]


if __name__=="__main__":
    legEndpoints=np.array([[100,-100,87.5,1],[100,-100,-87.5,1],[-100,-100,87.5,1],[-100,-100,-87.5,1]])
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