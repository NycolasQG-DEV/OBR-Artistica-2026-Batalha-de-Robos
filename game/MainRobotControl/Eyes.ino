void buildLedMapping() {
  uint16_t acc = 0;
  for (uint8_t c = 0; c < NUM_COLS; c++) {
    colStart[c] = acc;
    acc += COL_LEN[c];
    colGoesDown[c] = (c % 2 != 0); // Fita dobrada: Col 0 sobe (false), Col 1 desce (true), Col 2 sobe...
  }
}

int16_t ledIndex(uint8_t col, uint8_t row) {
  if (col >= NUM_COLS || row >= COL_LEN[col]) return -1;
  if (colGoesDown[col]) return colStart[col] + row;
  return colStart[col] + (COL_LEN[col] - 1 - row);
}

const uint8_t DesenhoX[9][9] = {
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 1, 0, 0, 0, 0, 0, 1, 0},
  {0, 0, 1, 0, 0, 0, 1, 0, 0},
  {0, 0, 0, 1, 0, 1, 0, 0, 0},
  {0, 0, 0, 0, 1, 0, 0, 0, 0},
  {0, 0, 0, 1, 0, 1, 0, 0, 0},
  {0, 0, 1, 0, 0, 0, 1, 0, 0},
  {0, 1, 0, 0, 0, 0, 0, 1, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0}
};

const uint8_t DesenhoON[9][9] = {
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

const uint8_t DesenhoOlhoAberto[9][9] = {
  {0, 0, 1, 1, 1, 1, 1, 0, 0},
  {0, 1, 1, 1, 1, 1, 1, 1, 0},
  {0, 1, 1, 1, 1, 1, 1, 1, 0},
  {1, 1, 1, 1, 1, 1, 1, 1, 1},
  {1, 1, 1, 1, 1, 1, 1, 1, 1},
  {1, 1, 1, 1, 1, 1, 1, 1, 1},
  {0, 1, 1, 1, 1, 1, 1, 1, 0},
  {0, 1, 1, 1, 1, 1, 1, 1, 0},
  {0, 0, 1, 1, 1, 1, 1, 0, 0}
};

const uint8_t DesenhoOlhoMeio[9][9] = {
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 1, 1, 1, 1, 1, 0, 0},
  {1, 1, 1, 1, 1, 1, 1, 1, 1},
  {0, 0, 1, 1, 1, 1, 1, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0}
};

const uint8_t DesenhoOlhoFechado[9][9] = {
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 1, 1, 1, 1, 1, 1, 1, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0},
  {0, 0, 0, 0, 0, 0, 0, 0, 0}
};

// PADRÃO DE TESTE PARA DEBUG DA GRADE FÍSICA
// Desenha uma Cruz exata no centro (Linha 4, Coluna 4) e acende os 4 cantos
const uint8_t DesenhoTest[9][9] = {
  {1, 0, 0, 0, 1, 0, 0, 0, 1},
  {0, 0, 0, 0, 1, 0, 0, 0, 0},
  {0, 0, 0, 0, 1, 0, 0, 0, 0},
  {0, 0, 0, 0, 1, 0, 0, 0, 0},
  {1, 1, 1, 1, 1, 1, 1, 1, 1}, // Linha horizontal inteira
  {0, 0, 0, 0, 1, 0, 0, 0, 0},
  {0, 0, 0, 0, 1, 0, 0, 0, 0},
  {0, 0, 0, 0, 1, 0, 0, 0, 0},
  {1, 0, 0, 0, 1, 0, 0, 0, 1}
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

void drawAnimatedRainbow(uint8_t &hue) {
  for (uint8_t col = 0; col < NUM_COLS; col++) {
    uint8_t colHue = hue + col * (255 / NUM_COLS);
    CRGB color = CHSV(colHue, 255, 255);
    for (uint8_t row = 0; row < COL_LEN[col]; row++) {
      int16_t idx = ledIndex(col, row);
      if (idx >= 0) leds[idx] = color;
    }
  }
  FastLED.show();
  hue += 2;
}

// ============================================================================
// TASK ISOLADA PARA OS OLHOS (Roda em paralelo no FreeRTOS)
// ============================================================================
void EyesTask(void *pvParameters) {
  uint8_t rainbowHue = 0;

  while(true) {
    if (!systemReady) {
      vTaskDelay(100 / portTICK_PERIOD_MS);
      continue;
    }

    if (xSemaphoreTake(eyesMutex, portMAX_DELAY) == pdTRUE) {
      int state = currentEyeState;
      bool blinkOk = eyeSignalBlinkOk;
      bool blinkErr = eyeSignalBlinkErr;
      bool stateX = eyesX;
      xSemaphoreGive(eyesMutex);

      if (blinkOk) {
        for (int i = 0; i < 3; i++) {
          drawEyeMatrix(DesenhoON, CRGB(0, 230, 0));
          vTaskDelay(100 / portTICK_PERIOD_MS);
          drawEyeMatrix(DesenhoOFF, CRGB(0, 0, 0));
          vTaskDelay(70 / portTICK_PERIOD_MS);
        }
        drawEyeMatrix(DesenhoON, CRGB(0, 230, 0));
        vTaskDelay(300 / portTICK_PERIOD_MS);
        
        xSemaphoreTake(eyesMutex, portMAX_DELAY);
        eyeSignalBlinkOk = false; 
        xSemaphoreGive(eyesMutex);
        continue;
      }
      else if (blinkErr) {
        drawEyeMatrix(DesenhoX, CRGB(255, 0, 0));
        vTaskDelay(1000 / portTICK_PERIOD_MS);
        
        xSemaphoreTake(eyesMutex, portMAX_DELAY);
        eyeSignalBlinkErr = false;
        xSemaphoreGive(eyesMutex);
        continue;
      }
      else if (stateX) {
        drawEyeMatrix(DesenhoX, CRGB(255, 0, 0));
        vTaskDelay(50 / portTICK_PERIOD_MS);
        continue;
      }
      
      // LOGICA DOS 5 ESTADOS
      if (state == 0) {
        static unsigned long lastBlinkMs = 0;
        static int nextBlinkInterval = 2000;
        
        unsigned long now = millis();
        if (now - lastBlinkMs > (unsigned long)nextBlinkInterval) {
           int numBlinks = random(1, 3); // 1 ou 2 piscadas
           for(int b = 0; b < numBlinks; b++) {
              drawEyeMatrix(DesenhoOlhoMeio, CRGB(255, 20, 147));
              vTaskDelay(40 / portTICK_PERIOD_MS);
              drawEyeMatrix(DesenhoOlhoFechado, CRGB(255, 20, 147));
              vTaskDelay(60 / portTICK_PERIOD_MS);
              drawEyeMatrix(DesenhoOlhoMeio, CRGB(255, 20, 147));
              vTaskDelay(40 / portTICK_PERIOD_MS);
              drawEyeMatrix(DesenhoOlhoAberto, CRGB(255, 20, 147));
              if (b < numBlinks - 1) vTaskDelay(100 / portTICK_PERIOD_MS);
           }
           lastBlinkMs = millis();
           nextBlinkInterval = random(1000, 5000);
        } else {
           drawEyeMatrix(DesenhoOlhoAberto, CRGB(255, 20, 147));
        }
      } 
      else if (state == 1) {
        drawEyeMatrix(DesenhoOFF, CRGB(0, 0, 0));
      } 
      else if (state == 2) {
        drawEyeMatrix(DesenhoOFF, CRGB(0, 0, 0));
      } 
      else if (state == 3) {
        drawEyeMatrix(DesenhoOFF, CRGB(0, 0, 0));
      } 
      else if (state == 4) {
        // STATE 4 AGORA É O MODO DEBUG DE TELA!
        drawEyeMatrix(DesenhoTest, CRGB(0, 255, 255)); // Ciano pra destacar
      } 
      else {
        // Fallback
        drawEyeMatrix(DesenhoOFF, CRGB(0, 0, 0));
      }
    }
    
    vTaskDelay(50 / portTICK_PERIOD_MS);
  }
}

void setupEyesTask() {
  FastLED.addLeds<LED_TYPE, LED_PIN, COLOR_ORDER>(leds, NUM_LEDS).setCorrection(TypicalLEDStrip);
  FastLED.setBrightness(BRIGHTNESS);
  buildLedMapping();
  
  xTaskCreatePinnedToCore(
    EyesTask,
    "EyesTask",
    4096,
    NULL,
    1,
    NULL,
    1
  );
}

void handleEyes(String pattern) {
  pattern.trim();
  pattern.toUpperCase();
  
  xSemaphoreTake(eyesMutex, portMAX_DELAY);
  
  if (pattern == "X") {
    eyesX = true;
  } else if (pattern == "OFF_X") {
    eyesX = false;
  } else {
    int parsedState = pattern.toInt();
    if (parsedState >= 0 && parsedState <= 4) {
      currentEyeState = parsedState;
      eyesX = false;
    } else {
      sendDebug("ERR: animacao EYES state invalido -> " + pattern);
    }
  }
  xSemaphoreGive(eyesMutex);
}
