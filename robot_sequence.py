import asyncio
import time

# robot_sequence.py — Arquivo de Sequência de Movimento Robótico Assíncrono
# -----------------------------------------------------------------------------
# Altere as linhas abaixo para programar a ordem e os parâmetros de cada movimento.
# Qualquer alteração salva neste arquivo é recarregada dinamicamente pelo sistema!

async def run_sequence(db, pen):
    """
    Sua sequência assíncrona de comandos.
    Escreva os comandos em ordem com 'await':
    """
    await asyncio.sleep(45)
    print("[RobotSequence] Passo 1: Avançando 1 tile para frente (W)...")
    await db.move_forward(tiles=1.0)

    print("[RobotSequence] Passo 2: Girando 90 graus para a direita (TURN_RIGHT)...")
    await db.turn_right(degrees=90.0)

    print("[RobotSequence] Passo 3: Recuando 1 tile para trás / dando ré (S)...")
    await db.move_backward(tiles=1.0)
