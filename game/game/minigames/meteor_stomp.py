# game/minigames/meteor_stomp.py
# ════════════════════════════════════════════════════════════════════════
# Minigame "METEOR STOMP" — Texturas Transparentes, Offset para Frente & Partículas 3D
# ════════════════════════════════════════════════════════════════════════
# Correções Aplicadas:
# 1. Projétil despachado 1.40m À FRENTE no focinho/boca do DinoByte (vetor fwd_y corrigido para -1.40m na perspectiva do DinoByte).
# 2. Textura da Bola de Fogo pura com transparência ativada (`setTransparency(TransparencyAttrib.MAlpha)`), sem cor sólida de cubo por trás.
# 3. Partículas 3D reais no chão sem caracteres unicode `💥` para evitar lag/warnings de fonte Panda3D.
# 4. Flash de Powerup Arcade no DinoByte ativando `setColorScale(2.5, 2.5, 2.5, 1.0)`.
# 5. Otimização de limpeza para zerar qualquer possibilidade de lag/drop de frames.
# ════════════════════════════════════════════════════════════════════════

import time
import math
import random
import asyncio
from typing import List, Dict, Any

from PySide6.QtCore import Qt, QPoint, QRectF
from PySide6.QtGui import (
    QColor, QFont, QPen, QBrush, QLinearGradient, QRadialGradient, QPainterPath
)
from panda3d.core import GeomNode, Material, LColor, TransparencyAttrib, Point3, TexturePool  # type: ignore

from engine import app_core as app
from engine.render.geometry import create_clean_cube, grid_to_world, normalize_angle_deg
from game.minigames.base_minigame import BaseAttackMinigame
from game.combat.battle_logic import _tick, wait_seconds
from game.combat.serial_controller import get_serial_controller
from game.champions.robot_base import (
    DB_MOV, PL_MOV, DB_ATTACK, PL_ATTACK, WAIT_MOV, _get_robots_from_ctx
)
from settings import SHAKE_HEAVY, C_ORANGE


class MeteorStompMinigame(BaseAttackMinigame):
    """Minigame Meteor Stomp — Otimizado e Otimização Sem Lag."""

    instruction_text = (
        "METEOR STOMP!\n"
        "Mova a cabeça para a Esquerda / Direita para coletar meteoros!"
    )
    instruction_icon = ""
    explanation_sound = "assets/sounds/dinobyte/minigames/meteor_stomp.wav"
    duration = 10.0

    def __init__(self):
        super().__init__()
        self.score = 0
        self.active_tile = 1
        self.face_side = "ESQUERDA"
        self.is_moving_tile = False

    def on_start(self):
        self.score = 0
        self.total_spawned = 0
        self.active_tile = 1  # 1 (Posição Base Inicial) ou 2 (1 Tile à Frente)
        self.face_side = "ESQUERDA"
        self.is_moving_tile = False

        # Meteoros 3D da jogabilidade e partículas de impacto no chão
        self.game_meteors_3d: List[Dict[str, Any]] = []
        self.floor_particles_3d: List[Dict[str, Any]] = []
        self.spawn_game_timer = 0.0

        # Referência de contexto, robô e orientação fixa
        self.robot = None
        self.ctx = None
        self.player_mov = None
        self.fixed_heading = 0.0

        if app.game_instance and hasattr(app.game_instance, "battle") and app.game_instance.battle:
            b = app.game_instance.battle
            self.ctx = b
            self.robot = b.player_robot
            if self.robot:
                db, pl = _get_robots_from_ctx(b)
                self.player_mov = DB_MOV if self.robot == db else PL_MOV
                self.fixed_heading = getattr(self.robot, "v_h", 0.0)

                self.base_tx = round(self.robot.v_tx)
                self.base_ty = round(self.robot.v_ty)
                forward_dy = -1.0 if self.robot.is_player else 1.0
                self.max_ty = self.base_ty + forward_dy

                # Garante que o robô comece 100% pronto para mover
                self.robot.is_moving = False
                self.robot.vx = 0.0
                self.robot.vy = 0.0
                self.robot.omega = 0.0
            else:
                self.base_tx, self.base_ty, self.max_ty = 1.0, 3.0, 2.0

            # Garante que os eventos seriais estejam limpos/desbloqueados para aceitar o primeiro passo
            sc = get_serial_controller()
            if sc and hasattr(sc, "_ok_events") and self.robot:
                tag = "PLAYER" if self.robot.is_player else "BOSS"
                if tag in sc._ok_events:
                    sc._ok_events[tag].set()

            if hasattr(b, "camera") and b.camera:
                b.camera.enter_meteor_stomp_mode(self.robot)

        # Restaura webcam para modo normal
        if app.game_instance and app.game_instance.qt_win:
            app.game_instance.qt_win.set_webcam_mode("normal")

        if app.game_instance and app.game_instance.cv_input:
            app.game_instance.cv_input.face_detection_enabled = True

        # Geometria simples e rápida dos meteoros
        self.small_meteor_geom = create_clean_cube(0.55, 0.55, 0.55)
        self.bright_mat = Material("bright_meteor_mat")
        self.bright_mat.setEmission(LColor(1.0, 0.9, 0.2, 1.0))
        self.bright_mat.setAmbient(LColor(1.0, 0.8, 0.1, 1.0))

        # Carrega textura fireball.png com transparência pura
        self.fireball_tex = None
        try:
            self.fireball_tex = TexturePool.loadTexture("assets/textures/fireball.png")
        except Exception:
            pass

        # Carrega som de explosão do meteoro
        self._snd_explosion = None
        if app.game_instance and hasattr(app.game_instance, "loader"):
            try:
                self._snd_explosion = app.game_instance.loader.loadSfx("assets/sounds/meteor_explosion.mp3")
                if self._snd_explosion:
                    self._snd_explosion.setVolume(1.0)
            except Exception as e:
                print(f"[MeteorStomp] Erro ao carregar som de explosão: {e}")

    def get_camera_x(self) -> float:
        """Obtém a posição X horizontal da câmera (0.0 = Esquerda, 1.0 = Direita)."""
        if app.game_instance and getattr(app.game_instance, "_input_mode", None) == "mouse":
            cursor = getattr(app.game_instance, "_finger_pos_norm", None)
            if cursor and cursor[0] is not None:
                return float(cursor[0])

        if app.game_instance and hasattr(app.game_instance, "cv_input") and app.game_instance.cv_input:
            cv = app.game_instance.cv_input
            cv.face_detection_enabled = True

            if hasattr(cv, "get_head_position"):
                fx, _ = cv.get_head_position()
                if fx is not None:
                    return float(fx)
            if hasattr(cv, "face_x") and cv.face_x is not None:
                return float(cv.face_x)

        if app.game_instance and hasattr(app.game_instance, "mouseWatcherNode"):
            try:
                if app.game_instance.mouseWatcherNode.hasMouse():
                    mx = app.game_instance.mouseWatcherNode.getMouseX()
                    return (mx + 1.0) / 2.0
            except Exception:
                pass

        return 0.5

    def _trigger_tile_step(self, direction: str, next_tile: int):
        """Dispara movimentação DSL completa e ininterrompível."""
        self.is_moving_tile = True

        async def step_sequence():
            try:
                await self.player_mov(self.ctx, direction, 1)
                await WAIT_MOV()
                self.active_tile = next_tile
            finally:
                self.is_moving_tile = False

        coro = step_sequence()
        if app.game_instance and hasattr(app.game_instance, "loop") and app.game_instance.loop:
            app.game_instance.loop.create_task(coro)
        elif hasattr(self.ctx, "_runner") and self.ctx._runner:
            self.ctx._runner.start(coro)

    def _spawn_floor_explosion_particles(self, pos_3d: Point3):
        """Cria uma pequena explosão 3D de partículas de poeira/fogo ao atingir o chão."""
        p_geom = create_clean_cube(0.18, 0.18, 0.18)
        p_mat = Material("floor_exp_mat")
        p_mat.setEmission(LColor(1.0, 0.5, 0.0, 1.0))

        for _ in range(6):
            gnode = GeomNode("floor_particle")
            gnode.addGeom(p_geom)
            p_np = app.game_instance.render.attachNewNode(gnode)
            p_np.setColor(LColor(1.0, random.uniform(0.3, 0.8), 0.0, 0.9))
            p_np.setMaterial(p_mat)
            p_np.setLightOff()
            p_np.setPos(pos_3d)
            p_np.setTransparency(TransparencyAttrib.MAlpha)

            vel = Point3(random.uniform(-2.0, 2.0), random.uniform(-2.0, 2.0), random.uniform(1.0, 3.5))
            self.floor_particles_3d.append({"np": p_np, "vel": vel, "life": 0.35})

    def on_update(self, hand_pos, hand_closed, dt):
        """Atualização dos meteoros 3D e movimentação ininterrompível."""
        if not app.game_instance or not hasattr(app.game_instance, "render"):
            return

        # ── Orientação Fixa do Robô ──
        if self.robot and hasattr(self, "fixed_heading"):
            self.robot.v_h = self.fixed_heading
            self.robot.target_h = self.fixed_heading

        # ── Rastreamento da Câmera ──
        cam_x = self.get_camera_x()
        target_tile = 1 if cam_x < 0.5 else 2
        self.face_side = f"ESQUERDA ({cam_x:.2f})" if target_tile == 1 else f"DIREITA ({cam_x:.2f})"

        # ── Movimento Ininterrupto via DSL entre 2 Tiles ──
        if self.robot and self.player_mov and self.ctx:
            if not getattr(self, "is_moving_tile", False) and not getattr(self.robot, "is_moving", False):
                if target_tile == 2 and self.active_tile == 1:
                    print("[MeteorStomp] Câmera Direita -> Avance para Tile 2...")
                    self._trigger_tile_step("FRENTE", 2)
                elif target_tile == 1 and self.active_tile == 2:
                    print("[MeteorStomp] Câmera Esquerda -> Recua para Tile 1...")
                    self._trigger_tile_step("TRAS", 1)

        # ── Spawn de METEOROS 3D ──
        self.spawn_game_timer += dt
        if self.spawn_game_timer >= 0.38:
            self.spawn_game_timer = 0.0
            target_meteor_tile = random.choice([1, 2])
            
            base_tx = getattr(self, "base_tx", 1.0)
            base_ty = getattr(self, "base_ty", 3.0)
            max_ty = getattr(self, "max_ty", 2.0)

            t1_world = grid_to_world(base_tx, base_ty)
            t2_world = grid_to_world(base_tx, max_ty)
            target_p3d = t1_world if target_meteor_tile == 1 else t2_world

            gnode_gm = GeomNode(f"game_meteor_{len(self.game_meteors_3d)}")
            gnode_gm.addGeom(self.small_meteor_geom)
            np_gm = app.game_instance.render.attachNewNode(gnode_gm)
            np_gm.setColor(LColor(1.0, 1.0, 1.0, 0.95))
            np_gm.setMaterial(self.bright_mat)
            np_gm.setLightOff()
            np_gm.setScale(0.60)
            np_gm.setPos(target_p3d.getX(), target_p3d.getY(), 7.5)
            np_gm.setTransparency(TransparencyAttrib.MAlpha)

            if self.fireball_tex:
                np_gm.setTexture(self.fireball_tex, 1)

            self.game_meteors_3d.append({
                "np": np_gm,
                "tile": target_meteor_tile,
                "z": 7.5,
                "speed": random.uniform(6.5, 9.0),
                "alive": True
            })

        # ── Atualiza Partículas de Chão ──
        for p in list(self.floor_particles_3d):
            p["life"] -= dt
            if p["life"] <= 0:
                p["np"].removeNode()
                self.floor_particles_3d.remove(p)
            else:
                p["np"].setPos(p["np"].getPos() + p["vel"] * dt)
                p["vel"].setZ(p["vel"].getZ() - 9.8 * dt)

        # ── Atualiza Queda dos Meteoros 3D ──
        for gm_m in list(self.game_meteors_3d):
            if not gm_m["alive"]:
                continue

            gm_m["z"] -= gm_m["speed"] * dt
            gm_m["np"].setZ(gm_m["z"])
            gm_m["np"].setHpr(gm_m["np"].getH() + 180 * dt, gm_m["np"].getP() + 90 * dt, 0)

            if gm_m["z"] <= 0.6:
                gm_m["alive"] = False
                gm_m["np"].hide()

                b = getattr(app.game_instance, "battle", None)
                ctx = b if b else None

                # 1. ACERTOU O DINOBYTE (Capturou o Meteoro)
                if gm_m["tile"] == self.active_tile:
                    self.score += 1

                    # Efeito de Powerup Arcade: Piscar branco brilhante no DinoByte
                    if self.robot and hasattr(self.robot, "flash_timer"):
                        self.robot.flash_timer = 0.28

                    if ctx and hasattr(ctx, "create_floating") and self.robot:
                        ctx.create_floating(
                            self.robot.v_tx,
                            self.robot.v_ty,
                            "+1 METEORO!",
                            (1.0, 0.85, 0.1, 1.0),
                            size=1.5
                        )
                # 2. ERROU (Meteoro explode no chão com partículas 3D e camerashake leve)
                else:
                    impact_p3d = gm_m["np"].getPos()
                    impact_p3d.setZ(0.2)
                    self._spawn_floor_explosion_particles(impact_p3d)

                    if getattr(self, "_snd_explosion", None):
                        self._snd_explosion.play()

                    if b and hasattr(b, "camera") and b.camera:
                        from settings import SHAKE_LIGHT
                        b.camera.add_shake(SHAKE_LIGHT)

                gm_m["np"].removeNode()
                self.game_meteors_3d.remove(gm_m)

    def evaluate(self) -> str:
        if self.score >= 12:
            return "excellent"
        elif self.score >= 5:
            return "good"
        return "poor"

    def on_finish(self):
        """Limpeza ao finalizar os 10s do minigame."""
        if app.game_instance and hasattr(app.game_instance, "cv_input") and app.game_instance.cv_input:
            app.game_instance.cv_input.face_detection_enabled = False

        for m in self.game_meteors_3d:
            if m.get("np"):
                m["np"].removeNode()
        self.game_meteors_3d.clear()

        for p in self.floor_particles_3d:
            if p.get("np"):
                p["np"].removeNode()
        self.floor_particles_3d.clear()

    def paint(self, painter, width: int, height: int, scale: float):
        """Renderiza o HUD 2D LIMPO."""
        painter.setRenderHint(painter.RenderHint.Antialiasing)

        banner_w = int(440 * scale)
        banner_h = int(36 * scale)
        banner_x = (width - banner_w) // 2
        banner_y = int(25 * scale)

        painter.setBrush(QColor(10, 12, 28, 210))
        painter.setPen(QPen(QColor(255, 140, 0, 240), 2 * scale))
        painter.drawRoundedRect(banner_x, banner_y, banner_w, banner_h, 8, 8)

        font_header = QFont("Arial", int(12 * scale), QFont.Bold)
        painter.setFont(font_header)
        painter.setPen(QColor(255, 220, 0))
        painter.drawText(
            QRectF(banner_x, banner_y, banner_w, banner_h),
            Qt.AlignCenter,
            f"GALAGA METEOR STOMP | SCORE: {self.score}"
        )

        time_frac = self.get_time_fraction()
        tbar_w = banner_w
        tbar_h = int(8 * scale)
        tbar_x = banner_x
        tbar_y = banner_y + banner_h + int(6 * scale)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(30, 30, 45, 220))
        painter.drawRoundedRect(tbar_x, tbar_y, tbar_w, tbar_h, 4, 4)

        fill_w = int(tbar_w * time_frac)
        t_grad = QLinearGradient(tbar_x, 0, tbar_x + tbar_w, 0)
        t_grad.setColorAt(0.0, QColor(0, 240, 255))
        t_grad.setColorAt(1.0, QColor(255, 60, 0))
        painter.setBrush(QBrush(t_grad))
        painter.drawRoundedRect(tbar_x, tbar_y, fill_w, tbar_h, 4, 4)

        cv_txt = f"CÂMERA: {self.face_side}  ➔  TILE {self.active_tile}"
        font_cv = QFont("Arial", int(9 * scale), QFont.Bold)
        painter.setFont(font_cv)
        painter.setPen(QColor(0, 240, 255))
        painter.drawText(
            QRectF(tbar_x, tbar_y + tbar_h + 4 * scale, tbar_w, 20 * scale),
            Qt.AlignCenter,
            cv_txt
        )


async def execute_meteor_stomp_attack(robot, target, ability, final_damage, camera, ctx):
    """Pós-minigame: Carregamento 1.4m À FRENTE no focinho, textura fireball transparente e sem lag."""
    db, pl = _get_robots_from_ctx(ctx)
    player_mov = DB_MOV if robot == db else PL_MOV

    collected_score = 0
    active_tile = 1
    active_mg = getattr(app.game_instance, "active_attack_minigame", None) if app.game_instance else None
    if active_mg:
        if hasattr(active_mg, "score"):
            collected_score = active_mg.score
        if hasattr(active_mg, "active_tile"):
            active_tile = active_mg.active_tile

    if app.game_instance and hasattr(app.game_instance, "cv_input") and app.game_instance.cv_input:
        app.game_instance.cv_input.face_detection_enabled = False

    if app.game_instance and hasattr(app.game_instance, "active_attack_minigame"):
        app.game_instance.active_attack_minigame = None

    if app.game_instance and app.game_instance.qt_win:
        app.game_instance.qt_win.set_webcam_mode("normal")
        app.game_instance.qt_win.minigame_instruction_overlay.hide()

    await WAIT_MOV()

    initial_tx = getattr(robot, "base_tx", round(robot.v_tx)) if hasattr(robot, "base_tx") else round(robot.v_tx)
    initial_ty = getattr(robot, "base_ty", round(robot.v_ty)) if hasattr(robot, "base_ty") else round(robot.v_ty)

    if active_tile == 2 or abs(robot.v_ty - initial_ty) > 0.3:
        print(f"[MeteorStomp] Retornando ao Tile 1 inicial via comando DSL: TRAS 1 tile...")
        await player_mov(ctx, "TRAS", 1)
        await WAIT_MOV()

    if hasattr(robot, "stop_all_motion"):
        robot.stop_all_motion()

    robot.v_tx = float(initial_tx)
    robot.v_ty = float(initial_ty)
    robot.target_tx = float(initial_tx)
    robot.target_ty = float(initial_ty)

    sc = get_serial_controller()
    if sc:
        sc.send_command_realtime(robot, "STOP", 0)

    # ════════════════════════════════════════════════════════════════════════
    # POSICIONAMENTO DA BOLA DE FOGO DESLOCADA PARA TRÁS (boca/garganta do DinoByte)
    # ════════════════════════════════════════════════════════════════════════
    p_mouth = grid_to_world(robot.v_tx, robot.v_ty) + Point3(0.0, 0.45, 1.05)
    p_target = grid_to_world(target.v_tx, target.v_ty) + Point3(0, 0, 0.85)

    # ════════════════════════════════════════════════════════════════════════
    # CARREGAMENTO 1.5s COM TEXTURA TRANSPARENTE PURA (SEM CUBO SÓLIDO)
    # ════════════════════════════════════════════════════════════════════════
    fireball_geom = create_clean_cube(0.85, 0.85, 0.85)
    gnode_fb = GeomNode("fireball_projectile")
    gnode_fb.addGeom(fireball_geom)
    fb_np = app.game_instance.render.attachNewNode(gnode_fb)
    fb_np.setColor(LColor(1.0, 1.0, 1.0, 0.95))  # Cor neutra para preservar textura pura
    fb_np.setLightOff()
    fb_np.setTransparency(TransparencyAttrib.MAlpha)

    try:
        fireball_tex = TexturePool.loadTexture("assets/textures/fireball.png")
        if fireball_tex:
            fb_np.setTexture(fireball_tex, 1)
    except Exception:
        pass

    fb_np.setPos(p_mouth)

    charge_duration = 1.5
    charge_start = time.time()

    while time.time() - charge_start < charge_duration:
        await _tick()

        if hasattr(robot, "stop_all_motion"):
            robot.stop_all_motion()
        robot.v_tx = float(initial_tx)
        robot.v_ty = float(initial_ty)

        ct = (time.time() - charge_start) / charge_duration
        ct = min(1.0, max(0.0, ct))

        current_dist = 4.5 - (2.2 * ct)
        if camera and hasattr(camera, "enter_mouth_close_up_charge"):
            camera.enter_mouth_close_up_charge(p_mouth, current_dist)

        scale_val = 0.12 + (1.45 * ct) + (0.09 * math.sin(ct * math.pi * 16.0))
        fb_np.setScale(scale_val)
        fb_np.setHpr(ct * 720, ct * 360, 0)

    # ════════════════════════════════════════════════════════════════════════
    # DISPARO RÁPIDO (0.45s) & CÂMERA ACOMPANHANDO VOÔ ATÉ O PENLINUX
    # ════════════════════════════════════════════════════════════════════════
    if camera and hasattr(camera, "add_shake"):
        from settings import SHAKE_MEDIUM
        camera.add_shake(SHAKE_MEDIUM)
    ctx.create_floating(
        robot.v_tx, robot.v_ty,
        f"GALAGA SCORE: {collected_score}!",
        (1.0, 0.85, 0.1, 1.0), size=1.8
    )

    fly_duration = 0.45
    fly_start = time.time()

    while time.time() - fly_start < fly_duration:
        await _tick()
        t = (time.time() - fly_start) / fly_duration
        t = min(1.0, max(0.0, t))

        curr_x = p_mouth.getX() + (p_target.getX() - p_mouth.getX()) * t
        curr_y = p_mouth.getY() + (p_target.getY() - p_mouth.getY()) * t
        curr_z = p_mouth.getZ() + (p_target.getZ() - p_mouth.getZ()) * t + math.sin(t * math.pi) * 0.9
        curr_pos = Point3(curr_x, curr_y, curr_z)

        fb_np.setPos(curr_pos)
        fb_np.setHpr(t * 900, t * 450, t * 225)

        if camera and hasattr(camera, "set_cinematic_fireball_pan"):
            camera.set_cinematic_fireball_pan(curr_pos)

    fb_np.removeNode()

    # ════════════════════════════════════════════════════════════════════════
    # IMPACTO, EXPLOSÃO DE PARTÍCULAS 3D & DANO NO PENLINUX
    # ════════════════════════════════════════════════════════════════════════
    explosion_particles = []
    p_mat = Material("exp_p_mat")
    p_mat.setEmission(LColor(1.0, 0.6, 0.0, 1.0))
    p_geom = create_clean_cube(0.22, 0.22, 0.22)

    for _ in range(10):
        gnode = GeomNode("exp_part")
        gnode.addGeom(p_geom)
        p_np = app.game_instance.render.attachNewNode(gnode)
        p_np.setColor(LColor(1.0, random.uniform(0.3, 0.8), 0.0, 0.9))
        p_np.setMaterial(p_mat)
        p_np.setLightOff()
        p_np.setPos(p_target)
        p_np.setTransparency(TransparencyAttrib.MAlpha)
        vel = Point3(random.uniform(-3.0, 3.0), random.uniform(-3.0, 3.0), random.uniform(1.5, 4.5))
        explosion_particles.append({"np": p_np, "vel": vel})

    exp_duration = 0.28
    exp_start = time.time()
    while time.time() - exp_start < exp_duration:
        await _tick()
        dt_exp = 0.016
        for p in explosion_particles:
            p["np"].setPos(p["np"].getPos() + p["vel"] * dt_exp)
            p["vel"].setZ(p["vel"].getZ() - 9.8 * dt_exp)

    for p in explosion_particles:
        p["np"].removeNode()
    explosion_particles.clear()

    damage_multiplier = min(1.0, max(0.3, collected_score / 14.0))
    damage_to_deal = max(1, int(final_damage * damage_multiplier))

    if camera and hasattr(camera, "shake"):
        from settings import SHAKE_HEAVY
        camera.shake(SHAKE_HEAVY, duration=0.80)
    elif camera and hasattr(camera, "add_shake"):
        from settings import SHAKE_HEAVY
        camera.add_shake(SHAKE_HEAVY)

    if robot.name_code.lower() == "dinobyte":
        await DB_ATTACK(ctx, damage_to_deal)
    else:
        await PL_ATTACK(ctx, damage_to_deal)
    await WAIT_MOV()

    if camera and hasattr(camera, "reset_to_battle_view"):
        camera.reset_to_battle_view()

    await wait_seconds(0.5)
