"""PCA9685 의 OE(Output Enable) 로 서보를 실제로 릴리즈한다.

배경
----
`angle = None` (PWM full-off) 은 신호선을 **능동적으로 LOW 로 끌어내린다**.
이 로봇의 DS 계열 서보는 그것을 유효 입력으로 보고 마지막 목표값을 계속 유지한다
(실측: 신호선을 뽑으면 즉시 힘이 빠진다). 즉 선이 "뜬 상태" 여야만 릴리즈된다.

PCA9685 는 MODE2 의 OUTNE 비트를 `10` 으로 두면 **OE 가 HIGH 일 때 모든 출력이
고임피던스**가 된다. 신호선을 12개 동시에 뽑는 것과 같은 효과다.

배선 (페일세이프 방향으로 잡는다)
--------------------------------
    OE ──┬── 1k ── 3.3V        풀업. 아무도 구동하지 않으면 HIGH = 릴리즈
         └────────  GPIO       소프트웨어가 LOW 로 내려야 서보가 산다

보드에는 보통 OE 에 10k 풀다운이 있다. 1k 풀업과 만나면 3.3 x 10/11 = 3.0V 로
HIGH 가 되고, GPIO 가 LOW 로 당길 때는 3.3mA 만 흐른다.

이 방향이 중요하다. 반대로(풀다운 유지 + GPIO 가 HIGH 로 릴리즈) 하면
프로그램이 끝나는 순간 GPIO 가 입력으로 돌아가 OE 가 LOW 로 떨어지고
**서보가 다시 살아난다.** 페일세이프 방향이면 반대가 된다:

    부팅 직후 / 프로그램 종료 / 크래시  ->  OE HIGH  ->  자동 릴리즈
    프로그램 실행 중                    ->  OE LOW   ->  정상 구동

권한
----
digitalio(Blinka)는 /dev/mem 을 열어 root 를 요구한다. 보행 스크립트는 sudo 없이
돌아야 하므로 gpiod(문자 장치 /dev/gpiochipN)를 쓴다. `gpio` 그룹이면 root 가 필요없다.

    sudo apt install -y python3-libgpiod
    sudo usermod -aG gpio $USER      # 재로그인 필요
"""

OE_CHIP = "/dev/gpiochip0"
OE_LINE = 17            # BCM 17 (40핀 헤더 11번). 배선에 맞춰 바꿀 것

# MODE2 비트: bit2 OUTDRV(토템폴), bit0-1 OUTNE
MODE2_OUTNE_MASK = 0x03
MODE2_OUTNE_HIZ = 0x02          # 10 = OE HIGH 일 때 고임피던스


def configurePCA(pca):
    """이 PCA9685 의 OE 동작을 '고임피던스' 로 바꾼다.

    MODE2 는 전원이 끊기면 기본값(0x04, OUTNE=00 = OE HIGH 일 때 LOW)으로 돌아가므로
    보드를 초기화할 때마다 호출해야 한다.
    """
    try:
        m2 = pca.mode2_reg
        pca.mode2_reg = (m2 & ~MODE2_OUTNE_MASK) | MODE2_OUTNE_HIZ
        return True
    except Exception:
        return False


class OutputEnable:
    """OE 라인을 잡고 있는 동안 서보가 살아있다.

    객체가 사라지면(프로그램 종료/크래시) 라인이 풀려 풀업이 OE 를 HIGH 로 올리고
    서보는 자동으로 릴리즈된다. 이것이 의도된 동작이다.
    """

    def __init__(self, chip=OE_CHIP, line=OE_LINE):
        self.available = False
        self.reason = ""
        self._req = None
        self._backend = None
        try:
            import gpiod
        except ImportError:
            self.reason = ("python3-libgpiod 가 없다. "
                           "sudo apt install -y python3-libgpiod")
            return
        try:
            # libgpiod v2
            from gpiod.line import Direction, Value
            self._req = gpiod.request_lines(
                chip, consumer="spotmicro-oe",
                config={line: gpiod.LineSettings(direction=Direction.OUTPUT,
                                                 output_value=Value.ACTIVE)})
            self._backend = "v2"
            self._vals = (Value.INACTIVE, Value.ACTIVE)
            self._line = line
            self.available = True
        except (AttributeError, ImportError):
            try:
                # libgpiod v1
                c = gpiod.Chip(chip)
                ln = c.get_line(line)
                ln.request(consumer="spotmicro-oe", type=gpiod.LINE_REQ_DIR_OUT)
                self._req = ln
                self._backend = "v1"
                self._chip = c
                self.available = True
            except Exception as e:
                self.reason = f"gpiod v1 요청 실패: {e}"
        except Exception as e:
            self.reason = f"gpiod v2 요청 실패: {e}"

    def enable(self, on=True):
        """on=True 면 서보 구동(OE LOW), False 면 릴리즈(OE HIGH)."""
        if not self.available:
            return False
        try:
            if self._backend == "v2":
                lo, hi = self._vals
                self._req.set_value(self._line, lo if on else hi)
            else:
                self._req.set_value(0 if on else 1)
            return True
        except Exception:
            return False

    def release(self):
        return self.enable(False)

    def close(self):
        """라인을 놓는다. 풀업이 OE 를 HIGH 로 올려 서보가 릴리즈된다."""
        try:
            if self._backend == "v2":
                self._req.release()
            elif self._backend == "v1":
                self._req.release()
                self._chip.close()
        except Exception:
            pass
        self.available = False
