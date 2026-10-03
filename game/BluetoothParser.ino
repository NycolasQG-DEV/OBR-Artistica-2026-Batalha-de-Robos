#include "BluetoothSerial.h"

#if !defined(CONFIG_BT_ENABLED) || !defined(CONFIG_BLUEDROID_ENABLED)
#error Bluetooth Classic nao esta habilitado.
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
  Serial2.print("STOP()\n");
  Serial2.print("NECK(STOP)\n");
  Serial2.print("MOUTH(STOP)\n");
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

  int uartAvail = Serial2.available();
  if (uartAvail > 0) {
    uint8_t buf[BRIDGE_BUFFER_SIZE];
    int toRead = uartAvail > BRIDGE_BUFFER_SIZE ? BRIDGE_BUFFER_SIZE : uartAvail;
    int n = Serial2.readBytes(buf, toRead);
    if (n > 0) {
      SerialBT.write(buf, n);
      for (int i = 0; i < n; i++) {
        char c = (char)buf[i];
        if (c == '\n') {
          if (uartRxLine.length() > 0) {
            addLog("[UART -> BT] TX: " + uartRxLine);
            uartRxLine = "";
          }
        } else if (c != '\r') {
          uartRxLine += c;
          if (uartRxLine.length() >= 120) {
            addLog("[UART -> BT] TX: " + uartRxLine);
            uartRxLine = "";
          }
        }
      }
    }
  }
}
