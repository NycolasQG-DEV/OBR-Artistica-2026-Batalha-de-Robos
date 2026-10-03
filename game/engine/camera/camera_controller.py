# engine/camera/camera_controller.py — controlador principal de câmera do Panda3D
import math
import random
from panda3d.core import Point3, Vec3

from settings import (
    CAM_SELECT_ZOOM_DIST, CAM_BATTLE_ZOOM_DIST, CAM_INTRO_DURATION, CAM_SELECT_SPIN_TIME,
    STATE_SELECT_ROBOT,
    POV_HEAD_HEIGHT, POV_OFFSET_UP, POV_OFFSET_BACK, POV_PITCH, POV_LERP_SPEED,
    TAIL_POV_FORWARD, TAIL_POV_HEIGHT, TAIL_POV_PITCH, TAIL_CAM_FOV, TAIL_CAM_LERP,
    CAM_DANCE_ZOOM_DIST,
)



def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3

class CameraController:
    """Câmera isométrica com cinematica suave: zoom, spin, intro épica."""

    # Modos de cinematica
    MODE_IDLE     = "idle"      # posição padrão isométrica
    MODE_INTRO    = "intro"     # sequência de abertura
    MODE_SPIN     = "spin"      # gira ao redor da arena
    MODE_ZOOM_IN  = "zoom_in"   # close in dramático
    MODE_ZOOM_OUT = "zoom_out"  # afasta para mostrar arena
    MODE_BATTLE   = "battle"    # modo de batalha focado
    MODE_TRACKING = "tracking"  # câmera dinâmica estilo transmissão
    MODE_ACTION   = "action"    # modo de ação cinematográfico
    MODE_MINIGAME = "minigame"  # câmera top-down para o minijogo
    MODE_POV      = "pov"       # câmera no ponto de vista do robô
    MODE_ORBIT    = "orbit"     # órbita cinemática ao redor de dois robôs
    MODE_TAIL_CHASE = "tail_chase"  # chase cam 3ª pessoa (Tail Quake minigame)

    def __init__(self, camera, base_app):
        self.camera      = camera
        self.base        = base_app
        self._shake_mag  = 0.0
        self._shake_time = 0.0
        self._center     = Point3(0, 0, 0)
        self._target_center = Point3(0, 0, 0)

        # Estado atual da câmera
        self._dist       = CAM_SELECT_ZOOM_DIST
        self._heading    = 0.0
        self._pitch      = -30.0

        # Alvos para interpolação suave
        self._target_dist    = CAM_SELECT_ZOOM_DIST
        self._target_heading = 0.0
        self._target_pitch   = -30.0

        # FOV and lens parameters
        self._base_fov       = 45.0
        self._target_fov     = 45.0
        self._fov            = 55.0  # start wide for cinematic intro entry
        self._lerp_fov       = 3.5
        self._fov_kick       = 0.0

        # Advanced Trauma system (0.0 to 1.0)
        self._trauma         = 0.0
        self._trauma_decay   = 1.5

        # Cinematica
        self._mode       = self.MODE_IDLE
        self._mode_timer = 0.0
        self._mode_dur   = CAM_INTRO_DURATION
        self._spin_dir   = 1.0   # +1 ou -1

        # Velocidades de interpolação (lerp factor por segundo)
        self._lerp_dist    = 2.5
        self._lerp_heading = 3.0
        self._lerp_pitch   = 2.0
        self._lerp_center  = 3.0

        # Orbita suave (modo idle / select)
        self._orbit_active = False
        self._orbit_speed  = 0.0  # desativado para manter câmera fixa/estável
        self._shot_timer = 0.0
        self._next_shot_change = random.uniform(3.0, 6.0)

        # Posição inicial
        self._heading = 0.0
        self._dist    = CAM_SELECT_ZOOM_DIST
        self._pitch   = -30.0

    # ── Controle público ──────────────────────────────────────────────

    def add_shake(self, magnitude: float):
        self._shake_mag  = max(self._shake_mag, magnitude * 5)
        self._shake_time = 0.3
        self._trauma = min(1.0, self._trauma + magnitude * 2.8)
        self._fov_kick = -magnitude * 3.5

    def shake(self, magnitude: float = 0.32, duration: float = 2.0):
        """Ativa camerashake de alta intensidade pela duração especificada em segundos."""
        self._trauma = min(1.0, magnitude * 3.2)
        self._trauma_decay = (1.0 / max(0.1, duration))
        self._fov_kick = -magnitude * 6.0

    def trigger_camera_pulse(self, intensity: float = 1.0):
        """Gera um pulso rápido de FOV/Zoom na câmera na batida da música."""
        self._fov_kick = -7.5 * intensity

    def set_center(self, cx: float, cy: float):
        self._target_center = Point3(cx, cy, 0.0)

    def set_camera_speed(self, speed_type: str):
        if speed_type == "fast":
            self._lerp_dist    = 5.0
            self._lerp_heading = 5.0
            self._lerp_pitch   = 4.5
            self._lerp_center  = 4.5
        elif speed_type == "slow":
            self._lerp_dist    = 1.2
            self._lerp_heading = 1.0
            self._lerp_pitch   = 1.0
            self._lerp_center  = 1.5
        else:  # normal
            self._lerp_dist    = 2.6
            self._lerp_heading = 3.2
            self._lerp_pitch   = 2.2
            self._lerp_center  = 2.8

    def update(self, dt: float):
        from panda3d.core import ClockObject
        globalClock = ClockObject.getGlobalClock()

        # ── Tremor de Câmera (Trauma) ──
        (shake_x, shake_y, shake_z,
         shake_h, shake_p, shake_r, shake_fov) = self.update_shake(dt)

        # ── Breathing/Handheld Drift (Sempre ativo fora do minijogo) ──
        drift_x = drift_y = drift_z = 0.0
        drift_h = drift_p = drift_r = 0.0

        if self._mode != self.MODE_MINIGAME:
            t_glob = globalClock.getFrameTime()
            drift_x = math.sin(t_glob * 0.6) * 0.14 + math.cos(t_glob * 1.1) * 0.06
            drift_y = math.sin(t_glob * 0.4) * 0.08
            drift_z = math.cos(t_glob * 0.5) * 0.18 + math.sin(t_glob * 1.3) * 0.07
            
            drift_h = math.sin(t_glob * 0.35) * 0.4 + math.cos(t_glob * 0.8) * 0.2
            drift_p = math.cos(t_glob * 0.45) * 0.3 + math.sin(t_glob * 0.9) * 0.15
            drift_r = math.sin(t_glob * 0.55) * 0.7 + math.cos(t_glob * 1.05) * 0.3

        # ── Modo TAIL_CHASE (Tail Quake minigame) ──
        if self._mode == self.MODE_TAIL_CHASE:
            self.update_tail_chase(dt, shake_x, shake_y, shake_z, shake_h, shake_p, shake_r, shake_fov, drift_x, drift_y, drift_z, drift_h, drift_p, drift_r)
            return

        # ── Modo POV first-person ──
        if self._mode == self.MODE_POV:
            self.update_pov(dt, shake_x, shake_y, shake_z, shake_h, shake_p, shake_r, shake_fov, drift_x, drift_y, drift_z, drift_h, drift_p, drift_r)
            return

        # ── Interpola centro ──
        lc_f = min(1.0, self._lerp_center * dt)
        self._center = Point3(
            self._center.getX() + (self._target_center.getX() - self._center.getX()) * lc_f,
            self._center.getY() + (self._target_center.getY() - self._center.getY()) * lc_f,
            0,
        )

        # ── Lógicas Cinemáticas por modo ──
        self.update_cinematics(dt, STATE_SELECT_ROBOT)

        # ── Modo ORBIT ──
        if self._mode == self.MODE_ORBIT:
            ra = getattr(self, "_orbit_robot_a", None)
            rb = getattr(self, "_orbit_robot_b", None)
            if ra and rb:
                from engine.render.geometry import grid_to_world
                pa = grid_to_world(ra.v_tx, ra.v_ty)
                pb = grid_to_world(rb.v_tx, rb.v_ty)
                mid_x = (pa.getX() + pb.getX()) / 2
                mid_y = (pa.getY() + pb.getY()) / 2
                self._target_center = Point3(mid_x, mid_y, 0.9)
                freq = 0.7
                amp = 20.0
                self._target_heading = self._orbit_start_heading + math.sin(self._mode_timer * freq) * amp

        # ── Orbita suave no modo idle/seleção ──
        if self._orbit_active and self._mode == self.MODE_IDLE:
            self._target_heading += self._orbit_speed * dt

        # ── Zoom Dinâmico de Ataque ──
        extra_zoom = 0.0
        if self._mode != self.MODE_MINIGAME and hasattr(self.base, "battle") and self.base.battle.player_robot:
            pr = self.base.battle.player_robot
            if pr.v_ty < pr.base_ty:
                diff = pr.base_ty - pr.v_ty
                extra_zoom = diff * 1.8

        # ── Interpola distância ──
        if self._mode != self.MODE_INTRO:
            ld = min(1.0, self._lerp_dist * dt)
            current_target_dist = max(4.0, self._target_dist - extra_zoom)
            self._dist += (current_target_dist - self._dist) * ld

        # ── Interpola heading ──
        if self._mode not in (self.MODE_INTRO, self.MODE_SPIN):
            dh = self._target_heading - self._heading
            while dh >  180: dh -= 360
            while dh < -180: dh += 360
            self._heading += dh * min(1.0, self._lerp_heading * dt)

        # ── Interpola pitch ──
        if self._mode != self.MODE_INTRO:
            self._pitch += (self._target_pitch - self._pitch) * min(1.0, self._lerp_pitch * dt)

        # Clamp parameters to keep the stage in view while supporting top-down and cinematic angles
        self._heading = (self._heading + 180.0) % 360.0 - 180.0
        min_p = -89.5 if self._mode in (self.MODE_MINIGAME, self.MODE_ACTION, self.MODE_POV, self.MODE_TAIL_CHASE) else -75.0
        max_p = 15.0 if self._mode in (self.MODE_MINIGAME, self.MODE_ACTION, self.MODE_POV) else -5.0
        self._pitch = max(min_p, min(max_p, self._pitch))
        self._dist = max(2.5, min(35.0, self._dist))

        # Posiciona câmera (sistema esférico normal)
        heading_rad = math.radians(self._heading)
        pitch_rad   = math.radians(self._pitch)
        d           = self._dist

        cx_off = math.sin(heading_rad) * math.cos(pitch_rad) * d
        cy_off = -math.cos(heading_rad) * math.cos(pitch_rad) * d
        cz_off = math.sin(-pitch_rad) * d

        pos = self._center + Vec3(
            cx_off + shake_x + drift_x, 
            cy_off + shake_y + drift_y, 
            cz_off + shake_z + drift_z
        )
        self.camera.setPos(pos)
        self.camera.lookAt(self._center + Vec3(0, 0, 1))

        # Adiciona offsets de rotação
        cam_h = self.camera.getH()
        cam_p = self.camera.getP()
        cam_r = self.camera.getR()

        roll = 0.0

        self.camera.setHpr(
            cam_h + shake_h + drift_h,
            cam_p + shake_p + drift_p,
            cam_r + shake_r + drift_r + roll
        )

        # Lentes (FOV + Zoom kick + shake)
        lens = getattr(self.base, "camLens", None)
        if lens:
            final_fov = self._fov + self._fov_kick + shake_fov
            final_fov = max(15.0, min(80.0, final_fov))
            lens.setFov(final_fov)


    # --- Shake Methods ---

    def update_shake(self, dt):
        from panda3d.core import ClockObject
        globalClock = ClockObject.getGlobalClock()
        if self._mode != self.MODE_INTRO:
            self._fov += (self._target_fov - self._fov) * min(1.0, self._lerp_fov * dt)
        if self._trauma > 0.0:
            self._trauma = max(0.0, self._trauma - self._trauma_decay * dt)
        if abs(self._fov_kick) > 0.01:
            self._fov_kick += (0.0 - self._fov_kick) * min(1.0, 8.0 * dt)
        else:
            self._fov_kick = 0.0
        if self._shake_time > 0:
            self._shake_time = max(0.0, self._shake_time - dt)
            self._shake_mag *= 0.85
        shake_x = shake_y = shake_z = 0.0
        shake_h = shake_p = shake_r = 0.0
        shake_fov = 0.0
        if self._trauma > 0.0:
            t_glob = globalClock.getFrameTime()
            shake_amt = self._trauma ** 2
            freq_x, freq_y, freq_z = (24.0, 20.0, 22.0)
            freq_h, freq_p, freq_r = (18.0, 16.0, 19.0)
            max_pos = 1.3
            shake_x = math.sin(t_glob * freq_x) * max_pos * shake_amt
            shake_y = math.cos(t_glob * freq_y) * max_pos * shake_amt
            shake_z = math.sin(t_glob * freq_z) * max_pos * shake_amt * 0.5
            max_rot = 5.5
            shake_h = math.sin(t_glob * freq_h) * max_rot * shake_amt
            shake_p = math.cos(t_glob * freq_p) * max_rot * shake_amt
            shake_r = math.sin(t_glob * freq_r) * max_rot * 1.5 * shake_amt
            shake_fov = math.sin(t_glob * 28.0) * 8.0 * shake_amt
        return (shake_x, shake_y, shake_z, shake_h, shake_p, shake_r, shake_fov)


    # --- Cinematics Methods ---

    def cinematic_select_spin(self):
        """Spin épico ao selecionar campeão."""
        self._mode = self.MODE_SPIN
        self._mode_timer = 0.0
        self._mode_dur = CAM_SELECT_SPIN_TIME
        self._spin_dir = random.choice([-1.0, 1.0])
        self._target_fov = 42.0
        self._orbit_active = False

    def cinematic_zoom_in(self):
        """Close in dramático para batalha."""
        self._mode = self.MODE_ZOOM_IN
        self._mode_timer = 0.0
        self._mode_dur = 1.2
        self._target_dist = CAM_BATTLE_ZOOM_DIST
        self._target_heading = 0.0
        self._target_pitch = -30.0
        self._target_fov = 42.0
        self._orbit_active = False

    def cinematic_zoom_out(self):
        """Afasta câmera para mostrar arena."""
        self._mode = self.MODE_ZOOM_OUT
        self._mode_timer = 0.0
        self._mode_dur = 1.0
        self._target_dist = CAM_SELECT_ZOOM_DIST
        self._target_pitch = -30.0
        self._target_fov = 45.0
        self._orbit_active = True

    def cinematic_battle_start(self):
        """Sequência de abertura de batalha."""
        self._target_dist = CAM_BATTLE_ZOOM_DIST
        self._target_pitch = -30.0
        self._target_heading = 0.0
        self._target_fov = 45.0
        self._orbit_active = False

    def cinematic_game_over(self):
        """Câmera dramática de fim de jogo."""
        self._target_dist = CAM_BATTLE_ZOOM_DIST * 0.85
        self._target_heading = self._heading + 60
        self._target_pitch = -38.0
        self._target_fov = 38.0
        self._mode = self.MODE_SPIN
        self._mode_timer = 0.0
        self._mode_dur = 3.0
        self._spin_dir = 1.0

    def update_cinematics(self, dt, STATE_SELECT_ROBOT):
        self._mode_timer += dt
        self._shot_timer += dt
        battle = getattr(self.base, 'battle', None)
        battle_state = getattr(battle, 'state', None)
        is_executing = getattr(battle, 'is_executing_action', False)
        is_static_moment = battle_state == STATE_SELECT_ROBOT or (battle_state == 'player_turn' and (not is_executing))
        if self._shot_timer >= self._next_shot_change and self._mode == self.MODE_IDLE and is_static_moment:
            self._shot_timer = 0.0
            self._next_shot_change = random.uniform(6.0, 10.0)
            if battle_state == STATE_SELECT_ROBOT:
                self._target_heading = random.choice([-20, -10, 0, 10, 20])
                self._target_pitch = random.uniform(-25, -35)
                self._target_dist = random.uniform(20.0, 24.0)
            else:
                view_type = random.choice(['standard', 'profile'])
                if view_type == 'standard':
                    self._target_heading = 0.0
                    self._target_pitch = -30.0
                    self._target_dist = 11.5
                else:
                    self._target_heading = random.choice([90.0, -90.0])
                    self._target_pitch = -18.0
                    self._target_dist = 13.0
                pr = getattr(battle, 'player_robot', None)
                ia = getattr(battle, 'ia_robot', None)
                if pr and ia:
                    from engine.render.geometry import grid_to_world
                    from panda3d.core import Point3
                    pa = grid_to_world(pr.v_tx, pr.v_ty)
                    pb = grid_to_world(ia.v_tx, ia.v_ty)
                    mid = (pa + pb) * 0.5
                    self._target_center = Point3(mid.getX(), mid.getY(), 0.8)
        if self._mode == self.MODE_INTRO:
            t = min(1.0, self._mode_timer / self._mode_dur)
            ease = ease_out_cubic(t)
            self._heading = self._intro_heading_start + (0.0 - self._intro_heading_start) * ease
            self._dist = CAM_SELECT_ZOOM_DIST * 1.6 + (CAM_SELECT_ZOOM_DIST - CAM_SELECT_ZOOM_DIST * 1.6) * ease
            self._pitch = -15.0 + (-30.0 - -15.0) * ease
            self._fov = 55.0 + (45.0 - 55.0) * ease
            if t >= 1.0:
                self._mode = self.MODE_IDLE
                self._orbit_active = False
        elif self._mode == self.MODE_SPIN:
            spin_speed = 360.0 / self._mode_dur
            self._heading += self._spin_dir * spin_speed * dt
            self._target_heading = self._heading
            if self._mode_timer >= self._mode_dur:
                self._mode = self.MODE_IDLE
                self._target_heading = 0.0
                self._orbit_active = True
        elif self._mode in (self.MODE_ZOOM_IN, self.MODE_ZOOM_OUT):
            if self._mode_timer >= self._mode_dur:
                self._mode = self.MODE_IDLE
        if self._mode == self.MODE_ACTION:
            self._target_heading += 1.5 * dt
            self._target_dist = max(3.5, self._target_dist - 0.25 * dt)


    # --- Gameplay Methods ---

    def enter_minigame_mode(self):
        """Prepara câmera estática para os minijogos de desvio do boss (Fixo no Palco, sem seguir o robô)."""
        self._mode = self.MODE_MINIGAME
        self._target_center = Point3(0, 0, 0.4)
        self._target_dist = 15.5
        self._target_heading = 0.0
        self._target_pitch = -25.0
        self._target_fov = 65.0
        self._orbit_active = False
        self.set_camera_speed('fast')

    def enter_meteor_stomp_mode(self, player_robot=None):
        """Câmera lateral para o minijogo Meteor Stomp (DinoByte no middle-bottom da tela)."""
        self._mode = self.MODE_MINIGAME
        if player_robot is None and hasattr(self.base, "battle") and self.base.battle:
            player_robot = self.base.battle.player_robot

        if player_robot:
            from engine.render.geometry import grid_to_world
            wp = grid_to_world(player_robot.v_tx, player_robot.v_ty)
            self._target_center = Point3(wp.getX(), wp.getY() + 0.8, 1.4)
        else:
            self._target_center = Point3(0.0, 0.5, 1.4)

        self._target_dist = 10.5   # Zoom aproximado no robô
        self._target_heading = 90.0   # Visão Lateral
        self._target_pitch = -18.0     # Inclinação suave
        self._target_fov = 65.0
        self._orbit_active = False
        self.set_camera_speed('fast')

    def enter_mouth_close_up_charge(self, focal_point, current_dist=2.8):
        """Super close-up lateral na boca do robô do player durante o carregamento."""
        self._mode = self.MODE_MINIGAME
        self._target_center = Point3(focal_point.getX(), focal_point.getY(), focal_point.getZ())
        self._target_dist = current_dist
        self._target_heading = 90.0   # Visão Lateral
        self._target_pitch = -4.0
        self._target_fov = 45.0
        self._orbit_active = False
        self.set_camera_speed('fast')

    def set_cinematic_side_charge(self, focal_point, current_dist):
        """Visão lateral focalizando a bola de fogo na boca com zoom dinâmico progressivo."""
        self._mode = self.MODE_MINIGAME
        self._target_center = Point3(focal_point.getX(), focal_point.getY(), focal_point.getZ())
        self._target_dist = current_dist
        self._target_heading = 90.0   # Visão Lateral
        self._target_pitch = -8.0
        self._target_fov = 55.0
        self._orbit_active = False
        self.set_camera_speed('fast')

    def set_cinematic_fireball_pan(self, current_fireball_pos):
        """Câmera lateral pivô acompanhando o voo rápido da bola de fogo até o PenLinux."""
        self._mode = self.MODE_MINIGAME
        self._target_center = Point3(current_fireball_pos.getX(), current_fireball_pos.getY(), current_fireball_pos.getZ())
        self._target_dist = 6.2
        self._target_heading = 90.0   # Mantém perspectiva lateral cinematográfica
        self._target_pitch = -12.0
        self._target_fov = 60.0
        self._orbit_active = False
        self.set_camera_speed('fast')

    def enter_dance_night_mode(self):
        """Close-up camera mode for the Dance Master pose matching minigame."""
        self._mode = self.MODE_ACTION
        pr = self.base.battle.player_robot
        if pr:
            from engine.render.geometry import grid_to_world
            wp = grid_to_world(pr.v_tx, pr.v_ty)
            self._target_center = Point3(wp.getX(), wp.getY(), 0.85)
        else:
            self._target_center = Point3(0.0, -2.84, 0.85)
        self._target_dist = CAM_DANCE_ZOOM_DIST
        self._target_heading = 90.0
        self._target_pitch = -10.0
        self._target_fov = 42.0
        self._orbit_active = False
        self.set_camera_speed('fast')

    def enter_tail_chase_mode(self, player_robot):
        """Ativa câmera 1ª pessoa no rabo/cabeça do robô (Tail Quake minigame)."""
        self._mode = self.MODE_TAIL_CHASE
        self._tail_robot = player_robot
        self._orbit_active = False
        from engine.render.geometry import grid_to_world
        wp = grid_to_world(player_robot.v_tx, player_robot.v_ty)
        self._tail_cx = wp.getX()
        self._tail_cy = wp.getY()
        self._tail_cz = TAIL_POV_HEIGHT
        self._tail_ch = player_robot.v_h + player_robot.model_offset + 180.0
        self._tail_cp = TAIL_POV_PITCH
        self.set_camera_speed('fast')

    def enter_pov_mode(self, player_robot):
        """Ativa câmera em 1ª pessoa no ponto de vista do robô."""
        self._mode = self.MODE_POV
        self._pov_robot = player_robot
        self._orbit_active = False
        from engine.render.geometry import grid_to_world
        wp = grid_to_world(player_robot.v_tx, player_robot.v_ty)
        self._pov_cx = wp.getX()
        self._pov_cy = wp.getY()
        self._pov_cz = POV_HEAD_HEIGHT
        self._pov_ch = player_robot.v_h + player_robot.model_offset + 180.0
        self._pov_cp = POV_PITCH
        self._target_fov = 60.0
        self.set_camera_speed('fast')

    def enter_action_selection_mode(self):
        """Câmera de seleção de ação (jackpot): mantém a visão padrão para evitar zoom."""
        self._mode = self.MODE_BATTLE
        self._target_center = Point3(0, 0, 0.4)
        self._target_dist = 13.5
        self._target_heading = 0.0
        self._target_pitch = -30.0
        self._target_fov = 45.0
        self._orbit_active = False
        self.set_camera_speed('normal')

    def enter_battle_mode(self):
        """Visão isométrica de combate."""
        self._mode = self.MODE_BATTLE
        self._target_center = Point3(0, 0, 0.4)
        self._target_dist = CAM_BATTLE_ZOOM_DIST
        self._target_heading = 0.0
        self._target_pitch = -30.0
        self._target_fov = 45.0
        self._orbit_active = False
        self.set_camera_speed('normal')

    def enter_select_mode(self):
        """Modo de seleção: vira 180 graus para não olhar para a arena."""
        self._target_dist = CAM_SELECT_ZOOM_DIST
        self._target_pitch = 0.0
        self._target_heading = 180.0
        self._target_fov = 45.0
        self._orbit_active = True
        self._lerp_dist = 1.8

    def _get_both_robots_wp(self):
        """Retorna as posições world dos dois robôs, se disponíveis."""
        from engine.render.geometry import grid_to_world
        pr = getattr(getattr(self, 'base', None), 'battle', None)
        if pr is None:
            return (None, None)
        p = getattr(pr, 'player_robot', None)
        ia = getattr(pr, 'ia_robot', None)
        if p and ia:
            return (grid_to_world(p.v_tx, p.v_ty), grid_to_world(ia.v_tx, ia.v_ty))
        return (None, None)

    def focus_on_attacker(self, attacker_wp: Point3):
        """Câmera de ação: enquadra atacante com ângulo inclinado, mantendo ambos visíveis."""
        self._mode = self.MODE_ACTION
        wp_p, wp_ia = self._get_both_robots_wp()
        if wp_p and wp_ia:
            mid = (wp_p + wp_ia) * 0.5
            self._target_center = Point3(mid.getX(), mid.getY(), 0.9)
            self._target_dist = 9.5
        else:
            self._target_center = Point3(attacker_wp.getX(), attacker_wp.getY(), 0.9)
            self._target_dist = 9.5
        self._target_heading = 35.0
        self._target_pitch = -18.0
        self._target_fov = 46.0
        self._orbit_active = False
        self.set_camera_speed('fast')
        self._fov_kick = 2.0

    def focus_on_target(self, target_wp: Point3):
        """Câmera de impacto: enquadra ambos com ângulo oposto ao do atacante."""
        self._mode = self.MODE_ACTION
        wp_p, wp_ia = self._get_both_robots_wp()
        if wp_p and wp_ia:
            mid = (wp_p + wp_ia) * 0.5
            self._target_center = Point3(mid.getX(), mid.getY(), 0.9)
            self._target_dist = 9.0
        else:
            self._target_center = Point3(target_wp.getX(), target_wp.getY(), 0.9)
            self._target_dist = 9.0
        self._target_heading = -35.0
        self._target_pitch = -18.0
        self._target_fov = 46.0
        self._orbit_active = False
        self.set_camera_speed('fast')

    def side_view_both(self, p1: Point3, p2: Point3, zoom_dist: float=14.0):
        """Posiciona a câmera lateralmente enquadrando ambos os robôs."""
        self._mode = self.MODE_ACTION
        midpoint = (p1 + p2) * 0.5
        self._target_center = Point3(midpoint.getX(), midpoint.getY(), 0.8)
        self._target_dist = zoom_dist - 1.0
        self._target_heading = 90.0
        self._target_pitch = -16.0
        self._target_fov = 52.0
        self._orbit_active = False
        self.set_camera_speed('normal')

    def enter_pov_mode(self, player_robot, enemy_robot=None):
        """Câmera first-person com transição suave."""
        self._mode = self.MODE_POV
        self._pov_target_robot = player_robot
        self._pov_enemy_robot = enemy_robot
        self._orbit_active = False
        self._target_fov = 75.0
        self._fov = 75.0
        self._pov_cx = self.camera.getX()
        self._pov_cy = self.camera.getY()
        self._pov_cz = self.camera.getZ()
        self._pov_ch = self.camera.getH()
        self._pov_cp = self.camera.getP()

    def focus_on_boss(self, boss_wp: Point3):
        """Câmera de boss: enquadra ambos os robôs com foco no lado do boss."""
        self._mode = self.MODE_ACTION
        wp_p, wp_ia = self._get_both_robots_wp()
        if wp_p and wp_ia:
            mid = (wp_p + wp_ia) * 0.5
            self._target_center = Point3(mid.getX(), mid.getY(), 0.9)
            self._target_dist = 11.0
        else:
            self._target_center = Point3(boss_wp.getX(), boss_wp.getY(), 0.9)
            self._target_dist = 11.0
        self._target_heading = 0.0
        self._target_pitch = -20.0
        self._target_fov = 48.0
        self._orbit_active = False
        self.set_camera_speed('fast')

    def enter_orbit_mode(self, robot_a, robot_b, orbit_speed: float=55.0):
        """Órbita cinemática lateral ao redor de dois robôs com transição suave."""
        self._mode = self.MODE_ORBIT
        self._orbit_robot_a = robot_a
        self._orbit_robot_b = robot_b
        self._orbit_speed_dyn = orbit_speed
        self._orbit_active = False
        self._mode_timer = 0.0
        from engine.render.geometry import grid_to_world
        pa = grid_to_world(robot_a.v_tx, robot_a.v_ty)
        pb = grid_to_world(robot_b.v_tx, robot_b.v_ty)
        mid_x = (pa.getX() + pb.getX()) / 2
        mid_y = (pa.getY() + pb.getY()) / 2
        self._target_center = Point3(mid_x, mid_y, 0.9)
        curr_h = self._heading
        diff_90 = abs((curr_h - 90.0 + 180) % 360 - 180)
        diff_270 = abs((curr_h + 90.0 + 180) % 360 - 180)
        self._orbit_start_heading = 90.0 if diff_90 < diff_270 else -90.0
        self._target_dist = 13.0
        self._target_heading = self._orbit_start_heading
        self._target_pitch = -16.0
        self._target_fov = 54.0
        self.set_camera_speed('fast')

    def reset_to_battle_view(self):
        self.enter_battle_mode()

    def update_tail_chase(self, dt, shake_x, shake_y, shake_z, shake_h, shake_p, shake_r, shake_fov, drift_x, drift_y, drift_z, drift_h, drift_p, drift_r):
        robot = getattr(self, '_tail_robot', None)
        if robot:
            from engine.render.geometry import grid_to_world
            lens = getattr(self.base, 'camLens', None)
            vh_rad = math.radians(robot.v_h + robot.model_offset)
            fwd_x = -math.sin(vh_rad) * TAIL_POV_FORWARD
            fwd_y = math.cos(vh_rad) * TAIL_POV_FORWARD
            wp = grid_to_world(robot.v_tx, robot.v_ty)
            target_x = wp.getX() + fwd_x
            target_y = wp.getY() + fwd_y
            target_z = TAIL_POV_HEIGHT
            target_h = robot.v_h + robot.model_offset + 180.0
            lf = min(1.0, TAIL_CAM_LERP * dt)
            self._tail_cx += (target_x - self._tail_cx) * lf
            self._tail_cy += (target_y - self._tail_cy) * lf
            self._tail_cz += (target_z - self._tail_cz) * lf
            dh_tail = target_h - self._tail_ch
            while dh_tail > 180:
                dh_tail -= 360
            while dh_tail < -180:
                dh_tail += 360
            self._tail_ch += dh_tail * lf
            self._tail_cp += (TAIL_POV_PITCH - self._tail_cp) * lf
            self.camera.setPos(self._tail_cx + shake_x * 0.2 + drift_x * 0.1, self._tail_cy + shake_y * 0.2 + drift_y * 0.1, self._tail_cz + shake_z * 0.1)
            self.camera.setHpr(self._tail_ch + shake_h * 0.3 + drift_h * 0.15, self._tail_cp + shake_p * 0.3 + drift_p * 0.1, shake_r * 0.25 + drift_r * 0.15)
            if lens:
                final_fov = TAIL_CAM_FOV + self._fov_kick + shake_fov * 0.4
                lens.setFov(max(45.0, min(85.0, final_fov)))

    def update_pov(self, dt, shake_x, shake_y, shake_z, shake_h, shake_p, shake_r, shake_fov, drift_x, drift_y, drift_z, drift_h, drift_p, drift_r):
        robot = getattr(self, '_pov_target_robot', None)
        if robot:
            from engine.render.geometry import grid_to_world
            lens = getattr(self.base, 'camLens', None)
            wp = grid_to_world(robot.v_tx, robot.v_ty)
            stable_h = getattr(robot, 'heading_to_boss', 180.0)
            vh_rad = math.radians(stable_h + robot.model_offset)
            back_x = -math.sin(vh_rad) * POV_OFFSET_BACK
            back_y = math.cos(vh_rad) * POV_OFFSET_BACK
            target_x = wp.getX() + back_x
            target_y = wp.getY() + back_y
            target_z = wp.getZ() + POV_HEAD_HEIGHT + POV_OFFSET_UP + 0.8
            enemy = getattr(self, '_pov_enemy_robot', None)
            if enemy:
                ewp = grid_to_world(enemy.v_tx, enemy.v_ty)
                enemy_head_z = ewp.getZ() + getattr(enemy, 'POV_HEAD_HEIGHT', 1.2)
                dx = ewp.getX() - target_x
                dy = ewp.getY() - target_y
                dz = enemy_head_z - target_z
                target_h = math.degrees(math.atan2(dx, dy)) % 360.0
                dist_2d = math.sqrt(dx * dx + dy * dy)
                target_p = math.degrees(math.atan2(dz, dist_2d))
            else:
                target_h = stable_h + robot.model_offset + 180.0
                target_p = POV_PITCH
            if not hasattr(self, '_pov_cx'):
                self._pov_cx = target_x
                self._pov_cy = target_y
                self._pov_cz = target_z
                self._pov_ch = target_h
                self._pov_cp = target_p
            lf = min(1.0, POV_LERP_SPEED * dt)
            self._pov_cx += (target_x - self._pov_cx) * lf
            self._pov_cy += (target_y - self._pov_cy) * lf
            self._pov_cz += (target_z - self._pov_cz) * lf
            dh = target_h - self._pov_ch
            while dh > 180:
                dh -= 360
            while dh < -180:
                dh += 360
            self._pov_ch += dh * lf
            self._pov_cp += (target_p - self._pov_cp) * lf
            self.camera.setPos(self._pov_cx + shake_x * 0.25 + drift_x * 0.15, self._pov_cy + shake_y * 0.25 + drift_y * 0.15, self._pov_cz + shake_z * 0.15)
            self.camera.setHpr(self._pov_ch + shake_h * 0.35 + drift_h * 0.25, self._pov_cp + shake_p * 0.35 + drift_p * 0.2, shake_r * 0.35 + drift_r * 0.2)
            if lens:
                final_fov = self._target_fov + self._fov_kick + shake_fov * 0.5
                lens.setFov(max(50.0, min(90.0, final_fov)))

    def enter_diagonal_view(self, attacker_wp, target_wp):
        """Modo ação diagonal dramático — sempre enquadra ambos os robôs."""
        self._mode = self.MODE_ACTION
        wp_p, wp_ia = self._get_both_robots_wp()
        if wp_p and wp_ia:
            mid = (wp_p + wp_ia) * 0.5
        else:
            mid = (attacker_wp + target_wp) * 0.5
        self._target_center = Point3(mid.getX(), mid.getY(), 0.9)
        self._target_dist = 10.5
        self._target_heading = 45.0
        self._target_pitch = -22.0
        self._target_fov = 50.0
        self._orbit_active = False
        self.set_camera_speed('fast')

    def enter_sky_view(self, target_wp):
        """Modo sky view — sempre enquadra ambos os robôs de cima."""
        self._mode = self.MODE_ACTION
        wp_p, wp_ia = self._get_both_robots_wp()
        if wp_p and wp_ia:
            mid = (wp_p + wp_ia) * 0.5
            self._target_center = Point3(mid.getX(), mid.getY(), 0.5)
        else:
            self._target_center = Point3(target_wp.getX(), target_wp.getY(), 0.5)
        self._target_dist = 13.0
        self._target_heading = 90.0
        self._target_pitch = -60.0
        self._target_fov = 56.0
        self._orbit_active = False
        self.set_camera_speed('fast')
