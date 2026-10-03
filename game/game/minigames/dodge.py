# game/minigames/dodge/minigame.py
# ═══════════════════════════════════════════════════════════════════════
# Dodge/Evade Minigame — Cleaned state holder for Qt-side rendering.
# ═══════════════════════════════════════════════════════════════════════

class DodgeMinigame:
    def __init__(self, base_app, battle):
        self.base = base_app
        self.battle = battle

    def build(self, attack_dir):
        pass

    def update_colors(self, attack_dir, intro_active):
        pass

    def clear(self):
        pass

    @staticmethod
    async def main_act(robot, target, ability, final_damage, camera, ctx):
        from game.champions.robot_base import DB_MOV, PL_MOV, DB_TURN, PL_TURN, WAIT_MOV, DELAY, DB_ATTACK, PL_ATTACK, ENVOLTO, _get_robots_from_ctx
        
        db, pl = _get_robots_from_ctx(ctx)
        
        player_mov = DB_MOV if target == db else PL_MOV
        boss_mov = DB_MOV if robot == db else PL_MOV
        player_turn = DB_TURN if target == db else PL_TURN
        boss_turn = DB_TURN if robot == db else PL_TURN
        boss_attack = DB_ATTACK if robot == db else PL_ATTACK

        def op_dir(d):
            return "ESQUERDA" if d == "DIREITA" else "DIREITA"

        # Lado da esquiva do Player capturado pelo rosto/webcam ("left" ou "right")
        raw_choice = getattr(ctx, "minigame_choice", None)
        if raw_choice in ("left", "esquerda"):
            p_screen_side = "left"
        elif raw_choice in ("right", "direita"):
            p_screen_side = "right"
        else:
            p_screen_side = None

        # Lado do ataque escolhido pela IA do Boss ("left" ou "right")
        boss_choice = getattr(ctx, "minigame_attack_dir", "left")
        raw_b_side = "left" if boss_choice in ("left", "esquerda") else "right"

        if p_screen_side is None:
            p_screen_side = raw_b_side

        # Regra do Giro do Boss:
        # Quando o player ACERTA o lado para desviar (p_screen_side != raw_b_side), o boss vira para o OUTRO lado (b_screen_side = raw_b_side).
        # Se o player ERRA o lado (p_screen_side == raw_b_side), o boss vira para a MESMA direção do player (b_screen_side = p_screen_side).
        if p_screen_side != raw_b_side:
            b_screen_side = raw_b_side
        else:
            b_screen_side = p_screen_side

        # Mapeamento estrito para os comandos de giro relativos virarem para os lados corretos na tela:
        # Player (virado a 180° / para cima): para ir para a esquerda da tela (h=270°), usa "DIREITA". Para a direita da tela (h=90°), usa "ESQUERDA".
        p_turn_cmd = "DIREITA" if p_screen_side == "left" else "ESQUERDA"

        # Boss (virado a 0° / para baixo): para ir para a esquerda da tela (h=270°), usa "ESQUERDA". Para a direita da tela (h=90°), usa "DIREITA".
        b_turn_cmd = "ESQUERDA" if b_screen_side == "left" else "DIREITA"

        # ── 1. GIRO 90° PARA AS FAIXAS LATERAIS (ENVOLVIDO) ──
        await ENVOLTO(
            player_turn(ctx, p_turn_cmd, speed=180),
            boss_turn(ctx, b_turn_cmd)
        )

        # ── 2. ANDAR 1 TILE FRENTE PARA AS COLUNAS LATERAIS (ENVOLVIDO) ──
        await ENVOLTO(
            player_mov(ctx, "FRENTE", 1, speed=180),
            boss_mov(ctx, "FRENTE", 1)
        )

        # ── 3. VIRAR 90° OLHANDO DE FRENTE UM PARA O OUTRO (ENVOLVIDO) ──
        await ENVOLTO(
            player_turn(ctx, op_dir(p_turn_cmd), speed=180),
            boss_turn(ctx, op_dir(b_turn_cmd))
        )

        # ── 4. BOSS AVANÇA 2 TILES FRENTE ──
        await boss_mov(ctx, "FRENTE", 2)
        await WAIT_MOV()

        # ── 5. ATAQUE DO BOSS E RECUO POR 2 TILES ──
        await boss_attack(ctx, final_damage)
        await boss_mov(ctx, "TRAS", 2)
        await WAIT_MOV()

        # ── 6. AMBOS GIRAM 90° EM SENTIDO AO CENTRO DO PALCO (ENVOLVIDO) ──
        await ENVOLTO(
            player_turn(ctx, op_dir(p_turn_cmd), speed=180),
            boss_turn(ctx, op_dir(b_turn_cmd))
        )

        # ── 7. AMBOS ANDAM 1 TILE FRENTE PARA O CENTRO (ENVOLVIDO) ──
        await ENVOLTO(
            player_mov(ctx, "FRENTE", 1, speed=180),
            boss_mov(ctx, "FRENTE", 1)
        )

        # ── 8. AMBOS GIRAM 90° PARA FICAR FRENTE A FRENTE DE NOVO (ENVOLVIDO) ──
        await ENVOLTO(
            player_turn(ctx, p_turn_cmd, speed=180),
            boss_turn(ctx, b_turn_cmd)
        )

        return True
