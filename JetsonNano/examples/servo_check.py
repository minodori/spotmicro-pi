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

인덱스는 servo_controller.py 의 _channel_map 과 동일:
    [0]~[2] FL / [3]~[5] FR / [6]~[8] RL / [9]~[11] RR
    각 다리 안에서 Lower, Upper, Shoulder 순서.
"""
import readline  # noqa: F401  input() 에서 방향키/백스페이스 편집 활성화
import sys
import time

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


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "map":
        show_map()
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
