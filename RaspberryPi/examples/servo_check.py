#!/usr/bin/env python3
"""
서보 채널 검증용 헬퍼.

사용법:
    python3 servo_check.py <index> <angle>              한 각도로 이동
    python3 servo_check.py <index> sweep                90 기준 +-20도 3회 왕복
    python3 servo_check.py <index> sweep <amp> <cycles> 진폭/횟수 지정
    python3 servo_check.py map                          인덱스 -> 보드/채널 표
    python3 servo_check.py raw <40|41> <ch> [angle]     보드/채널 직접 지정
    python3 servo_check.py scan                         12개 채널 순차 스윕 (실측용)
    python3 servo_check.py cal [index]                  오프셋 대화형 캘리브레이션
    python3 servo_check.py home [force]                 12개를 기준 자세(오프셋)로 한번에
                                                        (가동 한계에 붙은 오프셋은 건너뜀)
    python3 servo_check.py release [index]              PWM 을 끊어 힘을 뺀다 (stall 방지)
    python3 servo_check.py status                        각 채널이 구동 중인지 읽는다 (서보 안 움직임)

직립 자세(IK 로 무릎을 굽힌 자세)는 ../servo_controller.py 를 실행한다.

인덱스는 servo_controller.py 의 _channel_map 과 동일:
    [0]~[2] FL / [3]~[5] FR / [6]~[8] RL / [9]~[11] RR
    각 다리 안에서 Lower, Upper, Shoulder 순서.
"""
import os
import readline  # noqa: F401  input() 에서 방향키/백스페이스 편집 활성화
import sys
import termios
import time
import tty

import board
import busio
from adafruit_servokit import ServoKit

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from Common.servo_map import SERVO_OFFSETS
from Common.servo_oe import OutputEnable, configurePCA

i2c = busio.I2C(board.SCL, board.SDA)
kit = ServoKit(channels=16, i2c=i2c, address=0x40)   # 배터리 우측 보드 -> 오른쪽 다리
kit2 = ServoKit(channels=16, i2c=i2c, address=0x41)  # 배터리 좌측 보드 -> 왼쪽 다리

# 코드가 쓰는 건 CH0~5 뿐이지만, 배선 확인용으로 전 채널을 같은 조건으로 맞춰둔다.
for ch in range(16):
    kit.servo[ch].set_pulse_width_range(500, 2500)
    kit2.servo[ch].set_pulse_width_range(500, 2500)

# OE 를 고임피던스 방식으로 설정하고 라인을 잡는다. 배선이 안 되어 있거나
# gpiod 가 없으면 조용히 무시되고 기존 동작 그대로다.
for _k in (kit, kit2):
    configurePCA(_k._pca)
OE = OutputEnable()
OE.enable(True)


def holdUntilEnter(msg="Enter 를 누르면 릴리즈하고 종료"):
    """OE 페일세이프 배선에서는 프로세스가 끝나면 서보가 풀린다.
    각도를 세팅하고 혼을 끼우는 작업은 그동안 자세를 붙들고 있어야 한다."""
    if not OE.available:
        return          # 배선 전이면 서보가 알아서 유지하므로 기다릴 필요 없다
    try:
        input(f"  {msg} ")
    except (EOFError, KeyboardInterrupt):
        print()

# index -> (kit, 보드 채널). servo_controller.py 와 동기화 유지할 것.
# 배선이 짧아지는 헤더를 고른 결과.
# 좌측 보드(0x41)는 CH0 이 앞쪽, 우측 보드(0x40)는 반전 장착이라 CH15 가 앞쪽이다.
CHANNEL_MAP = {
    0: (kit2, 0),  1: (kit2, 1),  2: (kit2, 2),    # FL -> 0x41 CH0~2
    3: (kit, 13),  4: (kit, 14),  5: (kit, 15),    # FR -> 0x40 CH13~15
    6: (kit2, 13), 7: (kit2, 14), 8: (kit2, 15),   # RL -> 0x41 CH13~15
    9: (kit, 0),   10: (kit, 1),  11: (kit, 2),    # RR -> 0x40 CH0~2
}

NAMES = {
    0: "FL-Lower", 1: "FL-Upper", 2: "FL-Shoulder",
    3: "FR-Lower", 4: "FR-Upper", 5: "FR-Shoulder",
    6: "RL-Lower", 7: "RL-Upper", 8: "RL-Shoulder",
    9: "RR-Lower", 10: "RR-Upper", 11: "RR-Shoulder",
}

ADDR = {id(kit): "0x40", id(kit2): "0x41"}

# 오프셋은 Common/servo_map.py 한 곳에만 있다. servo_controller.py 도 거기서 읽는다.
#
# 예전에는 servo_controller.py 의 소스를 정규식으로 파싱했다. 값이 하드웨어를
# import 하는 파일 안에 리터럴로 있었기 때문인데, 그 방식은 원본의 표현이 조금만
# 바뀌어도 (예: 리터럴 -> import) 조용히 [90]*12 로 폴백해 서보를 엉뚱한 곳으로
# 보낸다. 이제는 그냥 import 한다.
DEFAULT_OFFSETS = list(SERVO_OFFSETS)
_OFFSET_SRC = "Common/servo_map.py"


# 각 관절을 어떤 자세에 맞춰야 하는지 (work06.md 5절)
# 기준 자세는 IK 의 theta=0, 즉 어깨관절부터 발끝까지 하나의 수직 직선이다.
# 실제 직립 자세가 아니라는 점에 주의 - 서 있을 때는 IK 가 무릎을 굽힌다.
POSE = {
    "Lower": (
        "대퇴부와 하퇴부의 내각 180도 (일직선)\n"
        "    확인: 측면에서 발끝이 무릎관절 바로 아래"
    ),
    "Upper": (
        "대퇴부가 수평면과 90도 (수직)\n"
        "    확인: 측면에서 무릎관절이 엉덩관절 바로 아래"
    ),
    "Shoulder": (
        "다리 축이 수직선과 0도 (좌우로 벌어지지 않음)\n"
        "    확인: 정면에서 발끝이 어깨관절 바로 아래"
    ),
}


def show_map():
    print("idx  관절          보드     채널")
    for i in range(12):
        k, ch = CHANNEL_MAP[i]
        print(f"{i:>3}  {NAMES[i]:<12}  {ADDR[id(k)]}   CH{ch}")


def sweep(sv, center, amp, cycles):
    def move(a, b, d=0.04):
        stp = 1 if b > a else -1
        for ang in range(a, b + stp, stp):
            sv.angle = ang
            time.sleep(d)

    sv.angle = center
    time.sleep(1.0)
    for c in range(cycles):
        print(f"  cycle {c + 1}/{cycles}", flush=True)
        move(center, center - amp)
        time.sleep(0.4)
        move(center - amp, center + amp)
        time.sleep(0.4)
        move(center + amp, center)
        time.sleep(0.6)


USED_CH = [0, 1, 2, 13, 14, 15]
SCAN_ORDER = [("0x41", kit2, ch) for ch in USED_CH] + [("0x40", kit, ch) for ch in USED_CH]


def scan(start=0):
    """모든 채널을 하나씩 흔들어 실제로 어느 관절이 물려있는지 확인한다."""
    print("각 채널을 90 기준 +-20도로 흔듭니다.")
    print("움직인 관절을 입력하고 Enter. 안 움직였으면 그냥 Enter.")
    print("r 입력 시 같은 채널 다시 흔들기. 중단은 Ctrl-C.\n")
    found = []
    for n, (addr, k, ch) in enumerate(SCAN_ORDER):
        if n < start:
            continue
        input(f"[{n}] {addr} CH{ch} - Enter 를 누르면 시작 ")
        while True:
            print(f"  {addr} CH{ch} 흔드는 중...", flush=True)
            sweep(k.servo[ch], 90, 20, 2)
            ans = input("  움직인 관절 (예: RR-Upper / r=다시): ").strip()
            if ans.lower() != "r":
                break
        found.append((f"{addr} CH{ch}", ans or "-"))
        print(f"  기록: {addr} CH{ch} = {ans or '-'}\n")

    print("\n=== 실측 결과 ===")
    for key, val in found:
        print(f"{key:<10} {val}")
    print("\n(중단했다면 다음 실행 시: servo_check.py scan <다음 번호>)")


def getch():
    """키 하나를 Enter 없이 읽는다. 방향키는 3바이트 이스케이프 시퀀스."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch += sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch


# 키 -> 각도 증분
STEP_KEYS = {
    "\x1b[A": 1, "+": 1, "=": 1,      # 위 방향키
    "\x1b[B": -1, "-": -1, "_": -1,   # 아래 방향키
    "\x1b[C": 5, "]": 5,              # 오른쪽 방향키
    "\x1b[D": -5, "[": -5,            # 왼쪽 방향키
}


def adjust(sv, start):
    """한 관절을 조정한다. 확정 각도를 반환하고, 중단이면 None."""
    angle = start
    sv.angle = angle

    if not sys.stdin.isatty():  # 파이프 등 TTY 가 아니면 줄 단위 입력
        while True:
            cmd = input(f"  현재 {angle}도 > ").strip().lower()
            if cmd == "":
                return angle
            if cmd == "q":
                return None
            if cmd == "r":
                angle = start
            elif cmd in ("+", "++", "-", "--"):
                angle += (5 if len(cmd) == 2 else 1) * (1 if cmd[0] == "+" else -1)
            else:
                try:
                    angle = int(cmd)
                except ValueError:
                    print("  숫자 또는 + - ++ -- r q Enter")
                    continue
            angle = max(1, min(179, angle))
            sv.angle = angle

    while True:
        print(f"\r  현재 {angle:>3}도   ", end="", flush=True)
        key = getch()
        if key in ("\r", "\n"):
            print()
            return angle
        if key in ("q", "\x03"):    # q 또는 Ctrl-C
            print()
            return None
        if key == "r":
            angle = start
        elif key == "g":            # 숫자 직접 입력
            print()
            try:
                angle = int(input("  이동할 각도: ").strip())
            except ValueError:
                continue
        elif key in STEP_KEYS:
            angle += STEP_KEYS[key]
        else:
            continue
        angle = max(1, min(179, angle))
        sv.angle = angle


# 캘리브레이션 순서: 다리마다 Shoulder -> Upper -> Lower.
# Shoulder 가 안 맞으면 다리가 옆으로 벌어진 상태이고, 그 상태에서 측면으로
# "대퇴부 수직" 이나 "발끝이 무릎 아래" 를 판정하면 왜곡된다.
# 인덱스는 다리 안에서 Lower, Upper, Shoulder 순이므로 다리별로 역순으로 돈다.
CAL_ORDER = [2, 1, 0,     # FL  Shoulder, Upper, Lower
             5, 4, 3,     # FR
             8, 7, 6,     # RL
             11, 10, 9]   # RR


def calibrate(only=None):
    """관절을 기준 자세에 맞추는 서보 각도를 찾아 _servo_offsets 를 실측한다.

    측정 순서는 CAL_ORDER (Shoulder -> Upper -> Lower). 결과 출력은
    붙여넣기 편하도록 인덱스 순서(0~11)를 유지한다.
    """
    print("기준 자세: 어깨관절부터 발끝까지 하나의 수직 직선 (IK 의 theta=0)")
    print("           실제 직립 자세가 아니다. 서 있을 때는 IK 가 무릎을 굽힌다.")
    print("           로봇이 수평으로 매달린 상태여야 기준이 맞는다.\n")
    if sys.stdin.isatty():
        print("  키 하나로 즉시 반응한다. Enter 불필요.")
        print("  위/아래 방향키 (또는 + -)   1도씩")
        print("  좌/우 방향키 (또는 [ ])     5도씩")
        print("  g  각도 직접 입력      r  시작값으로 되돌림")
        print("  Enter  확정하고 다음   q  중단하고 결과 출력\n")
    else:
        print("  숫자   해당 각도로 이동      +/-   1도씩      ++/--  5도씩")
        print("  r      시작값으로 되돌림     Enter 확정하고 다음")
        print("  q      중단하고 지금까지 결과 출력\n")

    print(f"시작값 출처: {os.path.normpath(_OFFSET_SRC)}")
    print(f"  {DEFAULT_OFFSETS}\n")

    offsets = list(DEFAULT_OFFSETS)
    measured = set()
    targets = [only] if only is not None else CAL_ORDER

    for i in targets:
        kit_obj, ch = CHANNEL_MAP[i]
        joint = NAMES[i].split("-")[1]

        print(f"[idx {i}] {NAMES[i]}  ({ADDR[id(kit_obj)]} CH{ch})")
        print(f"  목표 자세: {POSE[joint]}")

        result = adjust(kit_obj.servo[ch], DEFAULT_OFFSETS[i])
        if result is None:
            print("\n중단합니다.")
            show_offsets(offsets, measured)
            return
        offsets[i] = result
        measured.add(i)
        print(f"  확정: {NAMES[i]} = {result}\n")

    show_offsets(offsets, measured)


# 이 범위를 벗어난 오프셋은 서보 내부 스토퍼에 밀어붙일 위험이 있다.
# 좌측 무릎(FL/RL-Lower)의 179 는 "가동 한계에서 다리가 곧게 펴진다" 는 뜻이라
# 그대로 명령하면 스토퍼를 계속 미는 stall 이 된다. DS3235 는 신호를 끊어도
# setpoint 를 유지하므로 스크립트가 끝나도 계속 밀고 있다.
SAFE_BAND = (8, 172)


def home(force=False):
    """12개 서보를 각자의 오프셋(기준 자세)으로 보낸다.

    기준 자세는 다리를 곧게 편 수직선이다. 무릎이 약간 굽은 직립 자세는
    IK 가 필요하므로 ../servo_controller.py 를 실행할 것.

    SAFE_BAND 를 벗어난 오프셋은 기본적으로 건너뛴다. force=True 로 강제할 수
    있지만, 그 관절은 가동 한계를 계속 밀게 되므로 짧게만 쓸 것.
    """
    print("기준 자세(다리 곧게 편 상태)로 이동한다.")
    print("무릎이 굽은 직립 자세는 ../servo_controller.py 를 실행할 것.\n")
    lo, hi = SAFE_BAND
    skipped = []
    for i in range(12):
        kit_obj, ch = CHANNEL_MAP[i]
        target = DEFAULT_OFFSETS[i]
        if not lo <= target <= hi and not force:
            skipped.append(i)
            print(f"  idx {i:>2}  {NAMES[i]:<12} -- {target:>3}도 건너뜀 (가동 한계 stall 위험)")
            continue
        kit_obj.servo[ch].angle = target
        print(f"  idx {i:>2}  {NAMES[i]:<12} -> {target:>3}도")
        time.sleep(0.15)  # 12개 동시 기동 시 돌입 전류가 몰리는 것을 피한다
    holdUntilEnter()
    print("\n완료.")
    if skipped:
        print(f"  {len(skipped)}개를 건너뛰었다: {[NAMES[i] for i in skipped]}")
        print(f"  오프셋이 {lo}~{hi} 밖이라 서보를 스토퍼에 밀어붙인다.")
        print("  혼을 스플라인 한 칸(약 18도) 안쪽으로 다시 물려 여유를 만드는 것이 근본 해결이다.")
        print("  꼭 필요하면:  servo_check.py home force")


def release(only=None):
    """서보의 PWM 을 끊어 유지 토크를 없앤다.

    프로세스가 끝나도 PCA9685 는 마지막 펄스폭을 계속 내보내므로, 서보는 목표
    각도를 물고 stall 전류를 먹는다. 테스트를 마쳤으면 이걸로 풀어둘 것.

    angle = None 은 duty_cycle 을 0 으로 만들어 펄스 자체를 멈춘다.
    """
    targets = [only] if only is not None else range(12)
    print("주의: 지면에 서 있는 상태에서 풀면 그대로 주저앉는다. 매단 상태에서 실행할 것.\n")
    for i in targets:
        kit_obj, ch = CHANNEL_MAP[i]
        kit_obj.servo[ch].angle = None
        print(f"  idx {i:>2}  {NAMES[i]:<12} ({ADDR[id(kit_obj)]} CH{ch}) 펄스 정지")
    if OE.available and only is None:
        OE.release()
        print("\n  OE 고임피던스 - 신호선을 놓았다. 실제로 힘이 빠진다.")
    elif not OE.available:
        print(f"\n  주의: OE 제어 불가 ({OE.reason or 'OE 배선 없음'}).")
        print("  이 로봇의 DS 계열 서보는 펄스를 끊어도(LOW) 마지막 목표값을 유지한다.")
        print("  실제 릴리즈에는 OE 배선이 필요하다. Common/servo_oe.py 참고.")
    print("\n완료. 다시 힘을 주려면: servo_check.py home")


def status():
    """PCA9685 의 LEDn_ON/OFF 레지스터를 읽어 채널별 구동 여부를 본다.

    릴리즈가 먹었는지 판정하는 유일하게 확실한 방법이다. 관절이 늘어지는지로는
    판단할 수 없다 - Upper/Lower 는 다리가 회전축 바로 아래에 매달려 중력 토크가
    거의 0 이므로, 힘이 빠져도 그 자리에 그대로 있다. Shoulder 만 축에서 l1(50mm)
    옆으로 떨어져 있어 눈에 보이게 늘어진다.

    레지스터를 읽기만 하므로 서보는 움직이지 않는다.
    """
    print("idx  관절          보드   CH   on     off    상태")
    for i in range(12):
        kit_obj, ch = CHANNEL_MAP[i]
        on, off = kit_obj._pca.pwm_regs[ch]   # ServoKit 이 감싼 PCA9685 를 직접 읽는다
        if off == 0x1000:                     # full-off 비트 (LEDn_OFF_H bit4)
            state = "릴리즈됨"
        elif on == 0x1000:
            state = "FULL ON (비정상)"
        else:
            us = off / 4096 * (1e6 / kit_obj._pca.frequency)
            state = f"구동 중 {us:.0f}us"
        print(f"{i:>3}  {NAMES[i]:<12}  {ADDR[id(kit_obj)]}  {ch:>2}  {on:>5}  {off:>5}  {state}")


def show_offsets(offsets, measured):
    """measured 에 없는 항목은 이번 실행에서 재지 않은 기존값이다."""
    print("\n=== 오프셋 ===")
    for i in range(12):
        if i not in measured:
            note = "  (이번에 측정 안 함 - 기존값)"
        elif offsets[i] != DEFAULT_OFFSETS[i]:
            note = f"  <- 이번 측정 (기존 {DEFAULT_OFFSETS[i]})"
        else:
            note = "  <- 이번 측정 (기존값과 동일)"
        print(f"  idx {i:>2}  {NAMES[i]:<12} {offsets[i]:>3}{note}")

    missing = [i for i in range(12) if i not in measured]
    if missing:
        print(f"\n  주의: {len(missing)}개 관절이 이번 실행에서 측정되지 않았다: {missing}")
        print("  아래 배열의 해당 항목은 이 스크립트의 DEFAULT_OFFSETS 값일 뿐이다.")
        print("  그대로 붙여넣으면 다른 실행에서 잰 값을 덮어쓸 수 있으니 주의할 것.")
        print("  전체를 다시 재려면 인덱스 없이:  servo_check.py cal")
    print("\nCommon/servo_map.py 에 붙여넣을 값:")
    print(f"SERVO_OFFSETS = {offsets}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "map":
        show_map()
        return

    if sys.argv[1] == "home":
        home(force=len(sys.argv) > 2 and sys.argv[2] == "force")
        return

    if sys.argv[1] == "status":
        status()
        return

    if sys.argv[1] == "release":
        release(int(sys.argv[2]) if len(sys.argv) > 2 else None)
        return

    if sys.argv[1] == "cal":
        calibrate(int(sys.argv[2]) if len(sys.argv) > 2 else None)
        return

    if sys.argv[1] == "scan":
        scan(int(sys.argv[2]) if len(sys.argv) > 2 else 0)
        return

    if sys.argv[1] == "raw":
        addr = 0x40 if sys.argv[2].lstrip("0x") in ("40", "") else 0x41
        kit_obj = kit if addr == 0x40 else kit2
        ch = int(sys.argv[3])
        if len(sys.argv) > 4 and sys.argv[4] != "sweep":
            kit_obj.servo[ch].angle = int(sys.argv[4])
            print(f"0x{addr:02x} CH{ch} -> {sys.argv[4]}도")
        else:
            print(f"0x{addr:02x} CH{ch} sweep 90+-20 x3")
            sweep(kit_obj.servo[ch], 90, 20, 3)
            print("DONE - 90도 복귀")
        return

    if len(sys.argv) < 3:
        print(__doc__)
        return

    idx = int(sys.argv[1])
    if idx not in CHANNEL_MAP:
        print(f"인덱스는 0~11 이어야 합니다: {idx}")
        return

    kit_obj, ch = CHANNEL_MAP[idx]
    sv = kit_obj.servo[ch]
    label = f"idx{idx} {NAMES[idx]} ({ADDR[id(kit_obj)]} CH{ch})"

    if sys.argv[2] == "sweep":
        amp = int(sys.argv[3]) if len(sys.argv) > 3 else 20
        cycles = int(sys.argv[4]) if len(sys.argv) > 4 else 3
        print(f"{label} sweep 90+-{amp} x{cycles}")
        sweep(sv, 90, amp, cycles)
        print("DONE - 90도 복귀")
    else:
        angle = int(sys.argv[2])
        if not 0 <= angle <= 180:
            print(f"각도는 0~180 이어야 합니다: {angle}")
            return
        sv.angle = angle
        print(f"{label} -> {angle}도")
        holdUntilEnter("혼 결합이 끝나면 Enter (그때까지 이 자세를 유지한다)")


if __name__ == "__main__":
    main()
