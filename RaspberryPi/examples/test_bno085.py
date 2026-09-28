"""BNO085 IMU I2C 연결/축 방향 확인용 진단 스크립트.

배경: study/minho/work14.md 5.4절 참고.

배선 (실측)
-----------
| 핀   | RPi 물리핀        |
|------|-------------------|
| VIN  | 3.3V (1 또는 17)   |
| GND  | 아무 GND          |
| SDA  | GPIO2 (물리핀 3)   |
| SCL  | GPIO3 (물리핀 5)   |
| RST  | GPIO17 (물리핀 11) - 2026-09-29 추가, 스톨 자동 복구용. |
|      | 한때 Common/servo_oe.py 의 PCA9685 OE 핀과 겹쳐서(spotmicro-gait.service |
|      | 가 상시 점유) GPIO27 로 옮겼었으나, OE 기능 자체를 제거하면서 GPIO17 로 |
|      | 되돌렸다 - servo_oe.py 는 더 이상 이 저장소에 없다. |

I2C 주소는 0x4B (i2cdetect -y 1 실측, 2026-09-28). work14.md 작성 시점 예상은
0x4A였으나 실측이 다르다. PCA9685의 0x40/0x41과는 겹치지 않는다.

축 리매핑
---------
센서 부착 방향이 로봇 정면 기준으로 90도 돌아가 있다 (미러링이 아니라
정상 우수좌표계 회전). 그래서 로봇 좌표계로 옮기려면:

    robot_forward =  sensor_Y
    robot_left    =  sensor_X   (robot_right = -sensor_X)
    robot_down    =  sensor_Z   (robot_up    = -sensor_Z)

이 스크립트는 raw 센서값과 리매핑한 robot-frame 값을 같이 출력한다.
로봇을 앞으로/옆으로/위아래로 기울여보면서 robot-frame 쪽 부호가
예상과 맞는지 눈으로 확인하는 용도다 (조립 실수로 진짜 미러링됐을
가능성은 아직 배제 못 했다 - work14.md 5.4절 참고).

몽키패치 - 손상 패킷 스킵
-----------------------
RPi 의 하드웨어 I2C 컨트롤러(BCM283x/2711)가 BNO085 의 clock stretching 을
스펙대로 못 받아줘서 패킷이 간헐적으로 깨진다. 이건 잘 알려진 하드웨어 쪽
이슈고(adafruit/Adafruit_CircuitPython_BNO08x#9), 클럭을 낮춰도 없앨 수 없다 -
다만 발생 빈도를 낮출 뿐이다.

문제는 adafruit_bno08x 라이브러리가 이 상황에서 모르는 report_id 를 만나면
그냥 KeyError 를 다시 던져서 프로그램 전체가 죽는다는 것 - 정상적인 라이브러리라면
그 패킷 하나만 버리고 다음 걸 기다려야 한다. 그래서 여기서 `BNO08X._handle_packet`
을 감싸서, 예외가 나면 그 패킷만 버리고(`_packet_slices` 비우기) 계속 진행하게
만든다. site-packages 의 원본 파일은 건드리지 않고 이 프로세스 안에서만 동작을
바꾼다.

이 패치는 근본 원인(클럭 스트레칭 처리 미흡)을 고치는 게 아니라 증상(크래시)만
없앤다. 그래서 이 스크립트는 정상/손상 패킷 수를 세어 손상율을 주기적으로 찍는다 -
손상율이 낮으면(가끔 한 프레임 드롭) 이대로 계속 쓸 만하고, 너무 높으면 소프트웨어
I2C 나 UART-RVC 같은 다른 완화책이 필요하다는 뜻이다.

패치가 못 막는 실패 - 버스 트랜잭션 자체 실패
--------------------------------------------
위 패치는 "패킷은 받았는데 내용이 깨졌다" 상황만 막는다. 실측해보니 그보다 더
심하게, 헤더 4바이트를 읽는 I2C 버스 트랜잭션 자체가 `OSError: [Errno 5]
Input/output error` 로 실패하는 경우도 있었다 - 이건 `_handle_packet` 이전
단계라 그 패치로는 못 막는다. 원인은 같다(clock stretching 처리 미흡), 다만
이번엔 정도가 더 심해서 패킷 파싱까지 가지도 못한 것이다.

그래서 메인 루프에서 accel/gyro/quaternion 을 읽는 한 사이클 전체도
try/except OSError 로 감싸서, 실패하면 그 사이클만 버리고 넘어가게 했다.
연속 실패가 계속되면(버스가 눌린 채 안 풀리는 상황일 수 있다) 경고를 찍는다 -
이 경우는 재시도로 해결 안 되니 배선/전원을 점검해야 한다는 신호다.

패치도 못 막는 실패 - report_id 는 맞는데 payload 가 오염됨
-----------------------------------------------------------
실측 중 report_id 는 정상이라 패킷 파싱까지는 성공하는데, 값 자체가 물리적으로
말이 안 되는 경우를 발견했다 (로봇이 가만히 있는데 accel y 가 갑자기
+127.66 로 튐, 정확히 같은 숫자가 여러 번 재현됨 - 랜덤 노이즈가 아니라
재현 가능한 손상 패턴이라는 뜻). 이건 `_handle_packet` 패치로도 못 잡는다 -
그 함수 입장에서는 "정상적으로 파싱된 리포트"이기 때문이다.

그래서 물리적으로 가능한 범위를 벗어나면 버리는 sanity filter 를 추가했다
(가속도 크기 40 m/s^2 초과, 자이로 크기 35 rad/s 초과 - 센서 풀스케일
±2000dps 근처, 쿼터니언 norm 이 1 에서 0.3 이상 벗어남). 이것도
근본 원인을 고치는 게 아니라 증상을 걸러내는 것 - 세 가지 통계(패킷 손상율,
버스 실패율, sanity 거부율)를 다 같이 봐야 "실제로 쓸 수 있는 데이터 비율"이
나온다.

네 번째 실패 양상 - 통신은 되는데 새 리포트가 안 옴 (스톨)
------------------------------------------------------
adafruit_bno08x.i2c.BNO08X_I2C._data_ready 는 헤더 4바이트를 읽어서
`data_length > 0` 일 때만 True 를 반환한다. 즉 I2C 통신 자체는 계속 성공하는데
BNO085 가 "새 리포트 있음" 신호를 안 주는 상태에 빠지면, `_process_available_packets`
의 while 루프에 아예 안 들어가서 `_handle_packet` 이 호출되지 않고(패킷 통계가
안 늘어남), acceleration/gyro/quaternion 은 예외 없이 마지막 캐시값을 그대로
반환한다 - 크래시도 안 하고 read 실패로도 안 잡히는데 실제로는 죽은 값을 계속
읽는 상황이다. 이 라이브러리는 INT/RST 핀 없이 순수 폴링이라 이런 정지를
스스로 감지도 복구도 못 한다.

그래서 패킷 통계(ok+dropped 합)가 STALL_WARN_S 이상 전혀 안 늘어나면 경고를
찍는다.

스톨 자동 복구 - RST 핀
-----------------------
처음엔 RST 핀을 안 썼다(reset=None). adafruit_bno08x 의 `hard_reset()` 은
`self._reset` 이 없으면 그냥 아무것도 안 하고 리턴하므로, 사실상 죽어있는
기능이었다. `soft_reset()` 은 I2C 로 리셋 "명령"을 보내는 방식이라 버스
자체가 막혀있으면 이것도 같이 실패할 수 있다 - 실측한 스톨은 정확히 이
상황(OSError 한 번 나면 그 뒤로 다시는 회복 안 됨)과 일치했다.

RST 를 GPIO17(물리핀 11)에 연결하고 `reset=` 으로 넘기면 `hard_reset()` 이
실제로 그 핀을 HIGH->LOW->HIGH 로 토글해서(10ms 펄스) 칩을 물리적으로
재부팅시킨다. 이건 I2C 버스 상태와 완전히 독립적인 GPIO 신호라 버스가
막혀있어도 무조건 작동한다. 그래서 스톨이 감지되면 `bno.initialize()`
(내부적으로 hard_reset -> soft_reset -> ID 확인을 순서대로 한다) 를 호출해
센서를 재초기화하고, feature 를 다시 enable 해서 자동 복구를 시도한다.

RST 핀을 digitalio 로 안 잡고 gpiod 로 잡는 이유
------------------------------------------------
처음엔 `digitalio.DigitalInOut(board.D<n>)` 로 시도했는데
`RuntimeError: No access to /dev/mem. Try running as root!` 로 죽었다.
digitalio(Blinka)/RPi.GPIO 는 /dev/mem 을 직접 열어야 해서 root 가 필요하다 -
이 저장소가 이미 겪은 문제고(`/dev/gpiomem` 도 이 머신에서는 root 전용으로
잠겨있다, `crw-------`). 예전에는 `Common/servo_oe.py` 가 같은 이유로
RPi.GPIO 대신 gpiod(문자 장치 `/dev/gpiochipN`)를 썼는데(지금은 OE 기능
자체가 삭제되어 그 파일은 없다), 여기서도 같은 패턴을 따라
`_GpiodResetPin` 이 digitalio.DigitalInOut 이 흉내내는 최소 인터페이스
(`.direction =`, `.value =` 대입)만 gpiod 위에 얹어서, adafruit_bno08x 의
`hard_reset()` 코드를 그대로 쓸 수 있게 한다.
"""

import sys
import time

import board
import busio

import adafruit_bno08x
from adafruit_bno08x import (
    BNO_REPORT_ACCELEROMETER,
    BNO_REPORT_GYROSCOPE,
    BNO_REPORT_ROTATION_VECTOR,
)
from adafruit_bno08x.i2c import BNO08X_I2C

I2C_ADDRESS = 0x4B
RST_CHIP = "/dev/gpiochip0"
RST_LINE = 17  # BCM GPIO17, 물리핀 11
PRINT_INTERVAL_S = 0.2
STATS_INTERVAL_S = 2.0

_packet_stats = {"ok": 0, "dropped": 0}
_cycle_stats = {"ok": 0, "failed": 0}
_sanity_stats = {"ok": 0, "rejected": 0}
_recovery_stats = {"attempts": 0, "success": 0}
CONSECUTIVE_FAILURE_WARN = 20
STALL_WARN_S = 2.0

# 로봇이 아무리 거칠게 움직여도 이 이상은 물리적으로 말이 안 된다 (~4G).
ACCEL_SANITY_LIMIT_MS2 = 40.0
# 정상 쿼터니언은 unit norm(=1) 이어야 한다. 이만큼 벗어나면 오염으로 본다.
QUAT_NORM_TOLERANCE = 0.3
# BNO08x 자이로 풀스케일이 대략 ±2000dps(약 34.9 rad/s) 근처다. 그 이상은
# 센서 스펙 자체를 벗어나는 값이라 오염으로 본다.
GYRO_SANITY_LIMIT_RAD_S = 35.0


def _is_sane(ax, ay, az, gx, gy, gz, qi, qj, qk, qr):
    accel_mag = (ax * ax + ay * ay + az * az) ** 0.5
    if accel_mag > ACCEL_SANITY_LIMIT_MS2:
        return False
    gyro_mag = (gx * gx + gy * gy + gz * gz) ** 0.5
    if gyro_mag > GYRO_SANITY_LIMIT_RAD_S:
        return False
    quat_norm = (qi * qi + qj * qj + qk * qk + qr * qr) ** 0.5
    if abs(quat_norm - 1.0) > QUAT_NORM_TOLERANCE:
        return False
    return True


def _patch_skip_corrupt_packets():
    """BNO08X._handle_packet 을 감싸서 손상 패킷을 죽지 않고 버리게 만든다."""

    def _handle_packet_skip_unknown(self, packet):
        try:
            adafruit_bno08x._separate_batch(packet, self._packet_slices)
            while len(self._packet_slices) > 0:
                self._process_report(*self._packet_slices.pop())
        except Exception:
            self._packet_slices.clear()
            _packet_stats["dropped"] += 1
            return
        _packet_stats["ok"] += 1

    adafruit_bno08x.BNO08X._handle_packet = _handle_packet_skip_unknown


HARD_RESET_SETTLE_S = 0.5


def _patch_hard_reset_settle_time():
    """hard_reset() 직후 칩이 완전히 부팅될 시간을 더 준다.

    라이브러리 원본은 RST 토글 후 10ms 만 쉬고 바로 soft_reset() (I2C 쓰기)
    으로 넘어간다. 실측해보니 이 환경에서는 그 시점에 곧바로 쓰기를 시도하면
    `OSError: [Errno 5] Input/output error` 로 매번 실패한다 - BNO085 가
    리셋 후 SHTP 통신이 가능해지기까지 10ms 보다 더 걸리는 것으로 보인다.
    """
    original_hard_reset = adafruit_bno08x.BNO08X.hard_reset

    def _hard_reset_then_settle(self):
        original_hard_reset(self)
        time.sleep(HARD_RESET_SETTLE_S)

    adafruit_bno08x.BNO08X.hard_reset = _hard_reset_then_settle


def sensor_to_robot(x, y, z):
    """센서 좌표계 -> 로봇 좌표계 (forward, left, down)."""
    return y, x, z


class _GpiodResetPin:
    """adafruit_bno08x.hard_reset() 이 기대하는 digitalio.DigitalInOut 흉내.

    hard_reset() 은 `.direction = ...` 과 `.value = ...` 대입만 하므로 그
    인터페이스만 gpiod 위에 얹는다 (libgpiod v2/v1 폴백) - 이 저장소는
    root 없이 돌아가야 해서 RPi.GPIO/digitalio 대신 gpiod(문자 장치)를 쓴다.
    """

    def __init__(self, chip=RST_CHIP, line=RST_LINE):
        import gpiod

        self._line = line
        try:
            from gpiod.line import Direction, Value

            self._req = gpiod.request_lines(
                chip,
                consumer="bno085-rst",
                config={
                    line: gpiod.LineSettings(
                        direction=Direction.OUTPUT, output_value=Value.ACTIVE
                    )
                },
            )
            self._backend = "v2"
            self._active, self._inactive = Value.ACTIVE, Value.INACTIVE
        except (AttributeError, ImportError):
            chip_obj = gpiod.Chip(chip)
            line_obj = chip_obj.get_line(line)
            line_obj.request(consumer="bno085-rst", type=gpiod.LINE_REQ_DIR_OUT)
            self._req = line_obj
            self._chip = chip_obj
            self._backend = "v1"

    @property
    def direction(self):
        return None

    @direction.setter
    def direction(self, _value):
        pass  # 이미 OUTPUT 으로 요청했다.

    @property
    def value(self):
        return None

    @value.setter
    def value(self, value):
        if self._backend == "v2":
            self._req.set_value(self._line, self._active if value else self._inactive)
        else:
            self._req.set_value(1 if value else 0)


def _enable_features(bno):
    bno.enable_feature(BNO_REPORT_ACCELEROMETER)
    bno.enable_feature(BNO_REPORT_GYROSCOPE)
    bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)


INIT_RETRY_ATTEMPTS = 3
INIT_RETRY_DELAY_S = 1.0


def _initialize_with_retry(bno):
    """bno.initialize() 를 재시도한다.

    initialize() 내부에서 hard_reset()/soft_reset() 호출은 try 로 감싸여
    있지 않다 (감싸인 건 _check_id() 뿐) - 그래서 리셋 직후 버스가 아직
    안정화되기 전에 쓰기를 시도하면 OSError 가 그대로 빠져나간다. 실측으로
    확인했다. 그래서 여기서 한 번 더 감싸서 재시도한다.
    """
    last_exc = None
    for attempt in range(1, INIT_RETRY_ATTEMPTS + 1):
        try:
            bno.initialize()
            return
        except Exception as exc:
            last_exc = exc
            print(f"  [초기화 재시도 {attempt}/{INIT_RETRY_ATTEMPTS}] {exc}")
            time.sleep(INIT_RETRY_DELAY_S)
    raise last_exc


def _recover_stalled_sensor(bno):
    """RST 핀으로 센서를 물리적으로 재부팅하고 feature 를 다시 켠다.

    initialize() 가 내부적으로 hard_reset (RST 핀 토글, I2C 상태와 무관하게
    항상 동작) -> soft_reset -> ID 확인을 한다. 실패하면 RuntimeError/OSError.
    """
    _recovery_stats["attempts"] += 1
    try:
        _initialize_with_retry(bno)
        _enable_features(bno)
    except Exception as exc:
        print(f"  [복구 실패] {exc}")
        return False
    _recovery_stats["success"] += 1
    return True


def _connect_with_retry(i2c, reset_pin, attempts=INIT_RETRY_ATTEMPTS, delay_s=INIT_RETRY_DELAY_S):
    """BNO08X_I2C(...) 생성을 재시도한다 - 이유는 _initialize_with_retry 와 같다."""
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return BNO08X_I2C(i2c, reset=reset_pin, address=I2C_ADDRESS)
        except Exception as exc:
            last_exc = exc
            print(f"  [연결 재시도 {attempt}/{attempts}] {exc}")
            time.sleep(delay_s)
    raise last_exc


def main():
    _patch_skip_corrupt_packets()
    _patch_hard_reset_settle_time()

    i2c = busio.I2C(board.SCL, board.SDA, frequency=400_000)
    reset_pin = _GpiodResetPin(RST_CHIP, RST_LINE)

    try:
        bno = _connect_with_retry(i2c, reset_pin)
    except Exception as exc:
        print(
            f"BNO085 연결 실패 (주소 0x{I2C_ADDRESS:02X}): {exc}\n"
            "SDA(GPIO2/핀3), SCL(GPIO3/핀5), VIN(3.3V), GND, "
            "RST(GPIO17/핀11) 배선을 확인할 것.\n"
            "i2cdetect -y 1 로 주소가 실제로 잡히는지도 별도 터미널에서 확인 가능.",
            file=sys.stderr,
        )
        raise

    _enable_features(bno)

    print(f"BNO085 연결됨 (0x{I2C_ADDRESS:02X}). Ctrl+C 로 종료.")
    print("로봇을 앞/옆/위아래로 기울여가며 robot-frame 부호가 맞는지 확인할 것.")
    print(f"{STATS_INTERVAL_S:.0f}초마다 패킷 손상율도 같이 찍는다.\n")

    last_stats_print = time.monotonic()
    consecutive_failures = 0
    last_packet_total = 0
    stall_since = None
    stall_warned = False

    try:
        while True:
            try:
                ax, ay, az = bno.acceleration
                gx, gy, gz = bno.gyro
                qi, qj, qk, qr = bno.quaternion
            except OSError as exc:
                _cycle_stats["failed"] += 1
                consecutive_failures += 1
                print(f"  [읽기 실패] {exc}")
                if consecutive_failures == CONSECUTIVE_FAILURE_WARN:
                    print(
                        f"  [경고] {CONSECUTIVE_FAILURE_WARN}회 연속 실패 - "
                        "재시도로 안 풀린다. 버스가 눌린 채 안 풀렸을 수 있다. "
                        "배선/전원을 점검할 것."
                    )
                time.sleep(PRINT_INTERVAL_S)
                continue

            _cycle_stats["ok"] += 1
            consecutive_failures = 0

            packet_total = _packet_stats["ok"] + _packet_stats["dropped"]
            if packet_total == last_packet_total:
                if stall_since is None:
                    stall_since = time.monotonic()
                elif not stall_warned and time.monotonic() - stall_since >= STALL_WARN_S:
                    print(
                        f"  [경고] {STALL_WARN_S:.0f}초 이상 새 패킷 없음 - "
                        "통신은 되는데 센서가 스트리밍을 멈췄을 수 있다. "
                        "RST 로 재초기화를 시도한다."
                    )
                    stall_warned = True
                    if _recover_stalled_sensor(bno):
                        print("  [복구] 센서 재초기화 성공.")
                        stall_since = None
                        stall_warned = False
                        last_packet_total = _packet_stats["ok"] + _packet_stats["dropped"]
                    else:
                        print(
                            f"  [복구] 재초기화 실패 - {STALL_WARN_S:.0f}초 후 "
                            "다시 시도한다."
                        )
                        stall_since = time.monotonic()
                        stall_warned = False
            else:
                if stall_warned:
                    print("  [알림] 새 패킷 재개됨.")
                stall_since = None
                stall_warned = False
                last_packet_total = packet_total

            if not _is_sane(ax, ay, az, gx, gy, gz, qi, qj, qk, qr):
                _sanity_stats["rejected"] += 1
                print(
                    f"  [값 거부] 물리적으로 말이 안 되는 값 - "
                    f"accel=({ax:+.2f},{ay:+.2f},{az:+.2f}) "
                    f"gyro=({gx:+.2f},{gy:+.2f},{gz:+.2f}) "
                    f"quat=({qi:+.2f},{qj:+.2f},{qk:+.2f},{qr:+.2f})"
                )
                time.sleep(PRINT_INTERVAL_S)
                continue
            _sanity_stats["ok"] += 1

            fwd, left, down = sensor_to_robot(ax, ay, az)

            print(
                f"accel(raw) x={ax:+6.2f} y={ay:+6.2f} z={az:+6.2f}  "
                f"| robot-frame forward={fwd:+6.2f} left={left:+6.2f} down={down:+6.2f}  "
                f"| gyro x={gx:+6.2f} y={gy:+6.2f} z={gz:+6.2f}  "
                f"| quat i={qi:+.2f} j={qj:+.2f} k={qk:+.2f} r={qr:+.2f}"
            )

            now = time.monotonic()
            if now - last_stats_print >= STATS_INTERVAL_S:
                ok = _packet_stats["ok"]
                dropped = _packet_stats["dropped"]
                total = ok + dropped
                drop_rate = (dropped / total * 100) if total else 0.0

                cycle_ok = _cycle_stats["ok"]
                cycle_failed = _cycle_stats["failed"]
                cycle_total = cycle_ok + cycle_failed
                cycle_fail_rate = (cycle_failed / cycle_total * 100) if cycle_total else 0.0

                sanity_ok = _sanity_stats["ok"]
                sanity_rejected = _sanity_stats["rejected"]
                sanity_total = sanity_ok + sanity_rejected
                sanity_reject_rate = (
                    (sanity_rejected / sanity_total * 100) if sanity_total else 0.0
                )

                print(
                    f"  [패킷 통계] 정상={ok} 손상={dropped} 손상율={drop_rate:.1f}%  "
                    f"| [읽기 사이클] 정상={cycle_ok} 실패={cycle_failed} "
                    f"실패율={cycle_fail_rate:.1f}%  "
                    f"| [값 검증] 정상={sanity_ok} 거부={sanity_rejected} "
                    f"거부율={sanity_reject_rate:.1f}%  "
                    f"| [스톨 복구] 시도={_recovery_stats['attempts']} "
                    f"성공={_recovery_stats['success']}"
                )
                last_stats_print = now

            time.sleep(PRINT_INTERVAL_S)
    except KeyboardInterrupt:
        print("\n중단됨.")


if __name__ == "__main__":
    main()
