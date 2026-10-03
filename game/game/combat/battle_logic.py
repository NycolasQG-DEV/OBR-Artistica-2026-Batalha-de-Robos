# combat/battle_logic.py — turn and combat management logic
import random
import time
from typing import Callable, Any, Optional

from settings import (
    STATE_SELECT_ROBOT, STATE_MINIGAME, STATE_IA_TURN, STATE_PLAYER_TURN,
    STATE_GAME_OVER, MINIGAME_DURATION, IA_THINK_TIME, MAX_ROUNDS, C_PURPLE,
    C_GREEN, C_RED, PLAYER_BASE_COORDS, STATE_ATTACK_MINIGAME, MATCH_DURATION,
    STATE_TIMEOUT
)

# Tempo restante (segundos) abaixo do qual nenhum novo ataque pode ser iniciado
TIMER_BLOCK_THRESHOLD = 30.0

from game.combat.entities import Robot
import asyncio

_PENDING_TICKS: list[asyncio.Future] = []

async def _tick():
    fut = asyncio.get_event_loop().create_future()
    _PENDING_TICKS.append(fut)
    await fut

async def wait(ticks: int):
    for _ in range(max(0, ticks)):
        await _tick()

async def wait_seconds(seconds: float):
    from settings import FPS
    await wait(int(seconds * FPS))

async def _yield_to_tasks():
    await asyncio.sleep(0)

class ActionRunner:
    def __init__(self):
        self._loop  = asyncio.new_event_loop()
        self._tasks: list[asyncio.Task] = []

    def start(self, coro):
        task = self._loop.create_task(coro)
        self._tasks.append(task)

    def update(self):
        pending = _PENDING_TICKS[:]
        _PENDING_TICKS.clear()
        for fut in pending:
            if not fut.done():
                fut.set_result(None)
        self._loop.run_until_complete(_yield_to_tasks())
        for task in self._tasks[:]:
            if task.done():
                self._tasks.remove(task)
                if not task.cancelled():
                    exc = task.exception()
                    if exc:
                        raise exc

    @property
    def is_done(self) -> bool:
        return len(self._tasks) == 0

    def clear(self):
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()
        _PENDING_TICKS.clear()



class BattleLogic:
    """Manages the turn-based state machine, rounds, timeouts and damage calculation."""

    def __init__(self, camera: Any, create_floating_fn: Callable[[float, float, str, Any, float], None], create_particles_fn: Callable[[float, float, Any, int, float], None], log_fn: Callable[[str], None]) -> None:
        self.camera = camera
        self.create_floating = create_floating_fn
        self.create_particles = create_particles_fn
        self.log = log_fn

        self.player_robot: Optional[Robot] = None
        self.ia_robot: Optional[Robot] = None

        self.turn_number: int = 1
        self.player_rounds: int = 0
        self.is_executing_action: bool = False
        self.action_complete_time: float = 0.0
        self.ia_thinking_time: float = 0.0

        self.chosen_action: Optional[str] = None
        self.mini_game_result: str = "good"

        self.state: str = STATE_SELECT_ROBOT
        self.winner: Optional[str] = None

        self._runner: ActionRunner = ActionRunner()
        self._bg_runner: ActionRunner = ActionRunner()
        self.minigame_current_side: str = "center"
        self.match_time_remaining: float = MATCH_DURATION
        self.app: Any = None
        self.timeout_requested: bool = False
        self.timeout_triggered: bool = False

    def create_task(self, coro):
        """Dispara uma corrotina assíncrona no ActionRunner da batalha."""
        return self._runner.start(coro)

    # ── Character Selection ───────────────────────────────────────────

    def select_player_robot(self, color: Any, name_code: str) -> None:
        """Initializes both the player robot and the IA opponent."""
        from game.champions import get_robot_class
        from settings import C_CYAN, C_ORANGE
        
        klass = get_robot_class(name_code)
        self.player_robot = klass(2, 4, color, name_code, is_player=True)

        ia_name = "PenLinux" if name_code == "DinoByte" else "DinoByte"
        ia_color = C_CYAN if ia_name == "PenLinux" else C_ORANGE
        
        ia_klass = get_robot_class(ia_name)
        self.ia_robot = ia_klass(2, 0, ia_color, ia_name, is_player=False)

        # Rotate models according to initial facing direction offsets
        self.player_robot.v_h = (180.0 - self.player_robot.model_offset) % 360.0
        self.player_robot.target_h = self.player_robot.v_h

        self.ia_robot.v_h = (0.0 - self.ia_robot.model_offset) % 360.0
        self.ia_robot.target_h = self.ia_robot.v_h

        # Tara o ângulo de debug: neste instante os dois robôs estão de
        # frente um para o outro, então o ângulo relativo começa em 0°.
        self.player_robot.tare_debug_angle()
        self.ia_robot.tare_debug_angle()

        self.state = "intro"
        self.log(f">> {name_code} vs {ia_name} (IA)")
        
        # Inicia a sequência paralela de áudio
        from game.scripts.background_audio import background_audio_sequence
        self._bg_runner.start(background_audio_sequence(self))

    # ── Player Actions ───────────────────────────────────────────────

    def execute_player_action(self, chosen_action: str, mini_game_result: str) -> None:
        """Starts player skill execution with calculated damage multipliers."""
        if getattr(self, "timeout_requested", False) or getattr(self, "timeout_triggered", False) or self.state == STATE_TIMEOUT:
            print("[BattleLogic] Ação do jogador bloqueada: Timeout / Great Intelligence iniciada.")
            return

        self.is_executing_action = True
        self.chosen_action       = chosen_action
        self.mini_game_result    = mini_game_result
        attacker = self.player_robot

        multiplier = self._multiplier_from_result(mini_game_result, attacker.name_code)

        if chosen_action.startswith("atk"):
            if attacker and hasattr(attacker, "record_attack_used"):
                attacker.record_attack_used(chosen_action)
            idx     = int(chosen_action[-1])
            ability = attacker.abilities[idx]

            final_damage = int(ability.damage * multiplier)

            self.log(f"{attacker.name_code}: {ability.name.upper()} -> {final_damage} dmg")
            
            import sys
            sys.stdout.write(f"CMD -> [{attacker.name_code.upper()}] EXECUTE_SKILL {ability.name.upper()} | BASE_DMG: {ability.damage}\n")
            sys.stdout.flush()

            # Armazena dano e habilidade para uso pelas funções DB_ATTACK / PL_ATTACK da DSL
            self._pending_player_damage  = final_damage
            self._pending_player_ability = ability

            # Garante que o boss não seja alterado se o atacante for PenLinux
            if self.ia_robot and not (attacker and hasattr(attacker, "name_code") and attacker.name_code.lower() == "penlinux"):
                angle = self.ia_robot.angle_to(attacker)
                self.ia_robot.v_h = (angle - self.ia_robot.model_offset) % 360.0
                self.ia_robot.target_h = self.ia_robot.v_h

            self._runner.clear()
            self._runner.start(
                ability.sequence_fn(attacker, self.ia_robot, ability, final_damage,
                                    self.camera, self)
            )

        elif chosen_action == "def":
            self.log(f"{attacker.name_code}: MODO DEFENSIVO")
            
            import sys
            sys.stdout.write(f"CMD -> [{attacker.name_code.upper()}] DEFEND\n")
            sys.stdout.flush()

            attacker.defend()
            self.is_executing_action  = False
            self.action_complete_time = time.time() + 0.4

    # ── IA/Boss Actions ───────────────────────────────────────────────

    def execute_ia_action(self) -> None:
        """Triggers boss/IA decision tree and sets up the active dodge minigame."""
        if getattr(self, "timeout_requested", False) or getattr(self, "timeout_triggered", False) or self.state == STATE_TIMEOUT:
            print("[BattleLogic] Ação da IA bloqueada: Timeout / Great Intelligence iniciada.")
            return

        self.ia_thinking_time    = 0
        attacker = self.ia_robot
        print(f"[IA] execute_ia_action chamado. attacker={attacker}")
        if not attacker:
            return



        from game.combat.boss_ai import choose_boss_action
        decision = choose_boss_action(attacker, self.player_robot, self)
        chosen = decision["attack"]

        if chosen.startswith("atk"):
            idx        = int(chosen[-1])
            ability    = attacker.abilities[idx]
            ia_result  = random.choice(["good", "good", "excellent"])
            multiplier = self._multiplier_from_result(ia_result, attacker.name_code)
            final_dmg  = int(ability.damage * multiplier)
            
            self.pending_ia_ability = ability
            self.pending_ia_damage = final_dmg
            self.minigame_start_time = time.time()
            
            self.dodge_variant = 0
            
            # Direct boss attack lane based on player's current X position
            if self.player_robot.v_tx <= 1.5:
                self.minigame_attack_dir = "left"
            elif self.player_robot.v_tx >= 2.5:
                self.minigame_attack_dir = "right"
            else:
                self.minigame_attack_dir = random.choice(["left", "right"])
                
            self.minigame_choice = None
            self.dodge_safe_time = 0.0
            self.state = STATE_MINIGAME
            self.log(f"{attacker.name_code} (IA): preparando {ability.name.upper()}!")
            
            import sys
            sys.stdout.write(f"CMD -> [{attacker.name_code.upper()}] PREPARE_SKILL {ability.name.upper()} | TARGET_DIR: {self.minigame_attack_dir.upper()}\n")
            sys.stdout.flush()
        else:
            self.log(f"{attacker.name_code} (IA): BLOQUEANDO...")
            
            import sys
            sys.stdout.write(f"CMD -> [{attacker.name_code.upper()}] IA_DEFEND\n")
            sys.stdout.flush()

            attacker.defend()
            self.is_executing_action  = False
            self.action_complete_time = time.time() + 0.8

    def resolve_minigame(self, success_or_dir: Any) -> None:
        """Determines success or failure of the dodge minigame and runs the boss attack."""
        if self.state != STATE_MINIGAME or self.is_executing_action:
            return

        correct = False
        if isinstance(success_or_dir, bool):
            correct = success_or_dir
            direction = "safe" if correct else "fail"
        else:
            direction = success_or_dir
            if self.minigame_attack_dir == "left" and direction == "right":
                correct = True
            elif self.minigame_attack_dir == "right" and direction == "left":
                correct = True
            elif self.minigame_attack_dir == "center" and direction == "down":
                correct = True

        self.minigame_choice = direction
        
        dodge_success = correct
        attacker = self.ia_robot
        ability = self.pending_ia_ability
        
        if dodge_success:
            self.log(f">> DESVIO PERFEITO PARA A {direction.upper()}!")
            final_dmg = 0
            self.mini_game_result = "dodge"
            
            from engine import app_core as app
            if app.game_instance:
                if hasattr(app.game_instance, "snd_dodge") and app.game_instance.snd_dodge:
                    app.game_instance.snd_dodge.play()
                if hasattr(app.game_instance, "hud") and app.game_instance.hud:
                    app.game_instance.hud.show_banner("DESVIO PERFEITO!", C_GREEN)
            
            if self.create_floating and self.player_robot:
                self.create_floating(self.player_robot.v_tx, self.player_robot.v_ty, "DESVIOU!", C_GREEN, 1.5)
        else:
            if direction == "none":
                self.log(f">> TEMPO ESGOTADO! NÃO DESVIOU!")
            else:
                self.log(f">> DESVIO INCORRETO PARA A {direction.upper()}!")
            final_dmg = self.pending_ia_damage
            self.mini_game_result = "poor"
            
            from engine import app_core as app
            if app.game_instance and hasattr(app.game_instance, "hud") and app.game_instance.hud:
                app.game_instance.hud.show_banner("FALHA NO DESVIO!", C_RED)

        self.state = STATE_IA_TURN
        self.is_executing_action = True

        self._runner.clear()
        self._runner.start(
            self.seq_ia_attack_with_dodge(attacker, self.player_robot, ability, final_dmg,
                                          self.camera, self, dodge_success, direction)
        )

    async def seq_ia_attack_with_dodge(self, attacker: Robot, target: Robot, ability: Any, final_damage: int, camera: Any, ctx: Any, dodge_success: bool, dodge_choice: str) -> None:
        """Executes the IA attack sequence after the dodge minigame.
        Physical movements of both robots are handled by boss_attack_sequence()."""
        if camera:
            camera.enter_minigame_mode()

        # ── Post-attack robot movement sequence (dano físico e movimento) ──
        await boss_attack_sequence(attacker, target, ability, final_damage, camera, ctx)

        # Transição de câmera após todos estáticos
        if camera:
            camera.enter_action_selection_mode()

    # ── Main Update ───────────────────────────────────────────────────

    def _robots_at_rest(self) -> bool:
        """Retorna True se nenhuma ação/minigame está em andamento e os robôs estão na posição inicial."""
        if self.is_executing_action:
            return False
        if self.action_complete_time > 0:
            return False
        if self.ia_thinking_time > 0:
            return False
        if self.state in (STATE_MINIGAME, STATE_ATTACK_MINIGAME):
            return False
        return True

    def update(self, dt: float = 1 / 60) -> None:
        """Main update tick called by Panda3D's task manager."""
        if self.player_robot:
            self.player_robot.update(dt)
        if self.ia_robot:
            self.ia_robot.update(dt)

        if not self._bg_runner.is_done:
            self._bg_runner.update()

        if not self._runner.is_done:
            self._runner.update()
            if self._runner.is_done and self.is_executing_action:
                self.is_executing_action  = False
                delay = 1.0
                self.action_complete_time = time.time() + delay
                if self.camera._mode in ("minigame", "tail_chase"):
                    self.camera.enter_battle_mode()

        if self.state in (STATE_PLAYER_TURN, STATE_IA_TURN, STATE_MINIGAME, STATE_ATTACK_MINIGAME):
            self._check_game_over()

        if self.state == STATE_MINIGAME:
            if hasattr(self, "minigame_start_time") and self.minigame_start_time > 0:
                elapsed = time.time() - self.minigame_start_time
                nx = getattr(self, "last_known_face_x", 0.5)
                attack_dir = getattr(self, "minigame_attack_dir", "left")

                is_safe = False
                if attack_dir == "left":
                    if nx is not None and nx > 0.75:
                        is_safe = True
                else:
                    if nx is not None and nx < 0.25:
                        is_safe = True

                if is_safe:
                    self.dodge_safe_time += dt
                else:
                    self.dodge_safe_time = 0.0

                if self.dodge_safe_time >= 0.75 and not self.is_executing_action:
                    # Successfully held for 0.75s! No extra delay here.
                    chosen_dir = "right" if attack_dir == "left" else "left"
                    self.resolve_minigame(chosen_dir)
                elif elapsed >= MINIGAME_DURATION and not self.is_executing_action:
                    # Timeout fail!
                    self.resolve_minigame("none")

        if self.state == STATE_IA_TURN:
            self._update_ia_turn(dt)

    def _update_ia_turn(self, dt: float) -> None:
        """Inner update tracking for IA turn timeouts."""
        if self.action_complete_time > 0 and time.time() > self.action_complete_time:
            print(f"[IA] action_complete_time expirou - verificando tempo restante ao final do round")
            self.action_complete_time = 0

            # ── Verificação de tempo ao final do round (quando robôs estão estáticos na base) ──
            if hasattr(self, "match_time_remaining") and self.match_time_remaining <= 20.0:
                print(f"[ROUND END] Tempo limite (margem 20s) expirou ({self.match_time_remaining:.1f}s). Encerrando combate na posição inicial!")
                self.match_time_remaining = 0.0
                self._trigger_timeout()
                return

            self.state = STATE_PLAYER_TURN
            
            import sys
            sys.stdout.write(f"\n>>> [AVISO] Movimentos da IA concluídos. Iniciando seu turno. <<<\n\n")
            sys.stdout.flush()

            if self.player_robot:
                self.player_robot.recover_turn()
            self.turn_number   += 1
            self.player_rounds += 1
            self.log(f"--- TURNO {self.turn_number} ---")
            if self.player_rounds >= MAX_ROUNDS:
                self._resolve_round_limit()

        elif (self.ia_thinking_time > 0
              and not self.is_executing_action
              and time.time() > self.ia_thinking_time):
            print(f"[IA] ia_thinking_time expirou - executando acao da IA")
            self.execute_ia_action()

    def check_player_action_completion(self) -> None:
        """Transitions state machine to IA turn once player actions complete."""
        if self.state != STATE_PLAYER_TURN:
            return
        if self.action_complete_time > 0 and time.time() > self.action_complete_time:
            self.action_complete_time = 0

            # ── Verificação de tempo ao final do minigame/ação do jogador (na posição inicial) ──
            if hasattr(self, "match_time_remaining") and self.match_time_remaining <= 20.0:
                print(f"[PLAYER TURN END] Tempo limite (margem 20s) expirou ({self.match_time_remaining:.1f}s). Encerrando combate na posição inicial!")
                self.match_time_remaining = 0.0
                self._trigger_timeout()
                return

            print(f"[TURNO] Player completou acao -> mudando para STATE_IA_TURN")
            self.state = STATE_IA_TURN
            
            import sys
            sys.stdout.write(f"\n>>> [AVISO] Movimentos do Jogador concluídos. Iniciando turno da IA. <<<\n\n")
            sys.stdout.flush()

            if self.ia_robot:
                self.ia_robot.recover_turn()
            self.ia_thinking_time = time.time() + IA_THINK_TIME

    # ── Reset ─────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Resets combat variables to starting selection screen values."""
        self.player_robot         = None
        self.ia_robot             = None
        self.turn_number          = 1
        self.player_rounds        = 0
        self.is_executing_action  = False
        self.action_complete_time = 0.0
        self.ia_thinking_time     = 0.0
        self.mini_game_result     = "good"
        self.chosen_action        = None
        self.state                = STATE_SELECT_ROBOT
        self.winner               = None
        self.minigame_start_time  = 0.0
        self.minigame_attack_dir  = "left"
        self.minigame_choice      = None
        self.minigame_current_side = "center"
        self.match_time_remaining  = MATCH_DURATION
        self._runner.clear()

    def request_timeout(self) -> None:
        """Sinaliza o fim do tempo de partida e solicita o início da sequência de Timeout / Great Intelligence.
        
        Nenhum novo minijogo ou ação poderá ser iniciado a partir deste momento.
        Se houver uma ação em andamento (is_executing_action ou tarefas no _runner), ela continuará
        até a sua conclusão completa (incluindo a resposta 'ok' da comunicação serial física do ESP32)
        antes de acionar a transição para a Great Intelligence.
        """
        if getattr(self, "timeout_triggered", False):
            return

        if not getattr(self, "timeout_requested", False):
            self.timeout_requested = True
            self.log(">> TEMPO LIMITE ALCANÇADO! OCULTANDO MINIJOGOS E AGUARDANDO CONCLUSÃO DAS AÇÕES EM ANDAMENTO...")

        # 1. Encerra e oculta imediatamente qualquer minijogo / HUD ativo
        app = getattr(self, "app", None)
        if app:
            app.active_attack_minigame = None
            app.selected_attack_action = None
            if hasattr(app, "qt_win") and app.qt_win:
                try:
                    app.qt_win.exit_minigame_hud_mode()
                    app.qt_win.exit_attack_minigame_hud_mode()
                    if hasattr(app.qt_win, "actions_overlay") and app.qt_win.actions_overlay:
                        app.qt_win.actions_overlay.hide()
                    if hasattr(app.qt_win, "minigame_instruction_overlay") and app.qt_win.minigame_instruction_overlay:
                        app.qt_win.minigame_instruction_overlay.hide()
                    if hasattr(app.qt_win, "dodge_minigame_overlay") and app.qt_win.dodge_minigame_overlay:
                        app.qt_win.dodge_minigame_overlay.hide()
                    if hasattr(app.qt_win, "attack_minigame_overlay") and app.qt_win.attack_minigame_overlay:
                        app.qt_win.attack_minigame_overlay.hide()
                except Exception as e:
                    print(f"[request_timeout] Erro ao ocultar minijogos: {e}")

        # 2. Se nenhuma ação estiver em andamento (is_executing_action == False e _runner.is_done), executa a transição imediata
        self._check_and_execute_timeout()

    def _check_and_execute_timeout(self) -> None:
        """Verifica se não há nenhuma ação em andamento para iniciar a transição da Great Intelligence."""
        if not getattr(self, "timeout_requested", False):
            return
        if getattr(self, "timeout_triggered", False):
            return

        # 1. Verifica se o robô do jogador ou o Boss estão executando uma ação ou sequência no ActionRunner
        is_busy = (
            self.is_executing_action
            or (hasattr(self, "_runner") and not self._runner.is_done)
            or self.action_complete_time > 0
        )
        
        # 1.5. STRICT REST CHECK: Verifica se os robôs estão se movendo ou fora da base
        if self.player_robot:
            if getattr(self.player_robot, "is_moving", False):
                is_busy = True
            if abs(self.player_robot.v_tx - self.player_robot.base_tx) > 0.01 or abs(self.player_robot.v_ty - self.player_robot.base_ty) > 0.01:
                is_busy = True
                
        if self.ia_robot:
            if getattr(self.ia_robot, "is_moving", False):
                is_busy = True
            if abs(self.ia_robot.v_tx - self.ia_robot.base_tx) > 0.01 or abs(self.ia_robot.v_ty - self.ia_robot.base_ty) > 0.01:
                is_busy = True

        # 2. Verifica se a comunicação serial do robô físico ainda está aguardando a confirmação 'ok' do ESP32
        from game.combat.serial_controller import get_serial_controller
        sc = get_serial_controller()
        if self.player_robot and not sc.is_ok_set(self.player_robot):
            is_busy = True
        if self.ia_robot and not sc.is_ok_set(self.ia_robot):
            is_busy = True

        if is_busy:
            # Ação / transmissão serial em andamento. Aguarda o término completo da ação!
            return

        # 3. Todas as ações e respostas seriais do ESP32 foram concluídas! Inicia a transição da Great Intelligence.
        self.timeout_triggered = True
        self._trigger_timeout()

    def _trigger_timeout(self) -> None:
        self.is_executing_action = False
        self.action_complete_time = 0.0
        self.ia_thinking_time = 0.0

        if self.player_robot:
            self.player_robot.v_tx = self.player_robot.base_tx
            self.player_robot.v_ty = self.player_robot.base_ty
            self.player_robot.target_tx = self.player_robot.base_tx
            self.player_robot.target_ty = self.player_robot.base_ty
            self.player_robot.v_h = (180.0 - self.player_robot.model_offset) % 360.0
            self.player_robot.target_h = self.player_robot.v_h

        if self.ia_robot:
            self.ia_robot.v_tx = self.ia_robot.base_tx
            self.ia_robot.v_ty = self.ia_robot.base_ty
            self.ia_robot.target_tx = self.ia_robot.base_tx
            self.ia_robot.target_ty = self.ia_robot.base_ty
            self.ia_robot.v_h = (0.0 - self.ia_robot.model_offset) % 360.0
            self.ia_robot.target_h = self.ia_robot.v_h

        # Robôs voltaram a ficar de frente um para o outro: tara de novo.
        if self.player_robot:
            self.player_robot.tare_debug_angle()
        if self.ia_robot:
            self.ia_robot.tare_debug_angle()

        self.state = STATE_TIMEOUT
        self.log(">> TEMPO LIMITE EXCEDIDO! INICIANDO SEQUÊNCIA DA GREAT INTELLIGENCE...")

    # ── Victory Checks ────────────────────────────────────────────────

    def _check_game_over(self) -> None:
        if self.player_robot and not self.player_robot.is_alive:
            self.winner = "ia"
            self.state  = STATE_GAME_OVER
            self.log(f">> {self.ia_robot.name_code} VENCEU!")
        elif self.ia_robot and not self.ia_robot.is_alive:
            self.winner = "player"
            self.state  = STATE_GAME_OVER
            self.log(f">> {self.player_robot.name_code} VENCEU!")

    def _resolve_round_limit(self) -> None:
        if not self.player_robot or not self.ia_robot:
            return
        self.log(f">> LIMITE DE {MAX_ROUNDS} ROUNDS!")
        if self.player_robot.hp > self.ia_robot.hp:
            self.winner = "player"
            self.log(f">> {self.player_robot.name_code} vence por HP!")
        elif self.ia_robot.hp > self.player_robot.hp:
            self.winner = "ia"
            self.log(f">> {self.ia_robot.name_code} (IA) vence por HP!")
        else:
            self.winner = "draw"
            self.log(">> EMPATE!")
        self.state = STATE_GAME_OVER

    def _multiplier_from_result(self, result: Any, name_code: str) -> float:
        rating = result
        if isinstance(result, dict):
            rating = result.get("rating", "good")

        if rating == "excellent":
            self.log("** PERFECT STRIKE! +35% DMG")
            return 1.35
        elif rating == "good":
            return 1.0
        elif rating == "poor":
            self.log("ATAQUE FRACO -35%")
            return 0.65
        else:
            return 0.0


# ════════════════════════════════════════════════════════════════════════════
# SEQUÊNCIAS STANDALONE (fora da classe BattleLogic)
# ════════════════════════════════════════════════════════════════════════════

async def boss_attack_sequence(attacker, target, ability, final_damage, camera, ctx):
    # ╔════════════════════════════════════════════════════════════════╗
    # ║   SEQUÊNCIA DE MOVIMENTO DO BOSS E PLAYER (DODGE MINIGAME)      ║
    # ╚════════════════════════════════════════════════════════════════╝
    from game.minigames.dodge import DodgeMinigame
    await DodgeMinigame.main_act(attacker, target, ability, final_damage, camera, ctx)

    return True
