# combat/entities.py — Robot (sem pygame)
import random
import math
import time

from settings import (
    MAX_HP, DEFENSE_REDUCTION,
    ROBOT_MOVE_SPEED, SHAKE_MEDIUM, SHAKE_LIGHT,
    C_RED, C_ORANGE, C_GREEN,
    PLAYER_BASE_COORDS, BOSS_BASE_COORDS,
)


class Robot:
    """
    Dados lógicos de um robô.
    A renderização 3D (NodePath do cubo) fica em arena3d.py.
    """

    def __init__(self, tx: float, ty: float, color, name_code: str, is_player: bool):
        if is_player:
            bx, by = PLAYER_BASE_COORDS
        else:
            bx, by = BOSS_BASE_COORDS

        self.base_tx = float(bx)
        self.base_ty = float(by)
        self.v_tx    = float(bx)
        self.v_ty    = float(by)
        self.target_tx = float(bx)
        self.target_ty = float(by)

        self.name_code  = name_code
        self.is_player  = is_player
        self.base_color = color

        self.hp     = float(MAX_HP)

        self.movement_speed = getattr(self, "MOVE_SPEED", ROBOT_MOVE_SPEED)
        self.is_moving      = False

        self.is_defending  = False
        self.flash_timer   = 0.0

        # Rotação lógica do robô (180 = olhando para o sul, em direção à câmera)
        self.v_h = 180.0
        self.target_h = 180.0

        # ── Ângulo de debug (relativo / "tarado") ───────────────────────
        # Referência zerada no momento em que os robôs se posicionam
        # de frente um para o outro (ver BattleLogic). A tela de debug
        # (Ctrl+D / F12) usa isso para mostrar o giro acumulado a partir
        # do início, independente do offset de 180° do modelo do PenLinux.
        self.debug_reference_h = self.v_h

        self._bob_offset = random.uniform(0, math.tau)
        self._spawn_time = time.time()

        # Animação de giro (usado pelas sequences)
        self._spin_active         = False
        self._spin_timer          = 0.0
        self._spin_frames         = []
        self._spin_frame_duration = 0.0
        self._spin_frame_idx      = 0

        self.abilities = []
        self._cached_model_offset: float | None = None

    # ── Propriedades ──────────────────────────────────────────────────

    @property
    def model_offset(self) -> float:
        if self._cached_model_offset is not None:
            return self._cached_model_offset

        import os
        import json
        robot_name = self.name_code.lower()
        if self.is_player:
            config_path = f"assets/models/{robot_name}.json"
        else:
            config_path = f"assets/models/{robot_name}_boss.json"
            if not os.path.exists(config_path):
                config_path = f"assets/models/{robot_name}.json"
            if not os.path.exists(config_path):
                config_path = "assets/models/boss.json"
        
        offset = 180.0 if self.name_code == "PenLinux" else 0.0
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    model_config = json.load(f)
                    rotation = model_config.get("rotation", [0.0, 0.0, 0.0])
                    offset = float(rotation[0])
            except Exception:
                pass

        self._cached_model_offset = offset
        return offset

    @property
    def heading_to_boss(self) -> float:
        # Calculate angle to boss base coords at (2.0, 0.0)
        dx = 2.0 - self.v_tx
        dy = 0.0 - self.v_ty
        desired_world_h = math.degrees(math.atan2(dx, dy)) % 360.0
        return (desired_world_h - self.model_offset) % 360.0


    @property
    def heading_to_camera(self) -> float:
        if self.is_player:
            return self.heading_to_boss
        else:
            return (0.0 - self.model_offset) % 360.0


    def tare_debug_angle(self):
        """Zera ('tara') a referência do ângulo de debug na posição/heading atual.

        Chamado sempre que os robôs são recolocados de frente um para o
        outro (início de partida, timeout, etc). A partir daqui o ângulo
        de debug mostra apenas o quanto o robô girou desde esse instante,
        em vez do valor bruto de v_h (que já embute o offset visual do
        modelo, ex: os 180° do PenLinux).
        """
        self.debug_reference_h = self.v_h

    @property
    def debug_relative_angle(self) -> float:
        """Ângulo de giro relativo ao 'zero' tarado, na faixa [-180, 180]."""
        from engine.render.geometry import normalize_angle_deg
        return normalize_angle_deg(self.v_h - self.debug_reference_h)

    @property
    def is_alive(self) -> bool:
        return self.hp > 0

    # ── Animação de giro (mantida para compatibilidade com sequences) ──

    def start_spin(self, duration: float = 3.0, loops: int = 3):
        frames = [0, 1, 2, 3] * loops + [0]
        self._spin_frames         = frames
        self._spin_frame_idx      = 0
        
        # Respect physical maximum angular velocity limit
        total_degrees = 360.0 * loops
        max_turn_speed = getattr(self, "TURN_SPEED_MAX_DEG_S", 360.0)
        min_duration = total_degrees / max_turn_speed
        actual_duration = max(duration, min_duration)

        self._spin_frame_duration = actual_duration / (len(frames) - 1)
        self._spin_timer          = 0.0
        self._spin_active         = True

    def _update_spin(self, dt: float):
        if not self._spin_active:
            return
        self._spin_timer += dt
        idx = min(
            int(self._spin_timer / self._spin_frame_duration),
            len(self._spin_frames) - 1,
        )
        self._spin_frame_idx = idx
        if self._spin_timer >= self._spin_frame_duration * (len(self._spin_frames) - 1):
            self._spin_active = False
            self._spin_timer  = 0.0

    # ── Métodos de combate ────────────────────────────────────────────

    def defend(self):
        self.is_defending = True

    def recover_turn(self):
        self.is_defending = False

    def take_damage(self, damage: int, camera,
                    create_floating=None, create_particles=None,
                    shake: int = SHAKE_MEDIUM):
        if self.is_defending:
            damage = int(damage * DEFENSE_REDUCTION)
        damage = max(1, int(damage))
        self.hp = max(0.0, self.hp - damage)
        if camera:
            camera.add_shake(shake)
        self.flash_timer = 0.25  # segundos

        from engine import app_core as app
        if app.game_instance and hasattr(app.game_instance, "snd_hit") and app.game_instance.snd_hit:
            app.game_instance.snd_hit.play()

        if create_floating:
            create_floating(self.v_tx, self.v_ty, f"-{damage}", C_RED, size=1.2)
        if create_particles:
            create_particles(self.v_tx, self.v_ty, C_RED, count=12)

    # ── Update por frame ──────────────────────────────────────────────

    def update(self, dt: float = 1 / 60):
        if self._spin_active:
            self._update_spin(dt)

        if self.flash_timer > 0:
            self.flash_timer = max(0.0, self.flash_timer - dt)


def apply_hit_effects(attacker, target, final_damage: int, camera, ctx):
    from engine import app_core as app
    if camera is None and app.game_instance and hasattr(app.game_instance, "battle") and app.game_instance.battle:
        camera = getattr(app.game_instance.battle, "camera", None)

    if final_damage == 0:
        if ctx and hasattr(ctx, "create_floating"):
            ctx.create_floating(target.v_tx, target.v_ty, "MISS!", (0.5, 0.5, 0.5, 1))
        return

    from settings import SHAKE_MEDIUM
    target.take_damage(
        final_damage, camera,
        create_floating=ctx.create_floating if ctx else None,
        create_particles=ctx.create_particles if ctx else None,
        shake=SHAKE_MEDIUM,
    )
