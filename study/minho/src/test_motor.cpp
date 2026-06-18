/* -----------------------------------------------------------------------------
  서보 모터 테스트

  사용법:
  1. 업로드 후 시리얼 모니터 열기 (115200 baud)
  2. 명령어 입력:
     - aa / af   : channel A arm/foot 테스트 (90→0→180→90)
     - ba / bf   : channel B arm/foot 테스트
     - ca / cf   : channel C arm/foot 테스트
     - da / df   : channel D arm/foot 테스트
     - aa90      : channel A arm → 90도  (채널 a~d + a=arm/f=foot + 각도)
     - df45      : channel D foot → 45도
     - off       : 모든 서보 끄기
     - on        : 모든 서보 켜기 (90도)
   -----------------------------------------------------------------------------*/

#include <Arduino.h>
#include <ESP32Servo.h>

Servo servo_armA, servo_armB, servo_armC, servo_armD;
Servo servo_footA, servo_footB, servo_footC, servo_footD;

// 서보 배열: index = (type==foot ? 4:0) + (ch-'a')
// [0]=armA [1]=armB [2]=armC [3]=armD [4]=footA [5]=footB [6]=footC [7]=footD
Servo* servos[8] = {&servo_armA, &servo_armB, &servo_armC, &servo_armD,
                    &servo_footA, &servo_footB, &servo_footC, &servo_footD};
int pins[8]         = {26, 32, 15, 17, 12, 33, 2, 5};
const char* names[8] = {"armA(26)", "armB(32)", "armC(15)", "armD(17)",
                         "footA(12)", "footB(33)", "footC(2)", "footD(5)"};

// ch: 'a'~'d', type: 'a'=arm / 'f'=foot → servos[] index
int servoIndex(char ch, char type) {
  return (type == 'f' ? 4 : 0) + (ch - 'a');
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("========================================");
  Serial.println("  서보 모터 테스트");
  Serial.println("========================================");
  Serial.println();
  Serial.println("핀 배치:");
  Serial.println("  채널  arm    foot");
  for (int i = 0; i < 4; i++) {
    Serial.printf("   %c   %s  %s\n",
                  'A' + i, names[i], names[i + 4]);
  }
  Serial.println();
  Serial.println("명령어:");
  Serial.println("  aa/af  - channel A arm/foot 테스트 (90->0->180->90)");
  Serial.println("  aa90   - channel A arm  → 90도 (채널+타입+각도)");
  Serial.println("  df45   - channel D foot → 45도");
  Serial.println("  off    - 모든 서보 끄기");
  Serial.println("  on     - 모든 서보 켜기 (90도)");
  Serial.println("========================================");

  for (int i = 0; i < 8; i++) {
    servos[i]->attach(pins[i]);
    servos[i]->write(90);
  }
  Serial.println("모든 서보 90도로 설정 (대기 중)");
}

// 채널/타입으로 해당 서보 순차 테스트
void testSingleServo(char ch, char type) {
  int idx = servoIndex(ch, type);
  Serial.println();
  Serial.printf(">>> [%c%c] %s 테스트 시작 <<<\n", ch, type, names[idx]);
  Serial.println();

  Serial.println("  [1] 90도 (정지점)...");
  servos[idx]->write(90);
  delay(1500);

  Serial.println("  [2] 0도로 이동...");
  servos[idx]->write(0);
  delay(2000);

  Serial.println("  [3] 180도로 이동...");
  servos[idx]->write(180);
  delay(2000);

  Serial.println("  [4] 90도로 복귀...");
  servos[idx]->write(90);
  delay(1000);

  Serial.println();
  Serial.println("  ┌─────────────────────────────────────┐");
  Serial.println("  │ 결과 확인:                          │");
  Serial.println("  │  - 0°, 180°에서 멈춤 → 180도 서보 ✓ │");
  Serial.println("  │  - 계속 회전함 → 360도 서보 ✗       │");
  Serial.println("  └─────────────────────────────────────┘");
  Serial.println();
}

void moveServoTo(char ch, char type, int angle) {
  if (angle < 0 || angle > 180) {
    Serial.printf("오류: 각도 %d 는 유효하지 않습니다. (0~180)\n", angle);
    return;
  }
  int idx = servoIndex(ch, type);
  Serial.printf("[%c%c] %s → %d도\n", ch, type, names[idx], angle);
  servos[idx]->write(angle);
}

void allOff() {
  Serial.println("모든 서보 OFF");
  for (int i = 0; i < 8; i++) servos[i]->detach();
}

void allOn() {
  Serial.println("모든 서보 ON (90도)");
  for (int i = 0; i < 8; i++) {
    servos[i]->attach(pins[i]);
    servos[i]->write(90);
  }
}

// 채널(a~d)과 타입(a/f) 여부 확인
bool isValidCmd(const String& cmd) {
  return cmd[0] >= 'a' && cmd[0] <= 'd' &&
         (cmd[1] == 'a' || cmd[1] == 'f');
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    cmd.toLowerCase();

    Serial.print("CMD: ");
    Serial.println(cmd);

    if (cmd == "off") {
      allOff();
    }
    else if (cmd == "on") {
      allOn();
    }
    else if (cmd.length() == 2 && isValidCmd(cmd)) {
      // 형식: aa, af, da, df ... (채널+타입) → 테스트
      testSingleServo(cmd[0], cmd[1]);
    }
    else if (cmd.length() >= 3 && isValidCmd(cmd)) {
      // 형식: aa90, df45 ... (채널+타입+각도) → 각도 이동
      int angle = cmd.substring(2).toInt();
      moveServoTo(cmd[0], cmd[1], angle);
    }
    else {
      Serial.println("명령어: aa/af (테스트), aa90/df45 (각도), off, on");
    }
  }
  delay(10);
}
