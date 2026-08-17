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
    python3 servo_check.py home                         12개를 기준 자세(오프셋)로 한번에

직립 자세(IK 로 무릎을 굽힌 자세)는 ../servo_controller.py 를 실행한다.

인덱스는 servo_controller.py 의 _channel_map 과 동일:
    [0]~[2] FL / [3]~[5] FR / [6]~[8] RL / [9]~[11] RR
    각 다리 안에서 Lower, Upper, Shoulder 순서.
"""
import os
import re
import readline  # noqa: F401  input() 에서 방향키/백스페이스 편집 활성화
import sys
import termios
import time
import tty

import board
import busio
from adafruit_servokit import ServoKit

i2c = busio.I2C(board.SCL, board.SDA)
kit = ServoKit(channels=16, i2c=i2c, address=0x40)   # 배터리 우측 보드 -> 오른쪽 다리
kit2 = ServoKit(channels=16, i2c=i2c, address=0x41)  # 배터리 좌측 보드 -> 왼쪽 다리

# 코드가 쓰는 건 CH0~5 뿐이지만, 배선 확인용으로 전 채널을 같은 조건으로 맞춰둔다.
for ch in range(16):
    kit.servo[ch].set_pulse_width_range(500, 2500)
    kit2.servo[ch].set_pulse_width_range(500, 2500)

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

def _loadOffsets():
    """servo_controller.py 의 _servo_offsets 를 읽는다.

    값을 이 파일에도 적어두면 두 곳이 어긋나므로 원본에서 직접 가져온다.
    주석 처리된 줄은 건너뛴다.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "servo_controller.py")
    pattern = re.compile(r"^\s*self\._servo_offsets\s*=\s*\[([^\]]*)\]")
    try:
        with open(path) as f:
            for line in f:
                m = pattern.match(line)
                if m:
                    vals = [int(x) for x in m.group(1).split(",")]
                    if len(vals) == 12:
                        return vals, path
    except OSError:
        pass
    print("경고: servo_controller.py 에서 _servo_offsets 를 읽지 못했다. 90 으로 시작한다.")
    return [90] * 12, path


DEFAULT_OFFSETS, _OFFSET_SRC = _loadOffsets()

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


def calibrate(only=None):
    """관절을 기준 자세에 맞추는 서보 각도를 찾아 _servo_offsets 를 실측한다."""
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
    targets = [only] if only is not None else range(12)

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


def home():
    """12개 서보를 각자의 오프셋(기준 자세)으로 보낸다.

    기준 자세는 다리를 곧게 편 수직선이다. 무릎이 약간 굽은 직립 자세는
    IK 가 필요하므로 ../servo_controller.py 를 실행할 것.
    """
    print("기준 자세(다리 곧게 편 상태)로 이동한다.")
    print("무릎이 굽은 직립 자세는 ../servo_controller.py 를 실행할 것.\n")
    for i in range(12):
        kit_obj, ch = CHANNEL_MAP[i]
        kit_obj.servo[ch].angle = DEFAULT_OFFSETS[i]
        print(f"  idx {i:>2}  {NAMES[i]:<12} -> {DEFAULT_OFFSETS[i]:>3}도")
        time.sleep(0.15)  # 12개 동시 기동 시 돌입 전류가 몰리는 것을 피한다
    print("\n완료.")


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
    print("\nservo_controller.py 에 붙여넣을 값:")
    print(f"self._servo_offsets = {offsets}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "map":
        show_map()
        return

    if sys.argv[1] == "home":
        home()
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


if __name__ == "__main__":
    main()
