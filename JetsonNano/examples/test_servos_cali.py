from adafruit_servokit import ServoKit
import board
import busio

# On the Jetson Nano
# Bus 0 (pins 28,27) is board SCL_1, SDA_1 in the jetson board definition file
# Bus 1 (pins 5, 3) is board SCL, SDA in the jetson definition file
# Default is to Bus 1; We are using Bus 0, so we need to construct the busio first ...
print("Initializing Servos")
i2c_bus0=(busio.I2C(board.SCL, board.SDA))
print("Initializing ServoKit")

kit = ServoKit(channels=16, i2c=i2c_bus0, address=0x40)
kit2 = ServoKit(channels=16, i2c=i2c_bus0, address=0x41)

# DS3230 / DS3235 pulse width spec: 500-2500usec
for ch in range(6):
    kit.servo[ch].set_pulse_width_range(500, 2500)
    kit2.servo[ch].set_pulse_width_range(500, 2500)

# kit[0] is the front servos
# kit[1] is the rear servos
print("Done initializing")

# [0]~[2] : FL // [3]~[5] : FR // [6]~[8] : RL // [9]~[11] : RR

if __name__ == '__main__':

    while True:
        # motro_num is index of motor to rotate
        motro_num=int(input("Enter Servo to rotate (0-11): "))

        # new angle to be written on selected motor
        cur_angle=int(input("Enter new angles (0-180): "))

        if motro_num < 6:
            kit.servo[int(motro_num % 6)].angle = cur_angle
        else:
            kit2.servo[int(motro_num % 6)].angle = cur_angle