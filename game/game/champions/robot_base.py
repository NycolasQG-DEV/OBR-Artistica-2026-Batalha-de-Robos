import asyncio

_DSL_TASKS = []

import math
import random
from dataclasses import dataclass, field
from typing import Callable, Optional
from game.combat.entities import Robot
from settings import (
    CM_PER_GRID_UNIT, ARENA_MIN_X, ARENA_MAX_X, ARENA_MIN_Y, ARENA_MAX_Y
)

@dataclass
class AbilityDef:
    name: str
    damage: int
    sequence_fn: Callable
    triggers_minigame: bool = False
    description: list = field(default_factory=list)

class RobotBase(Robot):
    ATTACKS = []
    ATTACK_META = {}

    # Velocidades físicas sincronizadas com o tempo real de execução dos motores do ESP32
    MOVE_SPEED_MAX_CM_S = 65.0   # 54 cm (1 tile) em ~0.83s de translação
    TURN_SPEED_MAX_DEG_S = 110.0 # 90 graus em ~0.82s de curva PID

    def __init__(self, tx: float, ty: float, color, name_code: str, is_player: bool):
        super().__init__(tx, ty, color, name_code, is_player)
        self.vx = 0.0      # Grid units per second
        self.omega = 0.0   # Degrees per second
        self.movement_stack = []
        self._unwinding_stack = False

        # Rastreio de ciclo sem repetição de minijogos/ataques
        self.used_attack_keys: list[str] = []
        self.last_used_attack_key: Optional[str] = None

        # Build abilities from metadata
        self.abilities = []
        for atk_name in self.ATTACKS:
            meta = self.ATTACK_META[atk_name]
            method = getattr(self, atk_name)
            
            # Closure to match (attacker, target, ability, final_damage, camera, ctx)
            def make_wrapper(m):
                return lambda attacker, target, ability, final_damage, camera, ctx: m(target, ability, final_damage, camera, ctx)
            
            self.abilities.append(AbilityDef(
                name=meta["name"],
                damage=meta["damage"],
                sequence_fn=make_wrapper(method),
                triggers_minigame=meta.get("triggers_minigame", False),
                description=meta.get("description", [])
            ))

    def get_next_available_attack(self) -> str:
        """Retorna uma chave de ataque ('atk0', 'atk1', ...) garantindo o ciclo sem repetição
        até que todos os minijogos/ataques deste robô tenham sido jogados."""
        num_attacks = len(self.ATTACKS) if hasattr(self, "ATTACKS") and self.ATTACKS else 3
        available = [f"atk{i}" for i in range(num_attacks)]

        if not hasattr(self, "used_attack_keys"):
            self.used_attack_keys = []
        if not hasattr(self, "last_used_attack_key"):
            self.last_used_attack_key = None

        remaining = [a for a in available if a not in self.used_attack_keys]
        if not remaining:
            self.used_attack_keys = []
            remaining = list(available)
            # Evita repetição imediata ao reiniciar o ciclo
            if self.last_used_attack_key and len(remaining) > 1 and self.last_used_attack_key in remaining:
                filtered = [a for a in remaining if a != self.last_used_attack_key]
                if filtered:
                    remaining = filtered

        chosen = random.choice(remaining)
        return chosen

    def record_attack_used(self, attack_key: str):
        """Registra um ataque/minijogo como jogado no ciclo atual deste robô."""
        if not hasattr(self, "used_attack_keys"):
            self.used_attack_keys = []

        if isinstance(attack_key, str) and attack_key.startswith("atk"):
            if attack_key not in self.used_attack_keys:
                self.used_attack_keys.append(attack_key)
            self.last_used_attack_key = attack_key

            num_attacks = len(self.ATTACKS) if hasattr(self, "ATTACKS") and self.ATTACKS else 3
            available = [f"atk{i}" for i in range(num_attacks)]
            if all(a in self.used_attack_keys for a in available):
                self.used_attack_keys = []

    # ── Continuous Position/Heading Integration ────────────────────────
    def update(self, dt: float = 1 / 60):
        # Update spin/flash ticks using base Robot class behavior
        super().update(dt)

        # Update angle
        if self.omega != 0.0:
            self.v_h = (self.v_h + self.omega * dt) % 360.0

        # Update position
        if self.vx != 0.0:
            move_angle = self.v_h + self.model_offset
            dcol = self.vx * math.sin(math.radians(move_angle)) * dt
            drow = self.vx * math.cos(math.radians(move_angle)) * dt
            self.v_tx = max(ARENA_MIN_X, min(ARENA_MAX_X, self.v_tx + dcol))
            self.v_ty = max(ARENA_MIN_Y, min(ARENA_MAX_Y, self.v_ty + drow))

    # ── Distance & Angle Helpers ───────────────────────────────────────
    def distance_to(self, other_robot) -> float:
        return self.distance_to_pos(other_robot.v_tx, other_robot.v_ty)

    def angle_to(self, other_robot) -> float:
        return self.angle_to_pos(other_robot.v_tx, other_robot.v_ty)

    def distance_to_pos(self, tx: float, ty: float) -> float:
        dx = tx - self.v_tx
        dy = ty - self.v_ty
        return math.sqrt(dx*dx + dy*dy) * CM_PER_GRID_UNIT

    def angle_to_pos(self, tx: float, ty: float) -> float:
        dx = tx - self.v_tx
        dy = ty - self.v_ty
        return math.degrees(math.atan2(dx, dy)) % 360.0

    def distance_to_home(self) -> float:
        return self.distance_to_pos(self.base_tx, self.base_ty)

    def angle_to_home(self) -> float:
        return self.angle_to_pos(self.base_tx, self.base_ty)

    def _is_realtime_combat(self) -> bool:
        """Determines if the game is in a real-time mini-game phase."""
        from engine import app_core as app
        from game.combat.battle_logic import STATE_MINIGAME, STATE_ATTACK_MINIGAME
        if app.game_instance and hasattr(app.game_instance, "battle") and app.game_instance.battle:
            b = app.game_instance.battle
            return b.state in (STATE_MINIGAME, STATE_ATTACK_MINIGAME)
        return False


    async def _run_motion(
        self,
        action: str,
        amount_serial: float,
        speed_serial: int,
        speed_rate: float,
        total_units: float,
        is_time_based: bool = False,
        is_turn: bool = False,
        target_h: Optional[float] = None,
    ) -> None:
        from game.combat.battle_logic import _tick
        from panda3d.core import ClockObject  # type: ignore
        from game.combat.serial_controller import get_serial_controller

        globalClock = ClockObject.getGlobalClock()
        sc = get_serial_controller()
        sc.write_command(self, action, amount_serial, speed_serial)

        self.is_moving = True
        remaining = total_units
        while remaining > 0.001 and getattr(self, "is_moving", True):
            await _tick()
            dt = globalClock.getDt()
            if dt <= 0.0:
                dt = 0.01667
            dt = min(dt, 0.05)
            if is_time_based:
                remaining -= dt
            else:
                step = speed_rate * dt
                if step >= remaining:
                    break
                else:
                    remaining -= step

        if is_turn:
            self.omega = 0.0
            if target_h is not None:
                self.v_h = target_h
        else:
            self.vx = 0.0

        # Aguarda a resposta 'ok' específica (TURN vs MOV) do robô apenas se for o Player (DinoByte) ou se a serial do Boss estiver habilitada
        if self.is_player or getattr(sc, "BOSS_SERIAL_ENABLED", False):
            await sc.wait_ok(self, expected_action=action)
        self.is_moving = False

    def stop_all_motion(self):
        """Cancela imediatamente qualquer física ou movimento pendente no robô."""
        self.is_moving = False
        self.vx = 0.0
        self.vy = 0.0
        self.omega = 0.0
        self._spin_active = False

    # ── Async APIs for movement ────────────────────────────────────────
    async def turn(self, degrees: float, speed: int = 255):
        if speed <= 0 or abs(degrees) < 0.1:
            return

        if not getattr(self, "_unwinding_stack", False):
            if not hasattr(self, "movement_stack"): self.movement_stack = []
            self.movement_stack.append({"type": "turn", "degrees": degrees, "speed": speed})

        target_h = (self.v_h + degrees) % 360.0
        direction = 1.0 if degrees >= 0 else -1.0
        v_angular = (speed / 255.0) * self.TURN_SPEED_MAX_DEG_S
        self.omega = direction * v_angular
        action = "TURN"
        speed_serial = 255

        await self._run_motion(
            action=action,
            amount_serial=degrees,  # Grau tarado / relativo (+ direita, - esquerda)
            speed_serial=speed_serial,
            speed_rate=v_angular,
            total_units=abs(degrees),
            is_turn=True,
            target_h=target_h,
        )

    async def move_cm(self, cm: float, speed: int = 255):
        if speed <= 0 or abs(cm) < 0.1:
            return

        is_minigame = self._is_realtime_combat()
        if not is_minigame:
            from engine import app_core as app
            if app.game_instance and hasattr(app.game_instance, "battle") and app.game_instance.battle:
                other_robot = app.game_instance.battle.ia_robot if self.is_player else app.game_instance.battle.player_robot
                if other_robot and cm > 0:
                    curr_dist = self.distance_to(other_robot)
                    move_world_angle = (self.v_h + self.model_offset) % 360.0
                    angle_to_other = self.angle_to_pos(other_robot.v_tx, other_robot.v_ty)
                    from engine.render.geometry import normalize_angle_deg
                    dh = abs(normalize_angle_deg(angle_to_other - move_world_angle))
                    if dh < 45.0:
                        max_allowed_cm = max(0.0, curr_dist - 54.0)
                        if cm > max_allowed_cm:
                            cm = max_allowed_cm


        direction = 1.0 if cm >= 0 else -1.0
        v_linear = (speed / 255.0) * self.MOVE_SPEED_MAX_CM_S
        v_grid_s = v_linear / CM_PER_GRID_UNIT
        self.vx = direction * v_grid_s

        action = "W" if cm >= 0 else "S"
        speed_serial = max(200, min(255, speed))

        await self._run_motion(
            action=action,
            amount_serial=abs(cm),
            speed_serial=speed_serial,
            speed_rate=v_grid_s,
            total_units=abs(cm) / CM_PER_GRID_UNIT,
        )


    async def move_time(self, seconds: float, speed: int = 255):
        if seconds <= 0 or speed == 0:
            return
        v_linear = (speed / 255.0) * self.MOVE_SPEED_MAX_CM_S
        v_grid_s = v_linear / CM_PER_GRID_UNIT
        self.vx = v_grid_s
        dist_cm = seconds * v_linear
        action = "F"
        speed_serial = max(200, min(255, speed))

        await self._run_motion(
            action=action,
            amount_serial=dist_cm,
            speed_serial=speed_serial,
            speed_rate=v_grid_s,
            total_units=seconds,
            is_time_based=True,
        )

    async def move_dsl(self, direction: str, tiles: float, speed: int = 180):
        """Move o robô usando blocos DSL onde cada tile equivale exatamente a 800ms de andar reto."""
        if speed <= 0 or abs(tiles) < 0.01:
            return

        d_upper = str(direction).strip().upper()
        if not getattr(self, "_unwinding_stack", False):
            if not hasattr(self, "movement_stack"): self.movement_stack = []
            self.movement_stack.append({"type": "move_dsl", "direction": d_upper, "tiles": tiles, "speed": speed})

        if d_upper in ("TRAS", "TRÁS", "S"): action = "S"
        elif d_upper in ("ESQUERDA", "A"): action = "A"
        elif d_upper in ("DIREITA", "D"): action = "D"
        else: action = "W"

        duration_s = abs(tiles) * 0.950  # 950ms por tile (sincronizado com os 800ms + rampas do ESP32)
        v_grid_s = 1.0 / 0.950           # Velocidade Panda3D (1 tile a cada 0.95s)
        self.vx = (1.0 if action == "W" else -1.0) * v_grid_s

        await self._run_motion(
            action=action,
            amount_serial=abs(tiles),    # Envia o número de tiles (convertido em tiles * 800ms no serial_controller)
            speed_serial=speed,
            speed_rate=v_grid_s,
            total_units=duration_s,
            is_time_based=True,
        )

    async def return_to_initial_pose(self, ctx=None):
        """
        Calcula o caminho mais curto usando a menor quantidade de comandos DSL possíveis
        (move_dsl Y, move_dsl X e turn) com await e WAIT_MOV para retornar à posição inicial.
        """
        from game.champions.robot_base import WAIT_MOV
        from game.combat.serial_controller import get_serial_controller
        from engine.render.geometry import normalize_angle_deg
        sc = get_serial_controller()

        self._unwinding_stack = True
        try:
            # 1. Aguarda conclusão de qualquer passo em andamento
            await WAIT_MOV()

            initial_tx = getattr(self, "base_tx", round(self.v_tx))
            initial_ty = getattr(self, "base_ty", round(self.v_ty))
            initial_h = getattr(self, "base_h", 180.0 if self.is_player else 0.0)

            # 2. Deslocamento no eixo Y (Frente / Trás) em tiles
            dy = initial_ty - self.v_ty
            if abs(dy) >= 0.3:
                tiles_y = round(abs(dy))
                if tiles_y >= 1:
                    if self.is_player:
                        dir_y = "TRAS" if dy > 0 else "FRENTE"
                    else:
                        dir_y = "FRENTE" if dy > 0 else "TRAS"
                    print(f"[{self.name_code}] Retornando Y ({dy:.2f}) via DSL: move_dsl({dir_y}, {tiles_y})...")
                    await self.move_dsl(dir_y, tiles_y, speed=180)
                    await WAIT_MOV()

            # 3. Deslocamento no eixo X (Esquerda / Direita) em tiles
            dx = initial_tx - self.v_tx
            if abs(dx) >= 0.3:
                tiles_x = round(abs(dx))
                if tiles_x >= 1:
                    if self.is_player:
                        dir_x = "ESQUERDA" if dx < 0 else "DIREITA"
                    else:
                        dir_x = "DIREITA" if dx < 0 else "ESQUERDA"
                    print(f"[{self.name_code}] Retornando X ({dx:.2f}) via DSL: move_dsl({dir_x}, {tiles_x})...")
                    await self.move_dsl(dir_x, tiles_x, speed=180)
                    await WAIT_MOV()

            # 4. Ajuste de orientação final para encarar o rumo inicial (se necessário)
            dh = normalize_angle_deg(initial_h - self.v_h)
            dh = round(dh / 90.0) * 90.0
            if abs(dh) >= 15.0:
                print(f"[{self.name_code}] Re-alinhando orientação para {initial_h}° via turn({dh}°)...")
                await self.turn(dh, speed=180)
                await WAIT_MOV()

            # 5. Finaliza e garante alinhamento estático
            if hasattr(self, "stop_all_motion"):
                self.stop_all_motion()

            self.v_tx = float(initial_tx)
            self.v_ty = float(initial_ty)
            self.target_tx = float(initial_tx)
            self.target_ty = float(initial_ty)
            self.v_h = float(initial_h)
            self.target_h = float(initial_h)

            if sc:
                sc.send_command_realtime(self, "STOP", 0)

            if hasattr(self, "movement_stack") and self.movement_stack is not None:
                self.movement_stack.clear()
        finally:
            self._unwinding_stack = False

    async def move_to_grid(self, col: float, row: float, tolerance: float = 0.045):
        from engine.render.geometry import normalize_angle_deg
        col = max(ARENA_MIN_X, min(ARENA_MAX_X, col))
        row = max(ARENA_MIN_Y, min(ARENA_MAX_Y, row))
        dx = col - self.v_tx
        dy = row - self.v_ty
        if math.sqrt(dx*dx + dy*dy) < 0.1:
            return
        
        angle = self.angle_to_pos(col, row)
        visual_angle = (angle - self.model_offset) % 360.0
        dh = normalize_angle_deg(visual_angle - self.v_h)
        await self.turn(dh)
        
        dist_cm = self.distance_to_pos(col, row)
        await self.move_cm(dist_cm)



    async def rotate_to_heading(self, heading_deg: float, speed: int = 255):
        base = round(self.v_h / 90.0) * 90.0 % 360.0
        target = round(heading_deg / 90.0) * 90.0 % 360.0
        dh = target - base
        while dh > 180.0: dh -= 360.0
        while dh < -180.0: dh += 360.0
        dh = round(dh / 90.0) * 90.0
        if abs(dh) > 0.1:
            await self.turn(dh, speed=speed)



    async def spin_and_wait(self, duration: float = 3.0, loops: int = 3, speed: int = 255):
        from game.combat.battle_logic import _tick
        self.start_spin(duration=duration, loops=loops)
        await self.turn(360.0 * loops, speed=speed)
        while self._spin_active:
            await _tick()

    async def receive_damage(self, attacker, final_damage: int, camera, ctx):
        from game.combat.entities import apply_hit_effects
        from game.combat.serial_controller import get_serial_controller
        from game.combat.battle_logic import _tick
        apply_hit_effects(attacker, self, final_damage, camera, ctx)

        if final_damage > 0:
            sc = get_serial_controller()
            sc.write_command(self, "SEQ_DAMAGE", 0, 0)

            from panda3d.core import ClockObject  # type: ignore
            globalClock = ClockObject.getGlobalClock()

            orig_h = self.v_h
            orig_tx = self.v_tx
            orig_ty = self.v_ty
            duration = 0.6
            elapsed = 0.0

            # 15cm knockback backwards based on current heading
            from settings import CM_PER_GRID_UNIT
            dx_knockback = (-15.0 / CM_PER_GRID_UNIT) * math.sin(math.radians(orig_h))
            dy_knockback = (-15.0 / CM_PER_GRID_UNIT) * -math.cos(math.radians(orig_h))

            self.wobble_active = True
            try:
                while elapsed < duration:
                    await _tick()
                    dt = globalClock.getDt()
                    if dt <= 0.0:
                        dt = 0.01667
                    elapsed += dt
                    t_ratio = min(1.0, elapsed / duration)
                    
                    # Rotação do wobble
                    angle_offset = -20.0 * math.cos(4.0 * math.pi * (elapsed / duration)) * (1.0 - t_ratio)
                    self.v_h = (orig_h + angle_offset) % 360.0
                    
                    # Movimento de recuo (knockback) que vai e volta suavemente (onda senoide)
                    knockback_factor = math.sin(math.pi * t_ratio)
                    self.v_tx = orig_tx + dx_knockback * knockback_factor
                    self.v_ty = orig_ty + dy_knockback * knockback_factor

            finally:
                self.v_h = orig_h
                self.v_tx = orig_tx
                self.v_ty = orig_ty
                self.wobble_active = False

            await sc.wait_ok(self, expected_action="SEQ_DAMAGE")

    async def _execute_boss_vector_charge(self, target, ability, final_damage, camera, ctx, spin_duration=1.0, shake_level=None):
        """Boss attack stub — sequência de movimento programável via boss_attack_sequence()."""
        pass



# ══════════════════════════════════════════════════════════════════════════
# DSL DE MOVIMENTOS — Funções padronizadas para sequências de combate
# ══════════════════════════════════════════════════════════════════════════
# Como usar (dentro de qualquer async def player_attack_sequence_* ou
#             boss_attack_sequence):
#
#   await DB_MOV(ctx, "FRENTE", 3)   → DinoByte anda 3 tiles para frente
#   await PL_MOV(ctx, "TRAS", 2)     → PenLinux anda 2 tiles para trás
#   await DB_TURN(ctx, "DIREITA")    → DinoByte vira 90° à direita
#   await PL_TURN(ctx, "FULL")       → PenLinux gira 360° completo
#   await WAIT_MOV()                 → aguarda o último movimento terminar
#   await DELAY(1.5)                 → pausa de 1.5 segundos
#   await DB_ATTACK(ctx)             → aplica dano do minigame + animação leve
#   await PL_ATTACK(ctx)             → idem para PenLinux
#   choice = GET_CHOICE(ctx)         → retorna "DIREITA" ou "ESQUERDA"
#   await PLAY_SOUND(ctx, "path.wav") → toca um efeito sonoro assincronamente
# ══════════════════════════════════════════════════════════════════════════

def _get_robots_from_ctx(ctx):
    """Retorna (db_robot, pl_robot) a partir do contexto de batalha."""
    from engine import app_core as app
    if app.game_instance and app.game_instance.battle:
        b = app.game_instance.battle
        pr = b.player_robot
        ia = b.ia_robot
        if pr and ia:
            # DinoByte é sempre identificado pelo name_code
            if hasattr(pr, 'name_code') and 'DinoByte' in pr.name_code:
                return pr, ia
            else:
                return ia, pr
    return None, None


def _heading_for_direction(robot, direction: str) -> float:
    """Calcula o heading absoluto para uma direção relativa ao robô.
    
    Arredonda a base para o ângulo cardinal mais próximo (0°, 90°, 180°, 270°)
    para impedir qualquer acúmulo de desalinhamento de rotação.
    """
    base = round(robot.v_h / 90.0) * 90.0 % 360.0
    d = str(direction).strip().upper()
    if d == "FRENTE":
        return base
    elif d == "DIREITA":
        return (base + 90.0) % 360.0
    elif d == "ESQUERDA":
        return (base - 90.0) % 360.0
    elif d in ("TRAS", "TRÁS"):
        return (base + 180.0) % 360.0
    elif d == "FULL":
        return base
    return base


async def DB_MOV(ctx, direction: str = "FRENTE", tiles: float = 1.0, *args, **kwargs) -> bool:
    """Move o DinoByte N tiles na direção especificada (FRENTE ou TRAS).
    Não bloqueia a execução. Use WAIT_MOV() para aguardar."""
    db, _ = _get_robots_from_ctx(ctx)
    if db is None:
        return True
    
    speed = kwargs.get("speed", 180)
    for arg in args:
        if isinstance(arg, (int, float)):
            tiles = float(arg)
            
    task = asyncio.create_task(db.move_dsl(direction, tiles, speed=speed))
    _DSL_TASKS.append(task)
    return True


async def PL_MOV(ctx, direction: str = "FRENTE", tiles: float = 1.0, *args, **kwargs) -> bool:
    """Move o PenLinux N tiles na direção especificada (FRENTE ou TRAS).
    Não bloqueia a execução. Use WAIT_MOV() para aguardar."""
    _, pl = _get_robots_from_ctx(ctx)
    if pl is None:
        return True

    speed = kwargs.get("speed", 180)
    for arg in args:
        if isinstance(arg, (int, float)):
            tiles = float(arg)

    task = asyncio.create_task(pl.move_dsl(direction, tiles, speed=speed))
    _DSL_TASKS.append(task)
    return True


async def DB_TURN(ctx, direction: str = "FULL", *args, **kwargs) -> bool:
    """Vira o DinoByte para uma direção relativa à sua orientação atual.
    FULL = giro 360° completo. Não bloqueia a execução. Use WAIT_MOV() para aguardar."""
    db, _ = _get_robots_from_ctx(ctx)
    if db is None:
        return True
    d = str(direction).strip().upper()
    speed = kwargs.get("speed", 255)
    
    if d == "FULL":
        coro = db.spin_and_wait(duration=1.2, loops=1, speed=speed)
    else:
        rel_deg = 90.0 if d == "DIREITA" else (-90.0 if d == "ESQUERDA" else (180.0 if d in ("TRAS", "TRÁS") else 0.0))
        target_h = (db.v_h + rel_deg) % 360.0
        coro = db.rotate_to_heading(target_h, speed=speed)
        
    task = asyncio.create_task(coro)
    _DSL_TASKS.append(task)
    return True


async def PL_TURN(ctx, direction: str = "FULL", *args, **kwargs) -> bool:
    """Vira o PenLinux para uma direção relativa à sua orientação atual.
    Não bloqueia a execução. Use WAIT_MOV() para aguardar."""
    _, pl = _get_robots_from_ctx(ctx)
    if pl is None:
        return True
    d = str(direction).strip().upper()
    
    if d == "FULL":
        coro = pl.spin_and_wait(duration=1.2, loops=1)
    else:
        rel_deg = 90.0 if d == "DIREITA" else (-90.0 if d == "ESQUERDA" else (180.0 if d in ("TRAS", "TRÁS") else 0.0))
        target_h = (pl.v_h + rel_deg) % 360.0
        coro = pl.rotate_to_heading(target_h)
        
    task = asyncio.create_task(coro)
    _DSL_TASKS.append(task)
    return True


class _EnvoltoContextManager:
    """Gerenciador de contexto para o bloco ENVOLTO.
    Permite a sintaxe:
        async with ENVOLTO():
            await DB_TURN(ctx, "DIREITA")
            await PL_TURN(ctx, "ESQUERDA")
        await WAIT_MOV()
    """
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await WAIT_MOV()


async def ENVOLTO(*args, **kwargs):
    """Envólucro de descomplexação para agrupar múltiplos comandos de movimento/giro.
    Garante que todos os comandos dentro dele sejam 100% concluídos antes de prosseguir.
    
    Exemplos de uso:
      await ENVOLTO(player_turn(ctx, p_dir), boss_turn(ctx, b_dir))
      await WAIT_MOV()
      
      ou:
      
      async with ENVOLTO():
          await DB_TURN(ctx, "DIREITA")
          await PL_TURN(ctx, "ESQUERDA")
      await WAIT_MOV()
    """
    global _DSL_TASKS

    if args:
        tasks_to_wait = []
        for arg in args:
            if asyncio.iscoroutine(arg) or isinstance(arg, asyncio.Task):
                tasks_to_wait.append(arg)

        if _DSL_TASKS:
            tasks_to_wait.extend(_DSL_TASKS[:])
            _DSL_TASKS.clear()

        if tasks_to_wait:
            await asyncio.gather(*tasks_to_wait, return_exceptions=True)

        await WAIT_MOV()
        return True

    return _EnvoltoContextManager()


async def WAIT_MOV(*args, **kwargs) -> bool:
    """Aguarda o fim de todos os movimentos e a resposta 'ok' dos robôs antes de liberar a próxima ação."""
    global _DSL_TASKS
    from game.combat.serial_controller import get_serial_controller
    sc = get_serial_controller()

    if _DSL_TASKS:
        tasks = _DSL_TASKS[:]
        _DSL_TASKS.clear()
        await asyncio.gather(*tasks, return_exceptions=True)

    from engine import app_core as app
    if app.game_instance and hasattr(app.game_instance, "battle") and app.game_instance.battle:
        b = app.game_instance.battle
        if b.player_robot:
            await sc.wait_ok(b.player_robot)
        if b.ia_robot and getattr(b.ia_robot, "is_moving", False):
            await sc.wait_ok(b.ia_robot)

    return True


async def DELAY(seconds: float = 0.5, *args, **kwargs) -> bool:
    """Pausa a sequência por N segundos sem mover nada."""
    from game.combat.battle_logic import wait_seconds
    for arg in args:
        if isinstance(arg, (int, float)):
            seconds = float(arg)
    await wait_seconds(seconds)
    return True


async def PLAY_SOUND(ctx, sound_path: str, volume: float = 1.0, *args, **kwargs) -> bool:
    """Carrega e toca um efeito sonoro instantaneamente sem bloquear a sequência."""
    from engine import app_core as app
    if not (app.game_instance and hasattr(app.game_instance, "loader")):
        return True
    try:
        sfx = app.game_instance.loader.loadSfx(sound_path)
        if sfx:
            sfx.setVolume(volume)
            sfx.play()
    except Exception as e:
        print(f"[PLAY_SOUND] Erro ao reproduzir som {sound_path}: {e}")
    return True


async def _db_attack_logic(ctx, *args, **kwargs) -> bool:
    """Aplica o dano calculado pelo minigame ao alvo do DinoByte.
    Executa uma animação leve de balanço (alguns graus para cada lado)
    antes de aplicar o dano — sem mover fisicamente o robô."""
    from engine import app_core as app
    from game.combat.battle_logic import wait_seconds
    from settings import SHAKE_MEDIUM

    if not (app.game_instance and app.game_instance.battle):
        return True
    b = app.game_instance.battle
    
    db, pl = _get_robots_from_ctx(ctx)
    attacker = db
    target = pl
    if not attacker or not target:
        return True

    # Dano: tenta ler dos args ou kwargs se for passado, senão pega _pending_player_damage
    final_damage = getattr(b, '_pending_player_damage', 0)
    for arg in args:
        if isinstance(arg, int) and not isinstance(arg, bool):
            final_damage = arg
    if "damage" in kwargs and isinstance(kwargs["damage"], int):
        final_damage = kwargs["damage"]

    camera = b.camera if hasattr(b, 'camera') else None

    if final_damage > 0:
        # Animação de balanço suave e leve no ALVO (sem translação física)
        orig_h = target.v_h
        steps = 15
        for i in range(steps):
            frac = i / float(steps - 1)
            # Seno para ir e voltar suavemente, amplitude menor (5 graus)
            deg = math.sin(frac * 4 * math.pi) * 5.0
            target.v_h = (orig_h + deg) % 360.0
            target.target_h = target.v_h
            await wait_seconds(0.03)
        target.v_h = orig_h
        target.target_h = orig_h

        if camera:
            camera.add_shake(SHAKE_MEDIUM)
    await target.receive_damage(attacker, final_damage, camera if final_damage > 0 else None, ctx)
    return True




async def DB_ATTACK(ctx, *args, **kwargs) -> bool:
    """Inicia o ataque do DinoByte sem bloquear. Use WAIT_MOV() para aguardar."""
    task = asyncio.create_task(_db_attack_logic(ctx, *args, **kwargs))
    _DSL_TASKS.append(task)
    return True

async def _pl_attack_logic(ctx, *args, **kwargs) -> bool:
    """Aplica o dano calculado pelo minigame ao alvo do PenLinux.
    Animação leve de balanço antes do dano — sem translação física."""
    from engine import app_core as app
    from game.combat.battle_logic import wait_seconds
    from settings import SHAKE_MEDIUM

    if not (app.game_instance and app.game_instance.battle):
        return True
    b = app.game_instance.battle
    
    db, pl = _get_robots_from_ctx(ctx)
    attacker = pl
    target = db
    if not attacker or not target:
        return True

    # Dano: tenta ler dos args ou kwargs se for passado
    final_damage = getattr(b, '_pending_player_damage', 0)
    for arg in args:
        if isinstance(arg, int) and not isinstance(arg, bool):
            final_damage = arg
    if "damage" in kwargs and isinstance(kwargs["damage"], int):
        final_damage = kwargs["damage"]

    camera = b.camera if hasattr(b, 'camera') else None

    if final_damage > 0:
        # Animação de balanço suave e leve no ALVO
        orig_h = target.v_h
        steps = 15
        for i in range(steps):
            frac = i / float(steps - 1)
            deg = math.sin(frac * 4 * math.pi) * 5.0
            target.v_h = (orig_h + deg) % 360.0
            target.target_h = target.v_h
            await wait_seconds(0.03)
        target.v_h = orig_h
        target.target_h = orig_h

        if camera:
            camera.add_shake(SHAKE_MEDIUM)
            
    await target.receive_damage(attacker, final_damage, camera if final_damage > 0 else None, ctx)
    return True




async def PL_ATTACK(ctx, *args, **kwargs) -> bool:
    """Inicia o ataque do PenLinux sem bloquear. Use WAIT_MOV() para aguardar."""
    task = asyncio.create_task(_pl_attack_logic(ctx, *args, **kwargs))
    _DSL_TASKS.append(task)
    return True

def GET_CHOICE(ctx, *args, **kwargs) -> str:
    """Retorna a escolha de desvio do jogador: 'DIREITA' ou 'ESQUERDA'.
    Deve ser chamado dentro de boss_attack_sequence após o minigame de desvio."""
    from engine import app_core as app
    if app.game_instance and app.game_instance.battle:
        choice = getattr(app.game_instance.battle, 'minigame_choice', None)
        if choice in ('left', 'esquerda'):
            return 'ESQUERDA'
        if choice in ('right', 'direita'):
            return 'DIREITA'
    return 'DIREITA'  # fallback seguro
