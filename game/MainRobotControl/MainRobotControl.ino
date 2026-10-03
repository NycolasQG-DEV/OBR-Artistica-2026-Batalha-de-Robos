#include <Wire.h>
#include <MPU6050_light.h>
#include <math.h>
#include <FastLED.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>

// ============================================================================
// ESTRUTURAS E ENUMS
// ============================================================================
enum MoveDirection { MOVE_NONE, MOVE_FORWARD, MOVE_BACKWARD, MOVE_LEFT, MOVE_RIGHT, MOVE_DIFF };

#define CMD_MAX_LEN 64
struct UartCmd {
  char text[CMD_MAX_LEN];
};

struct PIDController {
  float kp, ki, kd;
  float integralLimit;
  float integralActivationDeg; // 0 = integra sempre
  float integral = 0.0f;
  float lastError = 0.0f;

  PIDController(float p, float i, float d, float iLimit, float iActivationDeg)
    : kp(p), ki(i), kd(d), integralLimit(iLimit), integralActivationDeg(iActivationDeg) {}

  void reset() {
    integral = 0.0f;
    lastError = 0.0f;
  }

  float compute(float error, float dt) {
    if (dt < 0.01f) dt = 0.01f;

    if (integralActivationDeg <= 0.0f || fabs(error) < integralActivationDeg) {
      integral += error * dt;
      integral = constrain(integral, -integralLimit, integralLimit);
    } else {
      integral = 0.0f;
    }

    float derivative = (error - lastError) / dt;
    lastError = error;

    return (kp * error) + (ki * integral) + (kd * derivative);
  }
};

// ============================================================================
// PINOS E CONSTANTES DE HARDWARE
// ============================================================================

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
#define COLOR_ORDER BRG
#define BRIGHTNESS  80
#define NUM_LEDS    69

#define S3_UART_RX_PIN    17
#define S3_UART_TX_PIN    2
#define S3_UART_BAUDRATE  115200
#define UART_WATCHDOG_MS  800

#define LEFT_MOTOR_REVERSED   false
#define RIGHT_MOTOR_REVERSED  true
#define PWM_FREQ 20000
#define PWM_RES  8

#define TURN_PWM_MIN       160
#define TURN_PWM_FLOOR     130
#define TURN_PWM_MAX       255

#define MOVE_PWM_MIN       130
#define MOVE_PWM_MAX       255

#define TURN_DEADZONE_DEG  0.25f
#define TURN_BRAKE_ZONE_DEG  6.0f

#define HEADING_CORRECTION_MAX 255

#define NECK_MIN_MS  -4000
#define NECK_MAX_MS   4000

#define NECK_SPEED  200
#define MOUTH_SPEED 200

#define DRIFT_IDLE_BEFORE_CALIB_MS   500
#define DRIFT_CALIB_DURATION_MS      800
#define DRIFT_MAX_CORRECTION_DEG_S   0.30f
#define DRIFT_MOTION_THRESHOLD_DEG_S 0.08f


// ============================================================================
// CLASSES DE MOTORES
// ============================================================================
class BTS7960Motor {
  public:
    BTS7960Motor(uint8_t rpwmPin, uint8_t lpwmPin, uint8_t rEnPin, uint8_t lEnPin, bool reversed)
      : _rpwm(rpwmPin), _lpwm(lpwmPin), _rEn(rEnPin), _lEn(lEnPin), _reversed(reversed) {}

    void begin() {
      pinMode(_rEn, OUTPUT); pinMode(_lEn, OUTPUT);
      digitalWrite(_rEn, LOW); digitalWrite(_lEn, LOW);
      ledcAttach(_rpwm, PWM_FREQ, PWM_RES);
      ledcAttach(_lpwm, PWM_FREQ, PWM_RES);
      ledcWrite(_rpwm, 0); ledcWrite(_lpwm, 0);
    }
    void enable() { digitalWrite(_rEn, HIGH); digitalWrite(_lEn, HIGH); }
    void disable() { digitalWrite(_rEn, LOW); digitalWrite(_lEn, LOW); }
    void forward(uint8_t speed) { setSigned((int16_t)speed); }
    void backward(uint8_t speed) { setSigned(-(int16_t)speed); }
    void stop() { setSigned(0); }
    void setSpeedSigned(int16_t signedSpeed) { setSigned(signedSpeed); }
  private:
    uint8_t _rpwm, _lpwm, _rEn, _lEn; bool _reversed;
    void setSigned(int16_t signedSpeed) {
      signedSpeed = constrain(signedSpeed, -255, 255);
      if (_reversed) signedSpeed = -signedSpeed;
      if (signedSpeed >= 0) {
        ledcWrite(_lpwm, 0); ledcWrite(_rpwm, signedSpeed);
      } else {
        ledcWrite(_rpwm, 0); ledcWrite(_lpwm, -signedSpeed);
      }
    }
};

class L298NMotor {
  public:
    L298NMotor(uint8_t in1Pin, uint8_t in2Pin, uint8_t enPin)
      : _in1(in1Pin), _in2(in2Pin), _en(enPin) {}
    void begin() {
      pinMode(_in1, OUTPUT); pinMode(_in2, OUTPUT);
      digitalWrite(_in1, LOW); digitalWrite(_in2, LOW);
      ledcAttach(_en, PWM_FREQ, PWM_RES);
      ledcWrite(_en, 0);
    }
    void forward(uint8_t speed) { digitalWrite(_in1, HIGH); digitalWrite(_in2, LOW); ledcWrite(_en, speed); }
    void backward(uint8_t speed) { digitalWrite(_in1, LOW); digitalWrite(_in2, HIGH); ledcWrite(_en, speed); }
    void stop() { digitalWrite(_in1, LOW); digitalWrite(_in2, LOW); ledcWrite(_en, 0); }
  private:
    uint8_t _in1, _in2, _en;
};

// ============================================================================
// VARIÁVEIS GLOBAIS
// ============================================================================

volatile MoveDirection currentMove = MOVE_NONE;
int moveSpeed = 0;
int diffLeftSpeed = 0;
int diffRightSpeed = 0;
float yawInicialMov = 0.0f;
long neckPositionMs = 0;
float turnInitialYaw = 0.0f;

volatile bool turnActive = false;
bool timeMoveActive = false;
unsigned long timeMoveStartTime = 0;
unsigned long timeMoveEndTime = 0;
int targetMoveSpeed = 0;
bool turnDirectionRight = true;
unsigned long turnStartTime = 0;
float turnTargetYaw = 0.0f;

unsigned long turnTimeInDeadzone = 0;
unsigned long lastTurnTime_us = 0;
unsigned long lastMoveTime_us = 0;

// Variáveis de detecção inteligente de estolagem (stall) por atrito
unsigned long lastStallCheckMs = 0;
float lastStallYaw = 0.0f;
float stallBoostPwm = 0.0f;

volatile bool seqActive = false;
String activeSeqName = "";

volatile unsigned long lastUartRxTime = 0;
unsigned long lastTelemetryTime = 0;
unsigned long lastMpuRetryTime = 0;

volatile bool stopRequested = false;
volatile bool sequenceAbortFlag = false;

SemaphoreHandle_t serialMutex = NULL;
QueueHandle_t cmdQueue = NULL;

bool mpuOK = false;
String mpuStatusMsg = "Nao Inicializado";

float headingKp = 7.5f;
float headingKi = 0.05f;
float headingKd = 1.0f;
PIDController headingPID(headingKp, headingKi, headingKd, 40.0f, 2.0f);

float turnKp = 2.4f;
float turnKi = 0.02f;
float turnKd = 0.90f;
PIDController turnPID(turnKp, turnKi, turnKd, 40.0f, 30.0f);

float gyroDriftRateDegS = 0.0f;
float driftCorrectionDeg = 0.0f;
unsigned long lastDriftApplyMs = 0;
unsigned long motorsIdleSinceMs = 0;
bool  driftCalibActive = false;
float driftCalibAccum = 0.0f;
int   driftCalibSamples = 0;
unsigned long driftCalibStartMs = 0;

const uint8_t NUM_COLS = 9;
const uint8_t COL_LEN[9] = {3, 9, 9, 9, 9, 9, 9, 9, 3};
CRGB leds[NUM_LEDS];
uint16_t colStart[9];
bool colGoesDown[9];

// Olhos em paralelo
volatile int currentEyeState = 0;
volatile bool eyeSignalBlinkOk = false;
volatile bool eyeSignalBlinkErr = false;
volatile bool eyesX = false;
volatile bool systemReady = false;
SemaphoreHandle_t eyesMutex = NULL;

BTS7960Motor motorLeft(PIN_L_RPWM, PIN_L_LPWM, PIN_L_R_EN, PIN_L_L_EN, LEFT_MOTOR_REVERSED);
BTS7960Motor motorRight(PIN_R_RPWM, PIN_R_LPWM, PIN_R_R_EN, PIN_R_L_EN, RIGHT_MOTOR_REVERSED);
L298NMotor neckMotor(PIN_NECK_IN1, PIN_NECK_IN2, PIN_NECK_ENA);
L298NMotor mouthMotor(PIN_MOUTH_IN3, PIN_MOUTH_IN4, PIN_MOUTH_ENB);
MPU6050 mpu(Wire);

// Assinaturas para manter o compilador feliz
void addLog(const String &msg);
void sendDebug(const String &msg);
void sendDebugAckOnly(const String &cmdStr);
void checkUartWatchdog();
void setupEyesTask();
void handleEyes(String pattern);
void setupMPU();
void parseAndExecute(String raw);
bool checkAndHandleStopRequest();
void applyDriftCorrection();
void updateDriftCalibration();
void updateSequences();
void updateTurnPID();
void updateMovement();
void handleMov(String dirStr, float val, int speed);
void handleTurn(float deltaDeg);
void handleMovTime(long durationMs, int speed, MoveDirection forceDir = MOVE_NONE);
void handleDiffMov(int leftSpeed, int rightSpeed);
void handleStop();
void handleSequence(String seqName);
void handleNeck(String action, long timeMs);
void handleMouth(float waitSeconds);

// ============================================================================
// COMM TASK (Roda no Core 0)
// ============================================================================
void CommTask(void *pvParameters) {
  while (true) {
    if (Serial1.available() > 0) {
      String raw = Serial1.readStringUntil('\n');
      raw.trim();
      if (raw.length() > 0) {
        lastUartRxTime = millis();
        
        if (raw.indexOf("ACK:") == 0 || raw == "ok") {
        } else if (raw.equalsIgnoreCase("STOP")) {
          stopRequested = true;
          sendDebugAckOnly(raw);
        } else {
          UartCmd newCmd;
          strncpy(newCmd.text, raw.c_str(), CMD_MAX_LEN - 1);
          newCmd.text[CMD_MAX_LEN - 1] = '\0';
          if (xQueueSend(cmdQueue, &newCmd, portMAX_DELAY) != pdTRUE) {
            sendDebug("ERR: Fila cheia, comando ignorado: " + raw);
          } else {
            sendDebugAckOnly(raw);
          }
        }
      }
    }
    checkUartWatchdog();
    vTaskDelay(10 / portTICK_PERIOD_MS);
  }
}

// ============================================================================
// SETUP
// ============================================================================
void setup() {
  Serial.begin(115200);
  Serial1.begin(S3_UART_BAUDRATE, SERIAL_8N1, S3_UART_RX_PIN, S3_UART_TX_PIN);
  Serial1.setTimeout(10);
  delay(1000);
  
  serialMutex = xSemaphoreCreateMutex();
  eyesMutex = xSemaphoreCreateMutex();
  cmdQueue = xQueueCreate(10, sizeof(UartCmd));
  if (serialMutex == NULL || cmdQueue == NULL || eyesMutex == NULL) {
    Serial.println("ERRO FATAL: Falha ao criar mutex ou fila do FreeRTOS!");
    while(1) delay(100);
  }
  
  addLog("\n--- Iniciando DinoByte System ---");
  
  setupEyesTask(); 
  
  motorLeft.begin();
  motorRight.begin();
  motorLeft.enable();
  motorRight.enable();
  
  neckMotor.begin();
  mouthMotor.begin();
  
  setupMPU();
  
  lastUartRxTime = millis();
  
  xTaskCreatePinnedToCore(
    CommTask,
    "CommTask",
    4096,
    NULL,
    1,
    NULL,
    0
  );
  
  systemReady = true;
  addLog("--- Sistema Pronto ---");
}

// ============================================================================
// LOOP PRINCIPAL (Roda no Core 1)
// ============================================================================
void loop() {
  UartCmd incoming;
  while (xQueueReceive(cmdQueue, &incoming, 0) == pdTRUE) {
    parseAndExecute(String(incoming.text));
  }

  checkAndHandleStopRequest();

  if (mpuOK) {
    mpu.update();
    if (isnan(mpu.getAngleZ())) {
      mpuOK = false;
      mpuStatusMsg = "ERRO Leitura NaN";
      addLog("[ERRO MPU] Leitura invalida (NaN) no MPU6050!");
      handleEyes("X");
    } else {
      applyDriftCorrection();
      updateDriftCalibration();
    }
  } else {
    if (millis() - lastMpuRetryTime >= 3000) {
      lastMpuRetryTime = millis();
      setupMPU();
    }
  }

  updateSequences();

  if (turnActive) {
    updateTurnPID();
  } else {
    updateMovement();
  }
}
