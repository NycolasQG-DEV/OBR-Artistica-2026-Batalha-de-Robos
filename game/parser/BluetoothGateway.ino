// BluetoothSerial é deprecated no core 4.x, mas funciona normalmente no 3.x.
// O pragma abaixo suprime o warning durante a compilação.
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wdeprecated-declarations"
#include "BluetoothSerial.h"
#pragma GCC diagnostic pop

#if !defined(CONFIG_BT_ENABLED) || !defined(CONFIG_BLUEDROID_ENABLED)
#error Bluetooth Classic nao esta habilitado. Ative em: Tools > Partition Scheme (com BT habilitado)
#endif

#define BT_DEVICE_NAME "DinoByte"

#define GATEWAY_UART_RX_PIN   16
#define GATEWAY_UART_TX_PIN   17
#define GATEWAY_UART_BAUDRATE 115200

#define BRIDGE_BUFFER_SIZE 256

BluetoothSerial SerialBT;
bool btWasConnected = false;

String btRxLine = "";
String uartRxLine = "";

void addLog(const String &msg) {
  Serial.println(msg);
}

void sendSafetyStop() {
  // STOP() já para todos os atuadores (motores + pescoço + boca) no ESP32-S3.
  // NECK(STOP) e MOUTH(STOP) seriam redundantes, e MOUTH(STOP) não existe
  // no parser do S3 (seria interpretado como handleMouth(0), abrindo a boca).
  Serial2.print("STOP()\n");
  addLog("[Gateway] Bluetooth caiu -> parada de seguranca enviada ao ESP32-S3.");
}

void setup() {
  Serial.begin(115200);
  delay(200);
  
  Serial2.begin(GATEWAY_UART_BAUDRATE, SERIAL_8N1, GATEWAY_UART_RX_PIN, GATEWAY_UART_TX_PIN);

  if (!SerialBT.begin(BT_DEVICE_NAME)) {
    addLog("[Gateway] ERRO ao iniciar Bluetooth Classic!");
  } else {
    addLog("[Gateway] Bluetooth Classic ativo. Nome: " + String(BT_DEVICE_NAME));
    addLog("[Gateway] Aguardando conexao Bluetooth...");
  }
}

void loop() {
  bool btConnected = SerialBT.hasClient();
  
  if (btWasConnected && !btConnected) {
    addLog("[BT] Bluetooth Classic DESCONECTADO!");
    sendSafetyStop();
  }
  
  if (!btWasConnected && btConnected) {
    addLog("[BT] Bluetooth Classic CONECTADO ao dispositivo remoto.");
  }
  
  btWasConnected = btConnected;

  int btAvail = SerialBT.available();
  if (btAvail > 0) {
    uint8_t buf[BRIDGE_BUFFER_SIZE];
    int toRead = btAvail > BRIDGE_BUFFER_SIZE ? BRIDGE_BUFFER_SIZE : btAvail;
    int n = SerialBT.readBytes(buf, toRead);
    if (n > 0) {
      Serial2.write(buf, n);
      for (int i = 0; i < n; i++) {
        char c = (char)buf[i];
        if (c == '\n') {
          if (btRxLine.length() > 0) {
            addLog("[BT -> UART] RX: " + btRxLine);
            btRxLine = "";
          }
        } else if (c != '\r') {
          btRxLine += c;
          if (btRxLine.length() >= 120) {
            addLog("[BT -> UART] RX: " + btRxLine);
            btRxLine = "";
          }
        }
      }
    }
  }

  // ── UART (S3) → Bluetooth ────────────────────────────────────────────────
  // Usa line-buffering: acumula caracteres do S3 até encontrar '\n', depois
  // envia a linha COMPLETA ao cliente BT de uma vez.
  // Isso garante que "ok", "DONE:xxx" e "ACK:xxx" cheguem íntegros,
  // sem fragmentação causada por leituras parciais do buffer UART.
  while (Serial2.available() > 0) {
    char c = (char)Serial2.read();
    if (c == '\r') continue; // ignora CR

    if (c == '\n') {
      if (uartRxLine.length() > 0) {
        // Envia a linha completa ao Bluetooth com \r\n para compatibilidade máxima
        String outLine = uartRxLine + "\r\n";
        SerialBT.print(outLine);

        // Log destacado para respostas especiais do S3
        if (uartRxLine == "ok") {
          addLog("[S3 -> BT] <<< ok >>> (comando concluido)");
        } else if (uartRxLine.startsWith("DONE")) {
          addLog("[S3 -> BT] <<< " + uartRxLine + " >>> (sequencia concluida)");
        } else {
          addLog("[UART -> BT] " + uartRxLine);
        }

        uartRxLine = "";
      }
    } else {
      uartRxLine += c;
      // Segurança: descarta linha se estiver muito longa
      if (uartRxLine.length() >= 120) {
        addLog("[AVISO] Linha UART muito longa, descartada: " + uartRxLine);
        uartRxLine = "";
      }
    }
  }
}
