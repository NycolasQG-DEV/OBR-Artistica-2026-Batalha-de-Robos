"""game/combat/serial_controller.py — Controlador Serial Otimizado para ESP32 / DinoByte.

Comunicação bidirecional via Serial (Bluetooth/UART) com o robô ESP32.
Envia comandos de movimento em cm (MOV) e giro em graus tarados (TURN) e aguarda
confirmação "ok" do ESP32 para prosseguir para a próxima instrução.

Garante suporte a verificação de estado da conexão (is_connected) antes da inicialização do jogo.
"""

from __future__ import annotations
import asyncio
import threading
import time
import sys
from typing import Any, Optional, Dict

try:
    import serial
    import serial.tools.list_ports
    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False


class SerialController:
    """Controlador de comunicação Serial/Bluetooth com o robô ESP32."""

    def __init__(self) -> None:
        from settings import DEV_MODE, SERIAL_PORT, SERIAL_BAUDRATE, SERIAL_TIMEOUT

        self.dev_mode: bool = DEV_MODE
        self.port_name: str = SERIAL_PORT
        self.baudrate: int = SERIAL_BAUDRATE
        self.timeout: float = SERIAL_TIMEOUT

        self.serial_conn: Optional[Any] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._running: bool = False

        # Eventos de confirmação "ok" por robô ("PLAYER" e "BOSS") e rastreamento de ação ("TURN" vs "MOV")
        self._ok_events: Dict[str, threading.Event] = {
            "PLAYER": threading.Event(),
            "BOSS": threading.Event(),
        }
        self._last_sent_action: Dict[str, str] = {"PLAYER": "", "BOSS": ""}
        self._active_ok_type: Dict[str, str] = {"PLAYER": "", "BOSS": ""}

        # Inicializa todos os eventos como SET (True), indicando robô pronto para o primeiro comando
        for evt in self._ok_events.values():
            evt.set()

        self._last_rx_line: str = ""

        # Tenta conectar se não estiver em DEV_MODE
        if not self.dev_mode:
            self._connect()
        else:
            print("[SerialController] DEV_MODE ATIVO: Execução em modo de simulação sem portas COM.")

    def is_connected(self) -> bool:
        """Retorna True se estiver em DEV_MODE ou se a porta Serial estiver efetivamente aberta."""
        if self.dev_mode:
            return True
        return self.serial_conn is not None and getattr(self.serial_conn, "is_open", False)

    def try_connect(self, port_name: Optional[str] = None) -> bool:
        """Tenta estabelecer a conexão serial com a porta especificada."""
        if self.dev_mode:
            return True

        if self.is_connected():
            return True

        if port_name:
            self.port_name = port_name

        return self._connect()

    def _get_robot_tag(self, robot: Any) -> str:
        """Retorna 'PLAYER' ou 'BOSS' dependendo da entidade do robô."""
        if hasattr(robot, "is_player"):
            return "PLAYER" if robot.is_player else "BOSS"
        if isinstance(robot, str):
            r_upper = robot.upper()
            if "BOSS" in r_upper:
                return "BOSS"
        return "PLAYER"

    def _find_com_port(self) -> str | None:
        """Busca automaticamente uma porta COM disponível se SERIAL_PORT == 'AUTO'."""
        if not HAS_PYSERIAL:
            return None
        ports = serial.tools.list_ports.comports()
        if not ports:
            return None
        for p in ports:
            desc = p.description.lower()
            if "bluetooth" in desc or "ch340" in desc or "cp210" in desc or "usb" in desc or "uart" in desc:
                return p.device
        return ports[0].device

    def _connect(self) -> bool:
        if not HAS_PYSERIAL:
            print("[SerialController] AVISO: pyserial não está instalado.")
            return False

        target_port = self.port_name
        if target_port == "AUTO" or not target_port:
            found = self._find_com_port()
            if found:
                target_port = found
            else:
                print("[SerialController] Nenhuma porta COM física foi encontrada no momento.")
                return False

        try:
            print(f"[SerialController] Conectando à porta serial {target_port} @ {self.baudrate} baud...")
            self.serial_conn = serial.Serial(target_port, self.baudrate, timeout=0.1)
            time.sleep(0.5)
            self._running = True
            if not self._reader_thread or not self._reader_thread.is_alive():
                self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
                self._reader_thread.start()
            print(f"[SerialController] Conectado com SUCESSO à porta {target_port}!")
            return True
        except Exception as e:
            print(f"[SerialController] Tentativa de conexão na porta {target_port} falhou: {e}")
            self.serial_conn = None
            return False

    def ensure_connected(self, target_port: str = "COM7", max_retries: int = 5, retry_interval: float = 0.5) -> bool:
        """Garante a conexão especificamente com a porta serial configurada (padrão COM7) antes de iniciar."""
        if self.dev_mode:
            print("[SerialController] Modo DEV_MODE ativo (Simulação). Conexão OK.")
            return True

        self.port_name = target_port

        if self.is_connected():
            return True

        for attempt in range(1, max_retries + 1):
            if self.is_connected():
                return True
            print(f"[SerialController] Tentativa {attempt}/{max_retries} de conectar à porta serial {self.port_name}...")
            if self._connect():
                return True
            time.sleep(retry_interval)

        # Se a porta COM7 falhar (ex: ocupada por outro processo), varre portas alternativas de fallback
        if not self.is_connected() and HAS_PYSERIAL:
            try:
                ports = serial.tools.list_ports.comports()
                for p in ports:
                    if p.device != target_port:
                        print(f"[SerialController] Tentando porta alternativa {p.device} ({p.description})...")
                        self.port_name = p.device
                        if self._connect():
                            return True
                        self.port_name = target_port
            except Exception as e:
                print(f"[SerialController] Erro ao listar portas alternativas: {e}")

        return self.is_connected()

    def _read_loop(self) -> None:
        """Loop contínuo de leitura de bytes na porta serial."""
        buf = bytearray()
        while self._running and self.serial_conn and self.serial_conn.is_open:
            try:
                data = self.serial_conn.read(self.serial_conn.in_waiting or 1)
                if data:
                    buf.extend(data)
                    while b'\n' in buf:
                        line_bytes, buf = buf.split(b'\n', 1)
                        line = line_bytes.decode('utf-8', errors='ignore').strip()
                        if line:
                            self._handle_incoming_line(line)
            except Exception as e:
                print(f"[SerialController Thread] Exceção na leitura serial: {e}")
                time.sleep(0.1)

    def _handle_incoming_line(self, line: str) -> None:
        self._last_rx_line = line
        print(f"[ESP32 RX] {line}")
        line_upper = line.upper().strip()

        # Ignora mensagens de recepção/ACK (como 'ACK:WAKE' ou 'ACK:MOV(...)') e mensagens de erro
        # Elas indicam apenas o recebimento da mensagem, NÃO o término do movimento físico do robô!
        if line_upper.startswith("ACK:") or line_upper.startswith("ERR:"):
            return

        # Reconhece apenas o término efetivo da ação física do ESP32 ('OK', 'DONE', 'SUCCESS', 'CONCLUIDO', 'K')
        if line_upper == "OK" or line_upper == "K" or line_upper.startswith("OK:") or "DONE" in line_upper or "SUCCESS" in line_upper or "CONCLUIDO" in line_upper:
            # Classifica o tipo do OK recebido (específico de TURN vs MOV)
            ok_type = "ANY"
            if any(k in line_upper for k in ("TURN", "YAW", "GIRO", "ANGLE")):
                ok_type = "TURN"
            elif any(k in line_upper for k in ("MOV", "TIME", "STOP")):
                ok_type = "MOV"

            print(f"[SerialController] FIM DE AÇÃO FÍSICA CONFIRMADO ({line_upper}) -> Desbloqueando OK!")
            for tag in ("PLAYER", "BOSS"):
                self._active_ok_type[tag] = ok_type
                if tag in self._ok_events:
                    self._ok_events[tag].set()

    def get_prefix(self, robot: Any) -> str:
        return "RB"

    def format_command(self, action: str, value: float, speed: int) -> str:
        """Formata os comandos no padrão exato especificado:
        - Giro: turn(<grau>)
        - Frente: mov(W,<tempo em ms>,<potencia de 150 até 200>)
        - Tras: mov(S,<tempo em ms>,<potencia de 150 até 200>)
        """
        act_upper = action.strip().upper()
        
        # Limita a potência estritamente entre 150 e 200
        speed_clamped = min(200, max(150, int(speed))) if speed > 0 else 180

        if act_upper in ("W", "F", "FRENTE", "FORWARD", "S", "T", "TRAS", "BACKWARD", "MOV", "A", "D", "ESQUERDA", "DIREITA"):
            if act_upper in ("S", "T", "TRAS", "BACKWARD"):
                dir_char = "S"
            elif act_upper in ("A", "ESQUERDA"):
                dir_char = "A"
            elif act_upper in ("D", "DIREITA"):
                dir_char = "D"
            else:
                dir_char = "W"
            
            # Cada tile no código de movimento equivale a 600ms de andar reto
            if abs(value) <= 10.0:
                tiles = abs(value)
            else:
                tiles = abs(value) / 54.0

            tempo_ms = int(tiles * 800.0)
            
            return f"mov({dir_char},{tempo_ms},{speed_clamped})"

        elif act_upper in ("TURN", "TURN_RIGHT", "TURN_LEFT", "DIR_RIGHT", "DIR_LEFT", "GIRO", "RODADO"):
            deg = float(value)
            if act_upper in ("TURN_LEFT", "DIR_LEFT"):
                deg = -abs(deg)  # Esquerda no físico ESP32 é negativo
            elif act_upper in ("TURN_RIGHT", "DIR_RIGHT"):
                deg = abs(deg)   # Direita no físico ESP32 é positivo
            elif act_upper == "TURN":
                deg = -deg       # Inverte pois Panda3D (+) é Esquerda, ESP32 (+) é Direita
            return f"turn({deg:.1f})"
        elif act_upper == "STOP":
            return "STOP()"
        else:
            if "(" in action:
                return action
            return f"{action}({value:.1f},{speed_clamped})"

    # ── Configuração de Comunicação Serial do Boss ─────────────────────
    BOSS_SERIAL_ENABLED: bool = False

    def _is_boss_bypassed(self, robot: Any) -> bool:
        """Retorna True se o robô for o Boss/IA e a comunicação serial do Boss estiver desabilitada."""
        if self.BOSS_SERIAL_ENABLED:
            return False
        if robot is None:
            return False
        
        tag = self._get_robot_tag(robot)
        return tag == "BOSS"

    def write_command(self, robot: Any, action: str, value: float, speed: int) -> None:
        """Envia o comando formatado para o ESP32 via Serial ou simula em DEV_MODE."""
        tag = self._get_robot_tag(robot)

        if self._is_boss_bypassed(robot):
            if tag in self._ok_events:
                self._ok_events[tag].set()
            return

        cmd_str = self.format_command(action, value, speed)
        act_upper = action.strip().upper()

        # Determina o tipo esperado de OK para este comando ("TURN" vs "MOV")
        expected_type = "TURN" if act_upper in ("TURN", "TURN_RIGHT", "TURN_LEFT", "DIR_RIGHT", "DIR_LEFT", "GIRO", "RODADO") else "MOV"
        self._last_sent_action[tag] = expected_type
        self._active_ok_type[tag] = ""

        # Ao transmitir um comando serial físico, limpa o evento OK para aguardar o ESP32
        if tag in self._ok_events:
            self._ok_events[tag].clear()

        if act_upper in ("W", "S", "MOV", "FRENTE", "TRAS", "ESQUERDA", "DIREITA") and abs(value) < 0.01:
            self._ok_events[tag].set()
            return

        if self.dev_mode:
            print(f"[Serial DEV SIMULATION] Ignorando envio real de sinal serial para {tag}: {cmd_str}")
            self._ok_events[tag].set()
            return

        if self.serial_conn and getattr(self.serial_conn, "is_open", False):
            try:
                self.serial_conn.write(b"WAKE\r\n")
                self.serial_conn.flush()
                time.sleep(0.005)

                print(f"[Serial TX][{tag}] {cmd_str} (Esperando OK tipo: '{expected_type}')")
                msg = (cmd_str + "\r\n").encode('utf-8')
                self.serial_conn.write(msg)
                self.serial_conn.flush()
            except Exception as e:
                print(f"[SerialController] Erro ao transmitir comando '{cmd_str}': {e}")
                self._ok_events[tag].set()
        else:
            print(f"[SerialController] Porta desconectada. Comando ignorado: {cmd_str}")
            self._ok_events[tag].set()

    def is_ok_set(self, robot: Any) -> bool:
        """Retorna True se o robô respondeu OK ao comando anterior (ou se em DEV_MODE / desconectado)."""
        if self.dev_mode or not self.is_connected() or self._is_boss_bypassed(robot):
            return True
        tag = self._get_robot_tag(robot)
        event = self._ok_events.get(tag, self._ok_events["PLAYER"])
        return event.is_set()

    async def wait_ok(self, robot: Any, expected_action: Optional[str] = None) -> None:
        """Aguarda a confirmação 'ok' do ESP32 antes de prosseguir para o próximo comando."""
        if self.dev_mode or not self.is_connected() or self._is_boss_bypassed(robot):
            # Simula o tempo físico do robô para não executar a fila inteira num único frame
            # Isso impede que o SlideEngine feche o jogo logo na tela de carregamento!
            if expected_action:
                act = expected_action.upper()
                if act in ("W", "S", "MOV", "FRENTE", "TRAS"):
                    await asyncio.sleep(1.0)
                elif "TURN" in act or "GIRO" in act or "DIR" in act:
                    await asyncio.sleep(1.5)
                else:
                    await asyncio.sleep(0.5)
            else:
                await asyncio.sleep(0.5)
            return

        tag = self._get_robot_tag(robot)
        event = self._ok_events.get(tag, self._ok_events["PLAYER"])

        start_time = time.time()
        max_wait = 15.0

        while True:
            if event.is_set():
                print(f"[SerialController] OK confirmado para [{tag}]! Prosseguindo para o proximo comando.")
                break

            if time.time() - start_time > max_wait:
                print(f"[SerialController] TIMEOUT ({max_wait}s) aguardando 'ok' para [{tag}] — liberando evento.")
                event.set()
                break
            await asyncio.sleep(0.01)

    def send_command_realtime(self, robot: Any, action: str, speed: Any = 200) -> None:
        """Envia comandos contínuos sem esperar ok (usado em minigames em tempo real)."""
        if self._is_boss_bypassed(robot):
            return

        tag = self._get_robot_tag(robot)
        act_upper = action.strip().upper()

        if act_upper in ("DIFF", "DIFF_MOV"):
            if isinstance(speed, (tuple, list)) and len(speed) >= 2:
                cmd = f"DIFF_MOV({int(speed[0])}, {int(speed[1])})"
            else:
                cmd = f"DIFF_MOV({int(speed)}, {int(speed)})"
        elif act_upper in ("W", "F", "FRENTE"):
            sp = speed[0] if isinstance(speed, (tuple, list)) else speed
            cmd = f"MOV(W, 0.0, {int(sp)})"
        elif act_upper in ("S", "T", "TRAS"):
            sp = speed[0] if isinstance(speed, (tuple, list)) else speed
            cmd = f"MOV(S, 0.0, {int(sp)})"
        elif act_upper in ("TURN_LEFT", "DIR_LEFT"):
            sp = speed[0] if isinstance(speed, (tuple, list)) else speed
            cmd = f"TURN(-{int(sp)})"
        elif act_upper in ("TURN_RIGHT", "DIR_RIGHT"):
            sp = speed[0] if isinstance(speed, (tuple, list)) else speed
            cmd = f"TURN({int(sp)})"
        elif act_upper == "STOP":
            cmd = "STOP()"
        else:
            if isinstance(speed, (tuple, list)):
                speeds_str = ", ".join(str(int(s)) for s in speed)
                cmd = f"{act_upper}({speeds_str})"
            else:
                cmd = f"{act_upper}(0.0, {int(speed)})"

        if self.dev_mode:
            print(f"[Serial RT DEV TX][{tag}] {cmd}")
            return

        now = time.time()
        # Taxa máxima de transmissão de tempo real: a cada 40ms (~25 Hz) ou se o comando mudou
        if cmd == getattr(self, "_last_realtime_cmd", "") and (now - getattr(self, "_last_realtime_time", 0.0)) < 0.04:
            return

        self._last_realtime_cmd = cmd
        self._last_realtime_time = now

        if self.serial_conn and getattr(self.serial_conn, "is_open", False):
            try:
                self.serial_conn.write((cmd + "\r\n").encode('utf-8'))
            except Exception:
                pass


    def close(self) -> None:
        """Encerra a comunicação serial de forma limpa."""
        self._running = False
        if self.serial_conn:
            try:
                self.serial_conn.close()
            except Exception:
                pass
            self.serial_conn = None


_serial_instance: SerialController | None = None


def get_serial_controller() -> SerialController:
    global _serial_instance
    if _serial_instance is None:
        _serial_instance = SerialController()
    return _serial_instance
