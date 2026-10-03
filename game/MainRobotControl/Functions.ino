void addLog(const String &msg) {
  if (xSemaphoreTake(serialMutex, portMAX_DELAY) == pdTRUE) {
    Serial.println(msg);
    xSemaphoreGive(serialMutex);
  }
}

void sendDebug(const String &msg) {
  addLog("[UART TX] " + msg);
  if (xSemaphoreTake(serialMutex, portMAX_DELAY) == pdTRUE) {
    Serial1.println(msg);
    xSemaphoreGive(serialMutex);
  }
}

void sendOkSignal() {
  addLog("[UART TX] ok");
  if (xSemaphoreTake(serialMutex, portMAX_DELAY) == pdTRUE) {
    Serial1.println("ok");
    xSemaphoreGive(serialMutex);
  }
}

void sendDebugAckOnly(const String &cmdStr) {
  String ack = "ACK:" + cmdStr;
  addLog("[UART TX] " + ack);
  if (xSemaphoreTake(serialMutex, portMAX_DELAY) == pdTRUE) {
    Serial1.println(ack);
    xSemaphoreGive(serialMutex);
  }
}

void sendDoneSignal(const String &seqName) {
  String doneMsg = "DONE";
  if (seqName.length() > 0) doneMsg += ":" + seqName;
  addLog("[UART TX] " + doneMsg);
  if (xSemaphoreTake(serialMutex, portMAX_DELAY) == pdTRUE) {
    Serial1.println(doneMsg);
    xSemaphoreGive(serialMutex);
  }
}

void sendTelemetry() {
  if (millis() - lastTelemetryTime >= 50) {
    lastTelemetryTime = millis();
    String line;
    if (mpuOK) {
      line = "DIR:" + String(getRealYaw(), 1);
    } else {
      line = "DIR:OFF";
    }
    if (xSemaphoreTake(serialMutex, portMAX_DELAY) == pdTRUE) {
      Serial1.println(line);
      Serial.println(line);
      xSemaphoreGive(serialMutex);
    }
  }
}

// ----------------------------------------------------------------------------
// SENSORS & DRIFT
// ----------------------------------------------------------------------------
float getRealYaw() {
  if (!mpuOK) return 0.0f;
  return mpu.getAngleZ() - driftCorrectionDeg;
}

float normalizeAngle(float deg) {
  while (deg >  180.0f) deg -= 360.0f;
  while (deg < -180.0f) deg += 360.0f;
  return deg;
}

void applyDriftCorrection() {
  if (!mpuOK) return;
  unsigned long now = millis();
  if (lastDriftApplyMs == 0) { lastDriftApplyMs = now; return; }
  float dt = (now - lastDriftApplyMs) / 1000.0f;
  if (dt > 0.0f && dt < 0.5f) {
    driftCorrectionDeg += gyroDriftRateDegS * dt;
  }
  lastDriftApplyMs = now;
}

void updateDriftCalibration() {
  if (!mpuOK) return;
  bool isIdle = (currentMove == MOVE_NONE && !turnActive && !timeMoveActive);

  if (!isIdle) {
    driftCalibActive  = false;
    driftCalibAccum   = 0.0f;
    driftCalibSamples = 0;
    motorsIdleSinceMs = 0;
    return;
  }

  unsigned long now = millis();
  if (motorsIdleSinceMs == 0) { motorsIdleSinceMs = now; return; }

  if (!driftCalibActive) {
    if (now - motorsIdleSinceMs >= DRIFT_IDLE_BEFORE_CALIB_MS) {
      driftCalibActive  = true;
      driftCalibAccum   = 0.0f;
      driftCalibSamples = 0;
      driftCalibStartMs = now;
    }
    return;
  }

  float gyroRate = mpu.getGyroZ();

  if (fabs(gyroRate) < DRIFT_MOTION_THRESHOLD_DEG_S) {
    driftCalibAccum += gyroRate;
    driftCalibSamples++;
  }

  if (now - driftCalibStartMs >= DRIFT_CALIB_DURATION_MS) {
    if (driftCalibSamples >= 5) {
      float measured = driftCalibAccum / (float)driftCalibSamples;
      measured = constrain(measured, -DRIFT_MAX_CORRECTION_DEG_S, DRIFT_MAX_CORRECTION_DEG_S);
      gyroDriftRateDegS = 0.7f * measured + 0.3f * gyroDriftRateDegS;
    }
    driftCalibActive  = false;
    motorsIdleSinceMs = now;
  }
}

void setupMPU() {
  Wire.end();
  delay(10);
  Wire.begin(PIN_SDA, PIN_SCL, 100000);
  delay(100);

  uint8_t targetAddr = 0;
  Wire.beginTransmission(0x68);
  if (Wire.endTransmission() == 0) {
    targetAddr = 0x68;
  } else {
    Wire.beginTransmission(0x69);
    if (Wire.endTransmission() == 0) targetAddr = 0x69;
  }

  if (targetAddr == 0) {
    mpuOK = false;
    mpuStatusMsg = "ERRO I2C (0x68/0x69)";
    sendDebug("[AVISO MPU] MPU6050 nao encontrado em 0x68 ou 0x69. Verifique fiacao SDA/SCL!");
    handleEyes("X");
    return;
  }

  byte mpuStatus = mpu.begin();
  if (mpuStatus != 0) {
    mpuOK = false;
    mpuStatusMsg = "ERRO mpu.begin() code " + String(mpuStatus);
    sendDebug("[AVISO MPU] Falha mpu.begin() no endereco 0x" + String(targetAddr, HEX));
    handleEyes("X");
  } else {
    sendDebug("Calibrando MPU6050 DinoByte no endereco 0x" + String(targetAddr, HEX) + "...");
    delay(500);
    mpu.calcOffsets(true, true);
    mpuOK = true;
    mpuStatusMsg = "OK";
    gyroDriftRateDegS  = 0.0f;
    driftCorrectionDeg = 0.0f;
    lastDriftApplyMs   = 0;
    motorsIdleSinceMs  = 0;
    sendDebug("[MPU OK] MPU6050 inicializado e calibrado. Drift compensation ativo.");
  }
}

// ----------------------------------------------------------------------------
// COMMAND PARSING & STATE LOGIC
// ----------------------------------------------------------------------------
bool checkAndHandleStopRequest() {
  if (!stopRequested) return false;
  stopRequested = false;

  currentMove = MOVE_NONE;
  moveSpeed = 0;
  diffLeftSpeed = 0;
  diffRightSpeed = 0;
  turnActive = false;
  timeMoveActive = false;

  motorLeft.stop();
  motorRight.stop();
  neckMotor.stop();
  mouthMotor.stop();

  sequenceAbortFlag = true;
  sendDebug("PARADA: STOP ou watchdog acionado — todos os atuadores parados.");
  return true;
}

bool interruptibleDelay(unsigned long ms) {
  unsigned long start = millis();
  while (millis() - start < ms) {
    if (checkAndHandleStopRequest()) return true;
    delay(1);
  }
  return false;
}

bool seqCheckAbort() {
  if (sequenceAbortFlag) {
    sequenceAbortFlag = false;
    seqActive = false;
    addLog("[SEQ] Sequencia abortada por STOP/watchdog.");
    return true;
  }
  return false;
}

void flushCmdQueue() {
  UartCmd dummy;
  int flushed = 0;
  while (xQueueReceive(cmdQueue, &dummy, 0) == pdTRUE) flushed++;
  if (flushed > 0) {
    addLog("[AVISO] flushCmdQueue: " + String(flushed) + " comando(s) descartado(s) da fila.");
  }
}

void checkUartWatchdog() {
  bool joystickMoving = (currentMove != MOVE_NONE) && !turnActive && !timeMoveActive;
  if (joystickMoving && !seqActive && (millis() - lastUartRxTime > UART_WATCHDOG_MS)) {
    stopRequested = true;
    sendDebug("WATCHDOG: UART sem comunicacao, parada de seguranca solicitada.");
  }
}

void parseAndExecute(String raw) {
  raw.trim();
  if (raw.length() == 0) return;

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

  if (cmd == "SEQ_MOV" && paramCount >= 1) {
    String dirStr = params[0];
    float val = (paramCount >= 2) ? params[1].toFloat() : 0.0f;
    int speed = (paramCount >= 3) ? params[2].toInt() : 220;
    handleMov(dirStr, val, speed);
  } else if (cmd == "SEQ_TURN" && paramCount >= 1) {
    float deltaDeg = params[0].toFloat();
    handleTurn(deltaDeg);
  } else if (cmd == "MOV") {
    String dirStr = params[0];
    float val = (paramCount >= 2) ? params[1].toFloat() : 0.0f;
    int speed = (paramCount >= 3) ? params[2].toInt() : 220;
    handleMov(dirStr, val, speed);
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

// ----------------------------------------------------------------------------
// MOVEMENT, PIDs & ACTUATORS
// ----------------------------------------------------------------------------

int scaleMovePwm(int speed) {
  if (speed <= 0) return 0;
  speed = constrain(speed, 1, 255);
  return map(speed, 1, 255, MOVE_PWM_MIN, MOVE_PWM_MAX);
}

int scaleTurnPwm(int speed) {
  if (speed <= 0) return 0;
  speed = constrain(speed, 1, 255);
  return map(speed, 1, 255, TURN_PWM_MIN, TURN_PWM_MAX);
}

void resetMotionState() {
  turnActive = false;
  timeMoveActive = false;
  stallBoostPwm = 0.0f;
  lastStallCheckMs = 0;
}

void handleStop() {
  currentMove = MOVE_NONE;
  moveSpeed = 0;
  diffLeftSpeed = 0;
  diffRightSpeed = 0;
  turnActive = false;
  timeMoveActive = false;
  stallBoostPwm = 0.0f;
  lastStallCheckMs = 0;
  motorLeft.stop();
  motorRight.stop();
  sendDebug("STOP: motores de tracao parados.");
}

void applyHeadingCorrection(float yawError, float dt, bool forward) {
  float correction = headingPID.compute(yawError, dt);
  
  // Garante força mínima de correção para vencer atrito estático no alinhamento retilíneo
  float absErr = fabs(yawError);
  if (absErr > 0.4f && fabs(correction) < 30.0f) {
    correction = (correction >= 0.0f) ? 30.0f : -30.0f;
  }

  // Limita a correção para que a roda nunca inverta o sentido enquanto tenta andar reto
  float maxCorr = fabs((float)moveSpeed);
  correction = constrain(correction, -maxCorr, maxCorr);

  int signed_base  = forward ? (int)moveSpeed : -(int)moveSpeed;
  int left_signed  = constrain(signed_base - (int)correction, -255, 255);
  int right_signed = constrain(signed_base + (int)correction, -255, 255);

  motorLeft.setSpeedSigned(left_signed);
  motorRight.setSpeedSigned(right_signed);
}

void updateTurnPID() {
  if (!turnActive) return;

  if (!mpuOK) {
    turnActive = false;
    stallBoostPwm = 0.0f;
    lastStallCheckMs = 0;
    motorLeft.stop();
    motorRight.stop();
    sendDebug("ERR: MPU falhou durante o giro. TURN abortado.");
    handleEyes("X");
    sendOkSignal();
    return;
  }

  unsigned long now = millis();
  float dt = (now - lastTurnTime_us) / 1000.0f;
  if (dt <= 0.0f || dt > 0.1f) dt = 0.01f;
  lastTurnTime_us = now;

  float yawAtual = getRealYaw();
  float error    = turnTargetYaw - yawAtual;
  float absError = fabs(error);

  if (absError <= TURN_DEADZONE_DEG) {
    motorLeft.stop();
    motorRight.stop();
    if (turnTimeInDeadzone == 0) turnTimeInDeadzone = millis();
    if (millis() - turnTimeInDeadzone > 200) {
      turnActive = false;
      stallBoostPwm = 0.0f;
      lastStallCheckMs = 0;
      sendDebug("TURN OK: Yaw=" + String(yawAtual, 1) + " err=" + String(error, 2) + " deg");
      sendOkSignal();
      turnTimeInDeadzone = 0;
      
      xSemaphoreTake(eyesMutex, portMAX_DELAY);
      eyeSignalBlinkOk = true;
      xSemaphoreGive(eyesMutex);
      
      return;
    }
    return;
  }

  turnTimeInDeadzone = 0;

  if (millis() - turnStartTime > 15000) {
    turnActive = false;
    stallBoostPwm = 0.0f;
    lastStallCheckMs = 0;
    motorLeft.stop();
    motorRight.stop();
    sendDebug("TURN: timeout de seguranca maximo (15s) atingido.");
    sendOkSignal();
    
    xSemaphoreTake(eyesMutex, portMAX_DELAY);
    eyeSignalBlinkErr = true;
    xSemaphoreGive(eyesMutex);
    
    return;
  }

  // ── DETECTOR INTELIGENTE DE ESTOLAGEM / ATRITO ──
  // Verifica a cada 100ms se o ângulo (yaw) parou de mudar sem ter atingido a deadzone
  if (lastStallCheckMs == 0) {
    lastStallCheckMs = now;
    lastStallYaw = yawAtual;
    stallBoostPwm = 0.0f;
  } else if (now - lastStallCheckMs >= 100) {
    float yawDelta = fabs(yawAtual - lastStallYaw);
    if (yawDelta < 0.15f && absError > TURN_DEADZONE_DEG) {
      // O robô travou no atrito do piso: injeta boost de torque progressivo
      stallBoostPwm += 8.0f;
      if (stallBoostPwm > 100.0f) stallBoostPwm = 100.0f;
    } else if (yawDelta >= 0.3f) {
      // O robô venceu o atrito e está girando: decai suavemente o boost extra
      stallBoostPwm -= 4.0f;
      if (stallBoostPwm < 0.0f) stallBoostPwm = 0.0f;
    }
    lastStallYaw = yawAtual;
    lastStallCheckMs = now;
  }

  float pidOutput = turnPID.compute(error, dt);

  float ffFade     = constrain(absError / TURN_BRAKE_ZONE_DEG, 0.0f, 1.0f);
  float dynamicMin = TURN_PWM_FLOOR + (TURN_PWM_MIN - TURN_PWM_FLOOR) * ffFade + stallBoostPwm;
  int magnitude    = (int)constrain(fabs(pidOutput) + dynamicMin, dynamicMin, (float)TURN_PWM_MAX);

  bool driveRight = (pidOutput >= 0.0f);
  turnDirectionRight = driveRight;

  if (driveRight) {
    motorLeft.forward(magnitude);
    motorRight.backward(magnitude);
  } else {
    motorLeft.backward(magnitude);
    motorRight.forward(magnitude);
  }
}

void updateMovement() {
  if (timeMoveActive) {
    if (millis() >= timeMoveEndTime) {
      timeMoveActive = false;
      
      float yawAtual = getRealYaw();
      float erroFinal = normalizeAngle(yawInicialMov - yawAtual);
      
      if (mpuOK && fabs(erroFinal) > TURN_DEADZONE_DEG) {
         sendDebug("MOV_TIME: tempo concluido. Realinhando " + String(erroFinal) + " graus.");
         handleTurn(erroFinal); // O handleTurn enviará o OK no final
      } else {
         handleStop();
         sendDebug("MOV_TIME: tempo concluido no alvo.");
         sendOkSignal();
      }
      return;
    }
    
    unsigned long elapsed = millis() - timeMoveStartTime;
    unsigned long remaining = timeMoveEndTime - millis();
    unsigned long totalDuration = timeMoveEndTime - timeMoveStartTime;
    
    float rampMs = 400.0f;
    if (totalDuration < 1200) {
        rampMs = totalDuration / 3.0f;
    }

    if (elapsed < rampMs) {
        float pct = (float)elapsed / rampMs;
        moveSpeed = MOVE_PWM_MIN + (targetMoveSpeed - MOVE_PWM_MIN) * pct;
    } else if (remaining < rampMs) {
        float pct = (float)remaining / rampMs;
        moveSpeed = MOVE_PWM_MIN + (targetMoveSpeed - MOVE_PWM_MIN) * pct;
    } else {
        moveSpeed = targetMoveSpeed;
    }
  }

  unsigned long now = millis();
  float dt = (now - lastMoveTime_us) / 1000.0f;
  if (dt <= 0.0f || dt > 0.1f) dt = 0.01f;
  lastMoveTime_us = now;

  switch (currentMove) {
    case MOVE_FORWARD:
    case MOVE_BACKWARD: {
      bool goingForward = (currentMove == MOVE_FORWARD);
      if (mpuOK) {
        float yawAtual = getRealYaw();
        float yawError = normalizeAngle(yawInicialMov - yawAtual);
        applyHeadingCorrection(yawError, dt, goingForward);
      } else {
        if (goingForward) {
          motorLeft.forward(moveSpeed);
          motorRight.forward(moveSpeed);
        } else {
          motorLeft.backward(moveSpeed);
          motorRight.backward(moveSpeed);
        }
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
      motorLeft.stop();
      motorRight.stop();
      break;
  }
}

void handleTurn(float deltaDeg) {
  currentMove = MOVE_NONE;
  moveSpeed = 0;
  motorLeft.stop();
  motorRight.stop();
  turnDirectionRight = (deltaDeg >= 0.0f);
  turnStartTime = millis();
  turnPID.reset();

  turnTimeInDeadzone = 0;
  lastTurnTime_us    = millis();

  if (mpuOK) {
    turnInitialYaw = getRealYaw();
    turnTargetYaw = turnInitialYaw + deltaDeg;
    turnActive = true;
    sendDebug("TURN (MPU): delta=" + String(deltaDeg) + " deg, alvo=" + String(turnTargetYaw, 1));
  } else {
    turnActive = false;
    sendDebug("ERR: TURN abortado (MPU falhou)");
    handleEyes("X");
    sendOkSignal();
  }

  while (turnActive) {
    if (checkAndHandleStopRequest()) break;
    if (mpuOK) { mpu.update(); applyDriftCorrection(); }
    updateTurnPID();
    sendTelemetry();
    delay(1);
  }
  turnTimeInDeadzone = 0;
}

void handleMovTime(long durationMs, int speed, MoveDirection forceDir) {
  flushCmdQueue();
  resetMotionState();
  
  if (forceDir != MOVE_NONE) {
    currentMove = forceDir;
    durationMs = abs(durationMs);
  } else {
    if (durationMs >= 0) {
      currentMove = MOVE_FORWARD;
    } else {
      currentMove = MOVE_BACKWARD;
      durationMs = -durationMs;
    }
  }
  
  targetMoveSpeed = scaleMovePwm(speed);
  moveSpeed = MOVE_PWM_MIN;
  yawInicialMov = mpuOK ? getRealYaw() : 0.0f;
  headingPID.reset();
  lastMoveTime_us = millis();
  timeMoveStartTime = millis();
  timeMoveEndTime = millis() + (unsigned long)durationMs;
  timeMoveActive = true;
  sendDebug("MOV_TIME: tempo=" + String(durationMs) + "ms, max_speed=" + String(targetMoveSpeed));

  while (timeMoveActive) {
    if (checkAndHandleStopRequest()) break;
    if (mpuOK) { mpu.update(); applyDriftCorrection(); }
    updateMovement();
    sendTelemetry();
    delay(1);
  }
}

void handleDiffMov(int leftSpeed, int rightSpeed) {
  resetMotionState();
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

void handleMov(String dirStr, float val, int speed) {
  dirStr.trim();
  dirStr.toUpperCase();
  MoveDirection dir = MOVE_NONE;
  if (dirStr == "W" || dirStr == "FRENTE") dir = MOVE_FORWARD;
  else if (dirStr == "S" || dirStr == "TRAS") dir = MOVE_BACKWARD;
  else if (dirStr == "A" || dirStr == "ESQUERDA") dir = MOVE_LEFT;
  else if (dirStr == "D" || dirStr == "DIREITA") dir = MOVE_RIGHT;

  if (val > 0.0f) {
    if (dir == MOVE_LEFT) {
      handleTurn(-val);
    } else if (dir == MOVE_RIGHT) {
      handleTurn(val);
    } else {
      handleMovTime(val, speed, dir);
    }
  } else {
    resetMotionState();
    currentMove = dir;
    moveSpeed = (dir == MOVE_LEFT || dir == MOVE_RIGHT) ? scaleTurnPwm(speed) : scaleMovePwm(speed);
    yawInicialMov = mpuOK ? getRealYaw() : 0.0f;
    headingPID.reset();
    sendDebug("MOV LIVRE: dir=" + dirStr + ", speed=" + String(moveSpeed));
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
    if (seqCheckAbort()) return;
    handleTurn(90.0f);
    if (seqCheckAbort()) return;
    handleMov("TRAS", 50.0f, 220);
    if (seqCheckAbort()) return;
    handleMouth(2.0f);
    if (seqCheckAbort()) return;
    handleNeck("LEFT", 1500);
    if (seqCheckAbort()) return;
    handleNeck("ZERO", 0);
    if (seqCheckAbort()) return;

    seqActive = false;
    addLog("[SEQ] DEFAULT concluida.");
    sendDoneSignal("DEFAULT");
  }
}

void handleNeck(String action, long timeMs) {
  action.trim();
  action.toUpperCase();
  if (action == "LEFT") {
    long target = constrain(neckPositionMs - timeMs, (long)NECK_MIN_MS, (long)NECK_MAX_MS);
    long actualMs = neckPositionMs - target;
    neckPositionMs = target;
    neckMotor.forward(255);
    sendDebug("NECK: LEFT por " + String(actualMs) + "ms (limitado ao curso permitido)");
    interruptibleDelay(actualMs);
    neckMotor.stop();
  } else if (action == "RIGHT") {
    long target = constrain(neckPositionMs + timeMs, (long)NECK_MIN_MS, (long)NECK_MAX_MS);
    long actualMs = target - neckPositionMs;
    neckPositionMs = target;
    neckMotor.backward(255);
    sendDebug("NECK: RIGHT por " + String(actualMs) + "ms (limitado ao curso permitido)");
    interruptibleDelay(actualMs);
    neckMotor.stop();
  } else if (action == "ZERO" || action == "CENTER") {
    sendDebug("NECK: Retornando ao ponto ZERO. Pos atual=" + String(neckPositionMs) + "ms");
    if (neckPositionMs > 0) {
      neckMotor.forward(255);
      if (!interruptibleDelay(neckPositionMs)) neckPositionMs = 0;
    } else if (neckPositionMs < 0) {
      neckMotor.backward(255);
      if (!interruptibleDelay(-neckPositionMs)) neckPositionMs = 0;
    }
    neckMotor.stop();
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
  if (interruptibleDelay(calibrationMs)) return;
  mouthMotor.stop();

  sendDebug("MOUTH: Aguardando " + String(waitSeconds) + "s");
  if (interruptibleDelay((unsigned long)(waitSeconds * 1000.0f))) return;

  sendDebug("MOUTH: Fechando");
  mouthMotor.backward(255);
  if (interruptibleDelay(calibrationMs)) return;
  mouthMotor.stop();
}
