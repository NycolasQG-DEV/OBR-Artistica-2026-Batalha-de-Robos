import math
import random
import time
from engine import app_core as app
from settings import SHAKE_HEAVY, C_ORANGE
from engine.render.geometry import create_clean_cube, grid_to_world, normalize_angle_deg
from panda3d.core import GeomNode, LColor, Material, TransparencyAttrib, ClockObject, Point3, CardMaker  # type: ignore
from PySide6.QtCore import QPoint, QPropertyAnimation
from game.combat.battle_logic import _tick, wait_seconds
from game.champions.robot_base import DB_MOV, PL_MOV, DB_TURN, PL_TURN, WAIT_MOV, DELAY, DB_ATTACK, PL_ATTACK, GET_CHOICE

class TailQuakeMinigame:
    @staticmethod
    async def run(robot, target, ability, final_damage, camera, ctx):
        await execute_tail_quake_attack(robot, target, ability, final_damage, camera, ctx)

async def execute_tail_quake_attack(robot, target, ability, final_damage, camera, ctx):
    app.game_instance.battle.tail_minigame_active = True
    
    # Registra a orientação inicial do robô (olhando reto a 0° para o oponente)
    _original_h = robot.v_h

    # Dino-Byte avança apenas 1 tile antes do minigame
    await DB_MOV(ctx, "FRENTE", 1)
    await WAIT_MOV()

    # Cria o vórtex de sucção
    tornado = app.game_instance.render.attachNewNode("suction_tornado")
    tornado.setTransparency(TransparencyAttrib.MAlpha)
    
    cm = CardMaker("wind_slice")
    cm.setFrame(-0.5, 0.5, -0.5, 0.5)
    layers = []
    num_layers = 15
    for i in range(num_layers):
        layer = tornado.attachNewNode(f"layer_{i}")
        card1 = layer.attachNewNode(cm.generate())
        card2 = layer.attachNewNode(cm.generate())
        card2.setR(45) # Rotaciona no próprio plano para formar uma estrela/círculo
        # Deixa no plano XZ (padrão) e move em Y (frente) para formar o tubo
        y_offset = (i / num_layers) * 4.0
        layer.setY(y_offset)
        scale_val = 0.3 + (i / num_layers) * 1.5
        layer.setScale(scale_val, scale_val, 0.3)
        color_val = LColor(0.2, 0.6, 1.0, 0.4 - (i / num_layers) * 0.2)
        card1.setColor(color_val)
        card2.setColor(color_val)
        rot_dir = 1.0 if i % 2 == 0 else -1.0
        rot_speed = 360.0 + i * 50.0
        layers.append({"node": layer, "rot_dir": rot_dir, "rot_speed": rot_speed})

    # Inicializa posição do tornado (na altura da boca, Z=1.0)
    p_robot = grid_to_world(robot.v_tx, robot.v_ty)
    tornado.setPos(p_robot.getX(), p_robot.getY(), 1.0)
    tornado.setH(robot.v_h)

    # Spawn orbs coming from both left and right
    orb_geom = create_clean_cube(0.45, 0.45, 0.45)
    neon_mat = Material("neon_material")
    neon_mat.setEmission(LColor(0.2, 0.8, 1.0, 1.0))
    neon_mat.setAmbient(LColor(0.2, 0.8, 1.0, 1.0))
    neon_mat.setDiffuse(LColor(0.2, 0.8, 1.0, 1.0))
    neon_mat.setShininess(120.0)

    orb_nodes = []
    num_orbs = 16
    for i in range(num_orbs):
        # Intercala os lados e aumenta ainda mais o espaçamento
        side = "left" if i % 2 == 0 else "right"
        start_row = -2.0 - i * 3.5
        col = 0.5 if side == "left" else 3.5
        pos = grid_to_world(col, start_row)
        
        gnode = GeomNode(f"energy_orb_{i}")
        gnode.addGeom(orb_geom)
        np_node = app.game_instance.render.attachNewNode(gnode)
        np_node.setColor(LColor(0.2, 0.8, 1.0, 1.0))
        np_node.setMaterial(neon_mat)
        np_node.setLightOff()
        np_node.setPos(pos.getX(), pos.getY(), 0.5)
        
        orb_nodes.append({
            "col": col,
            "row": start_row,
            "np": np_node,
            "alive": True,
            "side": side,
            "sucking": False
        })

    # Setup Fullscreen Webcam overlay
    if app.game_instance and app.game_instance.qt_win:
        qt_win = app.game_instance.qt_win
        qt_win.minigame_instruction_overlay.lbl_instruction.setText(
            "SUCÇÃO JURÁSSICA!\nVIRE A CABEÇA PARA SUGAR ORBES!"
        )
        geom = qt_win.panda_container.geometry()
        origin = qt_win.panda_container.mapToGlobal(QPoint(0, 0))
        vw = geom.width()
        vh = geom.height()
        qt_win.minigame_instruction_overlay.setGeometry(origin.x(), origin.y(), vw, vh)
        qt_win.minigame_instruction_overlay.setWindowOpacity(0.0)
        qt_win.minigame_instruction_overlay.show()
        qt_win.minigame_instruction_overlay.raise_()

        # Fade in
        qt_win._fade_inst_anim = QPropertyAnimation(qt_win.minigame_instruction_overlay, b"windowOpacity")
        qt_win._fade_inst_anim.setDuration(400)
        qt_win._fade_inst_anim.setStartValue(0.0)
        qt_win._fade_inst_anim.setEndValue(1.0)
        qt_win._fade_inst_anim.start()

        # Configura o fullscreen mode patcheado
        qt_win.set_webcam_mode("fullscreen")
        app.game_instance._webcam_mode = "fullscreen"

    if app.game_instance.cv_input:
        app.game_instance.cv_input.face_detection_enabled = True

    globalClock = ClockObject.getGlobalClock()
    start_time = time.time()
    has_faded_out_overlay = False
    
    minigame_duration = 10.0 
    orbs_collected = 0
    current_angle_state = 0.0  # Ângulo relativo discreto atual: -45.0 (esquerda), 0.0 (centro), 45.0 (direita)

    while time.time() - start_time < minigame_duration:
        await _tick()
        dt = globalClock.getDt()
        if dt <= 0.0: dt = 0.01667
        dt = min(dt, 0.05)
        elapsed = time.time() - start_time
        
        # Oculta overlay de instruções após 1.5s
        if elapsed > 1.5 and not has_faded_out_overlay and app.game_instance.qt_win:
            has_faded_out_overlay = True
            qt_win = app.game_instance.qt_win
            qt_win._fade_inst_anim2 = QPropertyAnimation(qt_win.minigame_instruction_overlay, b"windowOpacity")
            qt_win._fade_inst_anim2.setDuration(400)
            qt_win._fade_inst_anim2.setStartValue(1.0)
            qt_win._fade_inst_anim2.setEndValue(0.0)
            qt_win._fade_inst_anim2.start()

        # Anima tornado
        for layer in layers:
            layer["node"].setR(layer["node"].getR() + layer["rot_speed"] * layer["rot_dir"] * dt)
        
        # Controle discreto de direção em 3 zonas (usando landmark padronizado de cabeça)
        game = app.game_instance
        cv = getattr(game, "cv_input", None)
        cursor = getattr(game, "_finger_pos_norm", None)
        if getattr(game, "_input_mode", "cv") == "mouse" and cursor:
            face_x = cursor[0]
        elif cv and hasattr(cv, "get_head_position"):
            face_x, _ = cv.get_head_position()
        else:
            face_x = getattr(cv, "face_x", 0.5) if cv else 0.5
        if face_x is None: face_x = 0.5
        
        # Mapeia a câmera em 3 divisões:
        # face_x < 0.35 (Esquerda da câmera) -> +45.0°
        # face_x > 0.65 (Direita da câmera) -> -45.0°
        if face_x < 0.35:
            target_offset = 45.0   # Giro de +45°
        elif face_x > 0.65:
            target_offset = -45.0  # Giro de -45°
        else:
            target_offset = 0.0    # Reto no centro (0°)

        # Transmite comando de giro por serial APENAS se o ângulo mudar E se a confirmação 'ok' do giro anterior já tiver sido recebida
        if target_offset != current_angle_state:
            try:
                from game.combat.serial_controller import get_serial_controller
                sc = get_serial_controller()
                if sc.is_ok_set(robot):
                    diff_deg = target_offset - current_angle_state
                    sc.write_command(robot, "TURN", diff_deg, 180)
                    current_angle_state = target_offset
            except Exception:
                pass

        # Atualização visual suave do 3D para o ângulo discreto alvo
        target_h = _original_h + current_angle_state
        diff_h = normalize_angle_deg(target_h - robot.v_h)
        robot.v_h += diff_h * 6.0 * dt

        # Determina o lado de sucção baseado no estado de ângulo discreto atual do robô
        suction_side = None
        if current_angle_state > 15.0:
            suction_side = "left"
        elif current_angle_state < -15.0:
            suction_side = "right"
        else:
            suction_side = "center"
        
        p_robot = grid_to_world(robot.v_tx, robot.v_ty)
        tornado.setH(robot.v_h)
        tornado.setPos(p_robot.getX(), p_robot.getY(), 1.0)

        # Move orbs (velocidade desacelerada para ser mais cadenciada e justa)
        if elapsed > 2.0:
            speed = 1.0 + (elapsed * 0.08)  # Velocidade desacelerada para facilitar a jogabilidade
            for orb in orb_nodes:
                if not orb["alive"]: continue
                
                # O fogo azul é coletado APENAS se o robô estiver virado para o lado dele (suction_side estrito)
                is_suction_match = (suction_side == orb["side"])
                if is_suction_match and 0.0 < orb["row"] < 4.0 and not orb["sucking"]:
                    orb["sucking"] = True
                
                if orb["sucking"]:
                    # Atrai para a boca do robô visualmente
                    opos = orb["np"].getPos()
                    p_rob = grid_to_world(robot.v_tx, robot.v_ty)
                    dx = p_rob.getX() - opos.getX()
                    dy = p_rob.getY() - opos.getY()
                    dz = 1.0 - opos.getZ() # A boca fica em Z=1.0
                    
                    dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                    if dist < 0.5:
                        orb["alive"] = False
                        orb["np"].hide()
                        orbs_collected += 1
                        ctx.create_floating(robot.v_tx, robot.v_ty, "+1 ORB!", (0.2, 1.0, 0.2, 1.0))
                    else:
                        suck_speed = 10.0
                        orb["np"].setPos(opos.getX() + (dx/dist)*suck_speed*dt, 
                                         opos.getY() + (dy/dist)*suck_speed*dt, 
                                         opos.getZ() + (dz/dist)*suck_speed*dt)
                else:
                    # Avança normalmente em direção ao robô
                    orb["row"] += speed * dt
                    opos = grid_to_world(orb["col"], orb["row"])
                    orb["np"].setPos(opos.getX(), opos.getY(), 0.5)
                    if orb["row"] > 6.0:
                        orb["alive"] = False
                        orb["np"].hide()

    # Fim do minigame
    app.game_instance.battle.tail_minigame_active = False
    tornado.removeNode()
    for orb in orb_nodes:
        if orb["np"]: orb["np"].removeNode()

    # Para comandos em tempo real soltos
    try:
        from game.combat.serial_controller import get_serial_controller
        get_serial_controller().send_command_realtime(robot, "STOP", 0)
    except Exception:
        pass

    # 1. Espera o último movimento/giro em andamento terminar completamente
    await WAIT_MOV()

    # 2. CONSERTA A ORIENTAÇÃO DO ROBÔ OBRIGATORIAMENTE PARA ANGULO 0° (DE FRENTE PARA O OUTRO ROBÔ)
    if abs(current_angle_state) > 0.1:
        turn_back_deg = -current_angle_state
        current_angle_state = 0.0
        await robot.turn(turn_back_deg)
        await WAIT_MOV()

    diff_align = normalize_angle_deg(_original_h - robot.v_h)
    if abs(diff_align) > 0.1:
        await robot.turn(diff_align)
        await WAIT_MOV()

    robot.v_h = _original_h
    robot.target_h = _original_h

    # Volta a webcam para o modo normal
    if app.game_instance.qt_win:
        app.game_instance.qt_win.set_webcam_mode("normal")
        app.game_instance._webcam_mode = "normal"
        app.game_instance.qt_win.minigame_instruction_overlay.hide()

    # 3. Calcula o dano final e dispara o ataque via bloco DSL de descomplexação
    damage_to_deal = 0
    if orbs_collected > 0:
        damage_to_deal = int(final_damage * (orbs_collected / num_orbs))
        if damage_to_deal < 1: damage_to_deal = 1
        
        ctx.create_floating(target.v_tx, target.v_ty, f"SUCKED {orbs_collected} ORBS!", C_ORANGE, size=1.5)
        
        from game.champions.robot_base import DB_ATTACK, PL_ATTACK
        if robot.name_code.lower() == "dinobyte":
            await DB_ATTACK(ctx, damage_to_deal)
        else:
            await PL_ATTACK(ctx, damage_to_deal)
        await WAIT_MOV()
    else:
        ctx.create_floating(robot.v_tx, robot.v_ty, "FALHA!", (1.0, 0.2, 0.2, 1.0), size=1.5)

    # 4. Dino-Byte recua OBRIGATORIAMENTE o 1 tile que andou no início e confirma a orientação zero (olhando reto)
    await DB_MOV(ctx, "TRAS", 1)
    await WAIT_MOV()

    diff_final = normalize_angle_deg(_original_h - robot.v_h)
    if abs(diff_final) > 0.1:
        await robot.turn(diff_final)
        await WAIT_MOV()

    robot.v_h = _original_h
    robot.target_h = _original_h
