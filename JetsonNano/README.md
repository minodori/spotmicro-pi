> **디렉터리명은 upstream 유래입니다. 현재 대상 보드는 Raspberry Pi Compute Module 4 입니다.**
> Jetson Nano -> RPi 5 -> CM4 전환 경위는 [work05](../study/minho/work05.md),
> [work07](../study/minho/work07.md), [work11](../study/minho/work11.md) 참조.

## SpotMicroAI for JetsonNano

TODO: Update this documentation

The Nano will use a 16 Channel PCA9685 I2C-Servo Driver to drive the 12 Servos for the Legs.
First of all all prepare your Jetson Nano as you see in the NVIDIA Documentation.

Then connect to it via SSH and:

```
$ sudo apt install python-dev python-pip python3-pip libfreetype6-dev libavdevice-dev libavfilter-dev libswscale-dev libavformat-dev libjpeg-dev build-essential -y
$ sudo apt install libsdl-dev libportmidi-dev libsdl-ttf2.0-dev libsdl-mixer1.2-dev libsdl-image1.2-dev -y 

$ pip install --upgrade pip
$ pip install --upgrade setuptools

$ cd SpotMiroAI/JetsonNano
$ pip3 install -U -r requirements.txt 
```
