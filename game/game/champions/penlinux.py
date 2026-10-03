# ==============================================================================
# PenLinux Robot Kit
# ==============================================================================
# How to add or edit abilities:
# 1. Add the method string in `ATTACKS`.
# 2. Define metadata in the `ATTACK_META` dict (damage, energy, status, etc.).
# 3. Implement the corresponding async function using movement helpers:
#    - `self.turn(degrees, speed)`: Rotates the robot.
#    - `self.move_cm(cm, speed)`: Moves the robot in cm (54cm = 1 tile).
#    - `self.distance_to(target)`: Returns distance in cm to the other robot.
#    - `self.angle_to(target)`: Returns the absolute angle to face the other robot.
# ==============================================================================

from game.champions.robot_base import RobotBase
from settings import C_CYAN
from typing import Any

class PenLinuxRobot(RobotBase):
    """PenLinux champion configuration and skill execution sequences."""
    
    # Visual interpolation speed (lerp weight per frame)
    MOVE_SPEED = 0.002

    # Maximum physical speeds for actions (when speed = 255)
    MOVE_SPEED_MAX_CM_S = 70.0
    TURN_SPEED_MAX_DEG_S = 90.0
    PENLINUX_SPIN_SPEED = 70.0  # Spin speed for win/fail sequence (degrees/s)

    ATTACKS = ["attack_dance_night", "attack_frost_barrier", "attack_symphony_wave"]
    ATTACK_META = {
        "attack_dance_night": {
            "name": "Dance Night",
            "damage": 16,
            "triggers_minigame": True,
            "description": ["DANCE NIGHT", "16 dmg", "Minigame de ritmo/danca"],
        },
        "attack_frost_barrier": {
            "name": "Escudo de Gelo",
            "damage": 18,
            "triggers_minigame": True,
            "description": ["ESCUDO DE GELO", "18 dmg", "Barreira 3D e núcleos de gelo"],
        },
        "attack_symphony_wave": {
            "name": "Notas Musicais",
            "damage": 20,
            "triggers_minigame": True,
            "description": ["NOTAS MUSICAIS", "20 dmg", "Rastreio de cabeça CV e faixas"],
        },
    }

    async def attack_dance_night(self, target, ability, final_damage, camera, ctx):
        from game.combat.battle_logic import wait_seconds
        from settings import SHAKE_HEAVY

        if self.is_player:
            from game.minigames.dance_night import execute_dance_night_attack
            await execute_dance_night_attack(self, target, ability, final_damage, camera, ctx)
            await wait_seconds(1.0)
        else:
            await self._execute_boss_vector_charge(target, ability, final_damage, camera, ctx, spin_duration=0.0, shake_level=SHAKE_HEAVY)
            await wait_seconds(1.0)

    async def attack_frost_barrier(self, target, ability, final_damage, camera, ctx):
        from game.combat.battle_logic import wait_seconds
        from settings import SHAKE_HEAVY

        if self.is_player:
            from game.minigames.frost_barrier import execute_frost_barrier_attack
            await execute_frost_barrier_attack(self, target, ability, final_damage, camera, ctx)
            await wait_seconds(1.0)
        else:
            await self._execute_boss_vector_charge(target, ability, final_damage, camera, ctx, spin_duration=0.0, shake_level=SHAKE_HEAVY)
            await wait_seconds(1.0)

    async def attack_symphony_wave(self, target, ability, final_damage, camera, ctx):
        from game.combat.battle_logic import wait_seconds
        from settings import SHAKE_HEAVY

        if self.is_player:
            from game.minigames.symphony_wave import execute_symphony_wave_attack
            await execute_symphony_wave_attack(self, target, ability, final_damage, camera, ctx)
            await wait_seconds(1.0)
        else:
            await self._execute_boss_vector_charge(target, ability, final_damage, camera, ctx, spin_duration=0.0, shake_level=SHAKE_HEAVY)
            await wait_seconds(1.0)
