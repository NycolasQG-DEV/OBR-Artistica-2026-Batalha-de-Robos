#include <Wire.h>
#include <MPU6050_light.h>
#include <math.h>
#include <FastLED.h>
#define WHEEL_DIAMETER_CM    8.0f
#define WHEEL_CIRCUMFERENCE  (M_PI * WHEEL_DIAMETER_CM)
#define MAX_SPEED_CM_PER_SEC (270.0f / 5.6f)
#define PIN_L_RPWM   4
#define PIN_L_LPWM   5
#define PIN_L_R_EN   6
#define PIN_L_L_EN   7
#define PIN_R_RPWM   10
#define PIN_R_LPWM   11
#define PIN_R_R_EN   12
#define PIN_R_L_EN   13
#define PIN_SDA      8
#define PIN_SCL      9
#define PIN_NECK_IN1 15
#define PIN_NECK_IN2 41
#define PIN_NECK_ENA 16
#define PIN_MOUTH_IN3 18
#define PIN_MOUTH_IN4 3
#define PIN_MOUTH_ENB 21
#define LED_PIN     48
#define LED_TYPE    WS2812B
#define COLOR_ORDER GRB
#define BRIGHTNESS  80
#define NUM_LEDS    69
const uint8_t NUM_COLS = 9;
const uint8_t COL_LEN[NUM_COLS] = {3, 9, 9, 9, 9, 9, 9, 9, 3};
CRGB leds[NUM_LEDS];
uint16_t colStart[NUM_COLS];
bool colGoesDown[NUM_COLS];
bool eyesAnimated = false;
uint8_t rainbowHue = 0;
unsigned long lastEyeUpdate = 0;
#define S3_UART_RX_PIN    17
#define S3_UART_TX_PIN    2
#define S3_UART_BAUDRATE  115200
#define UART_WATCHDOG_MS  800
#define LEFT_MOTOR_REVERSED   false
#define RIGHT_MOTOR_REVERSED  true
#define PWM_FREQ 20000
#define PWM_RES  8
float turnKp = 2.2;
float turnKi = 0.0;
float turnKd = 0.35;
#define TURN_PWM_MIN       255
#define TURN_PWM_MAX       255
#define MOVE_PWM_MIN       170
#define MOVE_PWM_MAX       255
#define TURN_DEADZONE_DEG  1.5
#define TURN_SLOWDOWN_DEG  20.0
int scaleMovePwm(int speed) {
  if (speed <= 0) return 0;
  speed = constrain(speed, 1, 255);
  return map(speed, 1, 255, MOVE_PWM_MIN, MOVE_PWM_MAX);
}
int scaleTurnPwm(int speed) {
  if (speed <= 0) return 0;
  return 255;
}
float headingKp = 3.0;
#define HEADING_CORRECTION_MAX 50
#define NECK_SPEED  200
#define MOUTH_SPEED 200
#define CMD_MAX_LEN 64
bool mpuOK = false;
String mpuStatusMsg = "Nao Inicializado";
void addLog(const String &msg) {
  Serial.println(msg);
}
void buildLedMapping() {
  uint16_t acc = 0;
  for (uint8_t c = 0; c < NUM_COLS; c++) {
    colStart[c] = acc;
    acc += COL_LEN[c];
    colGoesDown[c] = (c % 2 == 0);
  }
}
int16_t ledIndex(uint8_t col, uint8_t row) {
  if (col >= NUM_COLS || row >= COL_LEN[col]) return -1;
  if (colGoesDown[col]) return colStart[col] + row;
  return colStart[col] + (COL_LEN[col] - 1 - row);
}
void drawEyeMatrix(const uint8_t matrix[9][9], CRGB color) {
  FastLED.clear();
  for (uint8_t r = 0; r < 9; r++) {
    for (uint8_t c = 0; c < 9; c++) {
      if (matrix[r][c] == 1) {
        uint8_t physRow = r;
        if (c == 0 || c == 8) {
          if (r >= 3 && r <= 5) physRow = r - 3;
          else continue;
        }
        int16_t idx = ledIndex(c, physRow);
        if (idx >= 0) leds[idx] = color;
      }
    }
  }
  FastLED.show();
}
const uint8_t DesenhoX[9][9] = {
  {0, 1, 1, 1, 1, 1, 1, 1, 0},
  {0, 1, 1, 1, 1, 1, 1, 1, 0},
  {0, 1, 1, 1, 1, 1, 1, 1, 0},
  {1, 1, 1, 1, 1, 1, 1, 1, 1},
  {1, 1, 1, 1, 1, 1, 1, 1, 1},
  {1, 1, 1, 1, 1, 1, 1, 1, 1},
  {0, 1, 1, 1, 1, 1, 1, 1, 0},
  {0, 1, 1, 1, 1, 1, 1, 1, 0},
  {0, 1, 1, 1, 1, 1, 1, 1, 0}
};
const uint8_t DesenhoON[9][9] = {
  {1, 1, 1, 1, 1, 1, 1, 1, 1},
  {1, 1, 1, 1, 1, 1, 1, 1, 1},
  {1, 1, 1, 1, 1, 1, 1, 1, 1},
  {1, 1, 1, 1, 1, 1, 1, 1, 1},
  {1, 1, 1, 1, 1, 1, 1, 1, 1},
  {1, 1, 1, 1, 1, 1, 1, 1, 1},
  {1, 1, 1, 1, 1, 1, 1, 1, 1},
  {1, 1, 1, 1, 1, 1, 1, 1, 1},
  {1, 1, 1, 1, 1, 1, 1, 1, 1}
};
const uint8_t DesenhoOFF[9][9] = {
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0}
};
void drawAnimatedRainbow() {
  for (uint8_t col = 0; col < NUM_COLS; col++) {
    uint8_t hue = rainbowHue + col * (255 / NUM_COLS);
    CRGB color = CHSV(hue, 255, 255);
    for (uint8_t row = 0; row < COL_LEN[col]; row++) {
      int16_t idx = ledIndex(col, row);
      if (idx >= 0) leds[idx] = color;
    }
  }
  FastLED.show();
  rainbowHue += 2;
}
class BTS7960Motor {
  public:
    BTS7960Motor(uint8_t rpwmPin, uint8_t lpwmPin, uint8_t rEnPin, uint8_t lEnPin, bool reversed)
      : _rpwm(rpwmPin), _lpwm(lpwmPin), _rEn(rEnPin), _lEn(lEnPin), _reversed(reversed) {}
    void begin() {
      pinMode(_rEn, OUTPUT);
      pinMode(_lEn, OUTPUT);
      digitalWrite(_rEn, LOW);
      digitalWrite(_lEn, LOW);
      ledcAttach(_rpwm, PWM_FREQ, PWM_RES);
      ledcAttach(_lpwm, PWM_FREQ, PWM_RES);
      ledcWrite(_rpwm, 0);
      ledcWrite(_lpwm, 0);
    }
    void enable() {
      digitalWrite(_rEn, HIGH);
      digitalWrite(_lEn, HIGH);
    }
    void disable() {
      digitalWrite(_rEn, LOW);
      digitalWrite(_lEn, LOW);
    }
    void forward(uint8_t speed)  { setSigned((int16_t)speed); }
    void backward(uint8_t speed) { setSigned(-(int16_t)speed); }
    void stop()                  { setSigned(0); }
    void setSpeedSigned(int16_t signedSpeed) {
      setSigned(signedSpeed);
    }
  private:
    uint8_t _rpwm, _lpwm, _rEn, _lEn;
    bool _reversed;
    void setSigned(int16_t signedSpeed) {
      signedSpeed = constrain(signedSpeed, -255, 255);
      if (_reversed) signedSpeed = -signedSpeed;
      if (signedSpeed >= 0) {
        ledcWrite(_lpwm, 0);
        ledcWrite(_rpwm, signedSpeed);
      } else {
        ledcWrite(_rpwm, 0);
        ledcWrite(_lpwm, -signedSpeed);
      }
    }
};
class L298NMotor {
  public:
    L298NMotor(uint8_t in1Pin, uint8_t in2Pin, uint8_t enPin)
      : _in1(in1Pin), _in2(in2Pin), _en(enPin) {}
    void begin() {
      pinMode(_in1, OUTPUT);
      pinMode(_in2, OUTPUT);
      digitalWrite(_in1, LOW);
      digitalWrite(_in2, LOW);
      ledcAttach(_en, PWM_FREQ, PWM_RES);
      ledcWrite(_en, 0);
    }
    void forward(uint8_t speed) {
      digitalWrite(_in1, HIGH);
      digitalWrite(_in2, LOW);
      ledcWrite(_en, speed);
    }
    void backward(uint8_t speed) {
      digitalWrite(_in1, LOW);
      digitalWrite(_in2, HIGH);
      ledcWrite(_en, speed);
    }
    void stop() {
      digitalWrite(_in1, LOW);
      digitalWrite(_in2, LOW);
      ledcWrite(_en, 0);
    }
  private:
    uint8_t _in1, _in2, _en;
};
BTS7960Motor motorLeft (PIN_L_RPWM, PIN_L_LPWM, PIN_L_R_EN, PIN_L_L_EN, LEFT_MOTOR_REVERSED);
BTS7960Motor motorRight(PIN_R_RPWM, PIN_R_LPWM, PIN_R_R_EN, PIN_R_L_EN, RIGHT_MOTOR_REVERSED);
L298NMotor neckMotor (PIN_NECK_IN1,  PIN_NECK_IN2,  PIN_NECK_ENA);
L298NMotor mouthMotor(PIN_MOUTH_IN3, PIN_MOUTH_IN4, PIN_MOUTH_ENB);
MPU6050 mpu(Wire);
enum MoveDirection { MOVE_NONE, MOVE_FORWARD, MOVE_BACKWARD, MOVE_LEFT, MOVE_RIGHT, MOVE_DIFF };
MoveDirection currentMove = MOVE_NONE;
int moveSpeed = 0;
int diffLeftSpeed = 0;
int diffRightSpeed = 0;
float yawInicialMov = 0.0f;
float globalDirection = 0.0f;
long neckPositionMs = 0;
float turnInitialYaw = 0.0f;
bool cmMoveActive = false;
unsigned long cmMoveEndTime = 0;
bool timeMoveActive = false;
unsigned long timeMoveEndTime = 0;
bool  turnActive          = false;
bool  turnFallbackActive  = false;
unsigned long turnFallbackEndTime = 0;
bool  turnDirectionRight  = true;
int   turnSpeedPwm        = 255;
unsigned long turnStartTime = 0;
float turnTargetYaw       = 0.0f;
float turnIntegral        = 0.0f;
float turnLastError       = 0.0f;
unsigned long turnLastTime = 0;
bool isTurning() {
  return turnActive || turnFallbackActive;
}
bool seqActive = false;
String activeSeqName = "";
int seqStep = 0;
unsigned long seqStepTimer = 0;
char uartLineBuf[CMD_MAX_LEN];
uint8_t uartLineLen = 0;
unsigned long lastUartRxTime = 0;
unsigned long lastTelemetryTime = 0;
void handleStop();
void parseAndExecute(String raw);
void sendDebugAckOnly(const String &cmdStr);
void handleTurn(float deltaDeg);
void handleMovTime(long durationMs, int speed);
void handleDiffMov(int leftSpeed, int rightSpeed);
void handleSequence(String seqName);
void handleNeck(String action, long timeMs);
void handleMouth(float waitSeconds);
void handleEyes(String pattern);
void moveRobot(MoveDirection dir, float cm, int speed);
void handleMov(String dirStr, float cm, int speed);
void sendDebug(const String &msg) {
  addLog("[UART TX] " + msg);
  Serial1.println(msg);
}
void sendOkSignal() {
  addLog("[UART TX] ok");
  Serial1.println("ok");
}
void sendDebugAckOnly(const String &cmdStr) {
  String ack = "ACK:" + cmdStr;
  addLog("[UART TX] " + ack);
  Serial1.println(ack);
}
void sendDoneSignal(const String &seqName = "") {
  String doneMsg = "DONE";
  if (seqName.length() > 0) {
    doneMsg += ":" + seqName;
  }
  addLog("[UART TX] " + doneMsg);
  Serial1.println(doneMsg);
}
float speedPwmToCmPerSec(int pwm) {
  pwm = constrain(pwm, 0, 255);
  return (float)pwm / 255.0f * MAX_SPEED_CM_PER_SEC;
}
unsigned long cmToDurationMs(float cm, int pwm) {
  float speedCmS = speedPwmToCmPerSec(pwm);
  if (speedCmS <= 0.1f) return 0;
  return (unsigned long)((fabs(cm) / speedCmS) * 1000.0f);
}
void moveRobot(MoveDirection dir, float cm, int speed) {
  if (dir == MOVE_NONE) {
    handleStop();
    return;
  }
  turnActive = false;
  turnFallbackActive = false;
  timeMoveActive = false;
  currentMove = dir;
  
  if (dir == MOVE_FORWARD || dir == MOVE_BACKWARD) {
    moveSpeed = scaleMovePwm(speed);
  } else {
    moveSpeed = scaleTurnPwm(speed);
  }
  yawInicialMov = mpuOK ? mpu.getAngleZ() : 0.0f;
  unsigned long duration = cmToDurationMs(cm, moveSpeed);
  cmMoveEndTime = millis() + duration;
  cmMoveActive = true;
  sendDebug("MOV_CM: dir=" + String(dir) + " dist=" + String(cm, 1) + "cm, speed=" + String(moveSpeed) + ", dur=" + String(duration) + "ms");
  while (cmMoveActive) {
    if (mpuOK) {
      mpu.update();
    }
    updateMovement();
    delay(1);
  }
}
void setupMPU() {
  Wire.end();
  delay(10);
  Wire.begin(PIN_SDA, PIN_SCL, 100000);
  delay(100);
  Wire.beginTransmission(0x68);
  byte i2cError = Wire.endTransmission();
  if (i2cError != 0) {
    mpuOK = false;
    mpuStatusMsg = "ERRO I2C (0x68)";
    addLog("[AVISO MPU] MPU6050 nao encontrado no barramento I2C. Modo Fallback ativado!");
    return;
  }
  byte mpuStatus = mpu.begin();
  if (mpuStatus != 0) {
    mpuOK = false;
    mpuStatusMsg = "ERRO mpu.begin() code " + String(mpuStatus);
    addLog("[AVISO MPU] Falha ao inicializar MPU6050. Modo Fallback ativado!");
  } else {
    addLog("Calibrando MPU6050 DinoByte...");
    delay(500);
    mpu.calcOffsets(true, true);
    mpuOK = true;
    mpuStatusMsg = "OK";
    addLog("[MPU OK] MPU6050 inicializado e calibrado com sucesso.");
  }
}
void readUartCommands() {
  while (Serial1.available() > 0) {
    int c = Serial1.read();
    if (c < 0) break;
    lastUartRxTime = millis();
    if (c == '\r') continue;
    if (c == '\n') {
      if (uartLineLen > 0) {
        uartLineBuf[uartLineLen] = '\0';
        String cmdStr(uartLineBuf);
        addLog("[UART RX] " + cmdStr);
        sendDebugAckOnly(cmdStr);
        parseAndExecute(cmdStr);
      }
      uartLineLen = 0;
      continue;
    }
    if (uartLineLen < (CMD_MAX_LEN - 1)) {
      uartLineBuf[uartLineLen++] = (char)c;
    } else {
      uartLineLen = 0;
    }
  }
}
void checkUartWatchdog() {
  bool moving = (currentMove != MOVE_NONE) || turnActive || cmMoveActive;
  if (moving && !seqActive && (millis() - lastUartRxTime > UART_WATCHDOG_MS)) {
    handleStop();
    neckMotor.stop();
    mouthMotor.stop();
    sendDebug("WATCHDOG: UART sem comunicacao, parada de seguranca executada.");
  }
}
void parseAndExecute(String raw) {
  raw.trim();
  if (raw.length() == 0) return;
  if (seqActive) {
    raw.toUpperCase();
    if (raw.startsWith("STOP")) {
      handleStop();
      seqActive = false;
      addLog("[SEQ] Sequência interrompida por STOP.");
    }
    return;
  }
  int openParen  = raw.indexOf('(');
  int closeParen = raw.lastIndexOf(')');
  if (openParen < 0 || closeParen < 0 || closeParen < openParen) {
    sendDebug("ERR: sintaxe invalida -> " + raw);
    return;
  }
  String cmd = raw.substring(0, openParen);
  String paramsStr = raw.substring(openParen + 1, closeParen);
  cmd.trim();
  cmd.toUpperCase();
  String params[4];
  int paramCount = 0;
  int start = 0;
  while (paramCount < 4) {
    int commaIdx = paramsStr.indexOf(',', start);
    if (commaIdx < 0) {
      String p = paramsStr.substring(start);
      p.trim();
      if (p.length() > 0) params[paramCount++] = p;
      break;
    } else {
      String p = paramsStr.substring(start, commaIdx);
      p.trim();
      params[paramCount++] = p;
      start = commaIdx + 1;
    }
  }
  if (cmd == "MOV") {
    String dirStr = params[0];
    float cm = (paramCount >= 2) ? params[1].toFloat() : 0.0f;
    int speed = (paramCount >= 3) ? params[2].toInt() : 220;
    handleMov(dirStr, cm, speed);
  } else if (cmd == "MOV_TIME" && paramCount >= 1) {
    long ms = params[0].toInt();
    int speed = (paramCount >= 2) ? params[1].toInt() : 220;
    handleMovTime(ms, speed);
  } else if (cmd == "DIFF_MOV" && paramCount >= 2) {
    handleDiffMov(params[0].toInt(), params[1].toInt());
  } else if (cmd == "STOP") {
    handleStop();
  } else if (cmd == "TURN" && paramCount >= 1) {
    float deltaDeg = params[0].toFloat();
    handleTurn(deltaDeg);
  } else if (cmd == "SEQ" && paramCount >= 1) {
    handleSequence(params[0]);
  } else if (cmd == "NECK" && paramCount >= 1) {
    String action = params[0];
    long timeMs = (paramCount >= 2) ? params[1].toInt() : 0;
    handleNeck(action, timeMs);
  } else if (cmd == "MOUTH" && paramCount >= 1) {
    float waitSeconds = params[0].toFloat();
    handleMouth(waitSeconds);
  } else if (cmd == "EYES" && paramCount >= 1) {
    handleEyes(params[0]);
  } else {
    sendDebug("ERR: comando desconhecido -> " + raw);
  }
}
void handleMov(String dirStr, float cm, int speed) {
  dirStr.trim();
  dirStr.toUpperCase();
  MoveDirection dir = MOVE_NONE;
  if (dirStr == "W" || dirStr == "FRENTE") {
    dir = MOVE_FORWARD;
  } else if (dirStr == "S" || dirStr == "TRAS") {
    dir = MOVE_BACKWARD;
  } else if (dirStr == "A" || dirStr == "ESQUERDA") {
    dir = MOVE_LEFT;
  } else if (dirStr == "D" || dirStr == "DIREITA") {
    dir = MOVE_RIGHT;
  }
  if (cm > 0.0f) {
    moveRobot(dir, cm, speed);
  } else {
    turnActive = false;
    turnFallbackActive = false;
    cmMoveActive = false;
    timeMoveActive = false;
    currentMove = dir;
    moveSpeed = (dir == MOVE_LEFT || dir == MOVE_RIGHT) ? scaleTurnPwm(speed) : scaleMovePwm(speed);
    yawInicialMov = mpuOK ? mpu.getAngleZ() : 0.0f;
    sendDebug("MOV: dir=" + dirStr + ", speed=" + String(moveSpeed));
  }
}
void handleMovTime(long durationMs, int speed) {
  turnActive = false;
  cmMoveActive = false;
  if (durationMs >= 0) {
    currentMove = MOVE_FORWARD;
  } else {
    currentMove = MOVE_BACKWARD;
    durationMs = -durationMs;
  }
  moveSpeed = scaleMovePwm(speed);
  yawInicialMov = mpuOK ? mpu.getAngleZ() : 0.0f;
  timeMoveEndTime = millis() + (unsigned long)durationMs;
  timeMoveActive = true;
  sendDebug("MOV_TIME: tempo=" + String(durationMs) + "ms, speed=" + String(moveSpeed));
  while (timeMoveActive) {
    if (mpuOK) {
      mpu.update();
    }
    updateMovement();
    delay(1);
  }
}
void handleDiffMov(int leftSpeed, int rightSpeed) {
  turnActive = false;
  cmMoveActive = false;
  timeMoveActive = false;
  currentMove = MOVE_DIFF;
  int scaledL = 0;
  if (leftSpeed > 0) scaledL = map(constrain(leftSpeed, 1, 255), 1, 255, MOVE_PWM_MIN, MOVE_PWM_MAX);
  else if (leftSpeed < 0) scaledL = -map(constrain(-leftSpeed, 1, 255), 1, 255, MOVE_PWM_MIN, MOVE_PWM_MAX);
  int scaledR = 0;
  if (rightSpeed > 0) scaledR = map(constrain(rightSpeed, 1, 255), 1, 255, MOVE_PWM_MIN, MOVE_PWM_MAX);
  else if (rightSpeed < 0) scaledR = -map(constrain(-rightSpeed, 1, 255), 1, 255, MOVE_PWM_MIN, MOVE_PWM_MAX);
  diffLeftSpeed = scaledL;
  diffRightSpeed = scaledR;
  motorLeft.setSpeedSigned(diffLeftSpeed);
  motorRight.setSpeedSigned(diffRightSpeed);
  sendDebug("DIFF_MOV: L=" + String(diffLeftSpeed) + " R=" + String(diffRightSpeed));
}
void handleStop() {
  currentMove = MOVE_NONE;
  moveSpeed = 0;
  diffLeftSpeed = 0;
  diffRightSpeed = 0;
  turnActive = false;
  turnFallbackActive = false;
  cmMoveActive = false;
  timeMoveActive = false;
  motorLeft.stop();
  motorRight.stop();
  sendDebug("STOP: motores de tracao parados.");
}
void handleTurn(float deltaDeg) {
  currentMove = MOVE_NONE;
  moveSpeed = 0;
  turnSpeedPwm = 255;
  motorLeft.stop();
  motorRight.stop();
  turnDirectionRight = (deltaDeg >= 0.0f);
  turnStartTime = millis();
  if (mpuOK) {
    turnInitialYaw = mpu.getAngleZ();
    turnTargetYaw = turnInitialYaw + deltaDeg;
    turnActive = true;
    turnFallbackActive = false;
    sendDebug("TURN (MPU): delta=" + String(deltaDeg) + " deg, alvo=" + String(turnTargetYaw, 1));
  } else {
    float absDeg = fabs(deltaDeg);
    unsigned long durationMs = (unsigned long)((absDeg / 240.0f) * 1000.0f);
    if (durationMs < 80) durationMs = 80;
    turnFallbackEndTime = millis() + durationMs;
    turnFallbackActive = true;
    turnActive = false;
    int pwmVal = 255;
    if (turnDirectionRight) {
      motorLeft.forward(pwmVal);
      motorRight.backward(pwmVal);
    } else {
      motorLeft.backward(pwmVal);
      motorRight.forward(pwmVal);
    }
    sendDebug("TURN (Fallback Tempo): delta=" + String(deltaDeg) + " deg, duracao=" + String(durationMs) + "ms");
  }
  while (turnActive || turnFallbackActive) {
    if (mpuOK) {
      mpu.update();
    }
    updateTurnPID();
    delay(1);
  }
}
void handleSequence(String seqName) {
  seqName.trim();
  seqName.toUpperCase();
  if (seqName == "DEFAULT") {
    seqActive = true;
    activeSeqName = "DEFAULT";
    addLog("[SEQ] DEFAULT iniciada.");
  } else {
    sendDebug("ERR: sequencia desconhecida -> " + seqName);
  }
}
void updateSequences() {
  if (!seqActive) return;
  if (activeSeqName == "DEFAULT") {
    handleMov("FRENTE", 50.0f, 220);
    handleTurn(90.0f);
    handleMov("TRAS", 50.0f, 220);
    handleMouth(2.0f);
    handleNeck("LEFT", 1500);
    handleNeck("ZERO", 0);
    seqActive = false;
    addLog("[SEQ] DEFAULT concluida.");
    sendDoneSignal("DEFAULT");
  }
}
void handleNeck(String action, long timeMs) {
  action.trim();
  action.toUpperCase();
  if (action == "LEFT") {
    neckPositionMs -= timeMs;
    neckMotor.forward(255);
    sendDebug("NECK: LEFT por " + String(timeMs) + "ms");
    delay(timeMs);
    neckMotor.stop();
  } else if (action == "RIGHT") {
    neckPositionMs += timeMs;
    neckMotor.backward(255);
    sendDebug("NECK: RIGHT por " + String(timeMs) + "ms");
    delay(timeMs);
    neckMotor.stop();
  } else if (action == "ZERO" || action == "CENTER") {
    sendDebug("NECK: Retornando ao ponto ZERO. Pos atual=" + String(neckPositionMs) + "ms");
    if (neckPositionMs > 0) {
      neckMotor.forward(255);
      delay(neckPositionMs);
    } else if (neckPositionMs < 0) {
      neckMotor.backward(255);
      delay(-neckPositionMs);
    }
    neckMotor.stop();
    neckPositionMs = 0;
  } else if (action == "STOP") {
    neckMotor.stop();
    sendDebug("NECK: STOP");
  } else {
    sendDebug("ERR: comando NECK invalido -> " + action);
  }
}
void handleMouth(float waitSeconds) {
  int calibrationMs = 2500;
  sendDebug("MOUTH: Abrindo");
  mouthMotor.forward(255);
  delay(calibrationMs);
  mouthMotor.stop();
  sendDebug("MOUTH: Aguardando " + String(waitSeconds) + "s");
  delay((unsigned long)(waitSeconds * 1000.0f));
  sendDebug("MOUTH: Fechando");
  mouthMotor.backward(255);
  delay(calibrationMs);
  mouthMotor.stop();
}
void updateTurnPID() {
  if (turnFallbackActive) {
    if (millis() >= turnFallbackEndTime) {
      turnFallbackActive = false;
      motorLeft.stop();
      motorRight.stop();
      sendDebug("TURN (Fallback): concluido por tempo.");
      sendOkSignal();
    }
    return;
  }
  if (!turnActive) return;
  if (!mpuOK) {
    turnActive = false;
    turnFallbackEndTime = millis() + 350;
    turnFallbackActive = true;
    sendDebug("TURN: MPU falhou mid-turn, migrando para fallback por tempo.");
    return;
  }
  float yawAtual = mpu.getAngleZ();
  float distanceToTarget = fabs(turnTargetYaw - yawAtual);
  bool reached = false;
  if (turnDirectionRight) {
    if (yawAtual >= (turnTargetYaw - TURN_DEADZONE_DEG)) {
      reached = true;
    }
  } else {
    if (yawAtual <= (turnTargetYaw + TURN_DEADZONE_DEG)) {
      reached = true;
    }
  }
  if (millis() - turnStartTime > 4500) {
    reached = true;
    sendDebug("TURN: timeout de seguranca (4.5s) atingido.");
  }
  if (reached) {
    turnActive = false;
    motorLeft.stop();
    motorRight.stop();
    
    float actualTurned = yawAtual - turnInitialYaw;
    globalDirection += actualTurned;
    
    sendDebug("TURN: concluido (MPU). Yaw final=" + String(yawAtual, 1) + " deg, Dir global=" + String(globalDirection, 1));
    sendOkSignal();
    return;
  }
  int pwmVal = 200 + (int)((distanceToTarget / 45.0f) * 55.0f);
  pwmVal = constrain(pwmVal, 200, 255);
  if (turnDirectionRight) {
    motorLeft.forward(pwmVal);
    motorRight.backward(pwmVal);
  } else {
    motorLeft.backward(pwmVal);
    motorRight.forward(pwmVal);
  }
}
void updateMovement() {
  if (cmMoveActive) {
    if (millis() >= cmMoveEndTime) {
      handleStop();
      sendDebug("MOV_CM: distancia finalizada.");
      sendOkSignal();
      return;
    }
  }
  if (timeMoveActive) {
    if (millis() >= timeMoveEndTime) {
      handleStop();
      sendDebug("MOV_TIME: tempo finalizado.");
      sendOkSignal();
      return;
    }
  }
  switch (currentMove) {
    case MOVE_FORWARD:
    case MOVE_BACKWARD: {
      float yawAtual = mpuOK ? mpu.getAngleZ() : 0.0f;
      float error = mpuOK ? (yawAtual - yawInicialMov) : 0.0f;
      float correction = headingKp * error;
      correction = constrain(correction, -HEADING_CORRECTION_MAX, HEADING_CORRECTION_MAX);
      int leftSpeed  = constrain((int)(moveSpeed - correction), MOVE_PWM_MIN, MOVE_PWM_MAX);
      int rightSpeed = constrain((int)(moveSpeed + correction), MOVE_PWM_MIN, MOVE_PWM_MAX);
      if (currentMove == MOVE_FORWARD) {
        motorLeft.forward(leftSpeed);
        motorRight.forward(rightSpeed);
      } else {
        motorLeft.backward(leftSpeed);
        motorRight.backward(rightSpeed);
      }
      break;
    }
    case MOVE_LEFT:
      motorLeft.backward(moveSpeed);
      motorRight.forward(moveSpeed);
      break;
    case MOVE_RIGHT:
      motorLeft.forward(moveSpeed);
      motorRight.backward(moveSpeed);
      break;
    case MOVE_DIFF:
      break;
    case MOVE_NONE:
    default:
      break;
  }
}
void handleEyes(String pattern) {
  pattern.trim();
  pattern.toUpperCase();
  if (pattern == "X") {
    eyesAnimated = false;
    drawEyeMatrix(DesenhoX, CRGB(0, 255, 0));
    sendDebug("EYES: DesenhoX aplicado");
  } else if (pattern == "RAINBOW" || pattern == "ANIM") {
    eyesAnimated = true;
    sendDebug("EYES: Animacao Arco-iris ativada");
  } else if (pattern == "ON") {
    eyesAnimated = false;
    drawEyeMatrix(DesenhoON, CRGB(255, 255, 255));
    sendDebug("EYES: 100% Ligado (Branco)");
  } else if (pattern == "OFF" || pattern == "STOP") {
    eyesAnimated = false;
    drawEyeMatrix(DesenhoOFF, CRGB(0, 0, 0));
    sendDebug("EYES: 100% Desligado");
  } else {
    sendDebug("ERR: padrao de olho desconhecido -> " + pattern);
  }
}
void setup() {
  Serial.begin(115200);
  delay(300);
  buildLedMapping();
  FastLED.addLeds<LED_TYPE, LED_PIN, COLOR_ORDER>(leds, NUM_LEDS);
  FastLED.setBrightness(BRIGHTNESS);
  FastLED.clear();
  FastLED.show();
  eyesAnimated = true;
  motorLeft.begin();
  motorRight.begin();
  neckMotor.begin();
  mouthMotor.begin();
  setupMPU();
  Serial1.begin(S3_UART_BAUDRATE, SERIAL_8N1, S3_UART_RX_PIN, S3_UART_TX_PIN);
  lastUartRxTime = millis();
  motorLeft.enable();
  motorRight.enable();
  addLog("RobotBrain DinoByte pronto. Roda: 8cm. Aguardando comandos UART...");
}
void loop() {
  if (mpuOK) {
    mpu.update();
    if (isnan(mpu.getAngleZ())) {
      mpuOK = false;
      mpuStatusMsg = "ERRO Leitura NaN";
      addLog("[ERRO MPU] Leitura invalida (NaN) no MPU6050!");
    }
  }
  readUartCommands();
  checkUartWatchdog();
  updateSequences();
  if (eyesAnimated && (millis() - lastEyeUpdate >= 20)) {
    lastEyeUpdate = millis();
    drawAnimatedRainbow();
  }
  if (turnActive || turnFallbackActive) {
    updateTurnPID();
  } else {
    updateMovement();
  }

  if (millis() - lastTelemetryTime >= 100) {
    lastTelemetryTime = millis();
    if (mpuOK) {
      Serial1.println("DIR:" + String(mpu.getAngleZ(), 1));
    }
  }
}
