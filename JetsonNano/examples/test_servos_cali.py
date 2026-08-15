from adafruit_servokit import ServoKit
import board
import busio

# RPi 5 / CM4: I2C1 (pins 3, 5) is board SDA, SCL
print("Initializing Servos")
i2c_bus0=(busio.I2C(board.SCL, board.SDA))
print("Initializing ServoKit")

kit = ServoKit(channels=16, i2c=i2c_bus0, address=0x40)
kit2 = ServoKit(channels=16, i2c=i2c_bus0, address=0x41)

# DS3230 / DS3235 pulse width spec: 500-2500usec
for ch in range(6):
    kit.servo[ch].set_pulse_width_range(500, 2500)
    kit2.servo[ch].set_pulse_width_range(500, 2500)

# kit  (0x40) drives the right legs, kit2 (0x41) drives the left legs
print("Done initializing")

# [0]~[2] : FL // [3]~[5] : FR // [6]~[8] : RL // [9]~[11] : RR
# Must stay in sync with _channel_map in ../servo_controller.py
channel_map = {
    0: (kit2, 0), 1: (kit2, 1), 2: (kit2, 2),   # FL -> 0x41 CH0~2
    3: (kit, 0),  4: (kit, 1),  5: (kit, 2),    # FR -> 0x40 CH0~2
    6: (kit2, 3), 7: (kit2, 4), 8: (kit2, 5),   # RL -> 0x41 CH3~5
    9: (kit, 3),  10: (kit, 4), 11: (kit, 5),   # RR -> 0x40 CH3~5
}

if __name__ == '__main__':

    while True:
        # motro_num is index of motor to rotate
        motro_num=int(input("Enter Servo to rotate (0-11): "))

        # new angle to be written on selected motor
        cur_angle=int(input("Enter new angles (0-180): "))

        kit_obj, ch = channel_map[motro_num]
        kit_obj.servo[ch].angle = cur_angle