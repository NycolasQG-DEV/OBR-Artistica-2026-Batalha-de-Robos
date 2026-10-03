# ==============================================================================
# DinoByte Robot Kit
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

import math
from game.champions.robot_base import RobotBase
from settings import C_ORANGE
from typing import Any

class DinoByteRobot(RobotBase):
    """DinoByte champion configuration and skill execution sequences."""
    
    # Visual interpolation speed (lerp weight per frame)
    MOVE_SPEED = 0.002

    # Maximum physical speeds for actions (when speed = 255: 2.7m in 4.5s = 60.0 cm/s)
    MOVE_SPEED_MAX_CM_S = 60.0
    TURN_SPEED_MAX_DEG_S = 70.0

    ATTACKS = ["attack_jurassic_bite", "attack_tail_quake", "attack_meteor_stomp"]
    ATTACK_META = {
        "attack_jurassic_bite": {
            "name": "Mordida Jurássica",
            "damage": 16,
            "triggers_minigame": True,
            "description": ["MORDIDA JURÁSSICA", "16 dmg", "Mãos: morder as presas"],
        },
        "attack_tail_quake": {
            "name": "Sucção Jurássica",
            "damage": 18,
            "triggers_minigame": False,
            "description": ["SUCÇÃO JURÁSSICA", "18 dmg", "Cabeça: sugar orbes"],
        },
        "attack_meteor_stomp": {
            "name": "Meteor Stomp",
            "damage": 20,
            "triggers_minigame": True,
            "description": ["METEOR STOMP", "20 dmg", "Cabeça: coletar meteoros"],
        }
    }

    async def attack_jurassic_bite(self, target, ability, final_damage, camera, ctx):
        from game.combat.battle_logic import wait_seconds
        from settings import SHAKE_MEDIUM

        if self.is_player:
            from game.minigames.target_aim import execute_jurassic_bite_attack
            await execute_jurassic_bite_attack(self, target, ability, final_damage, camera, ctx)
            if camera:
                camera.reset_to_battle_view()
            await wait_seconds(1.0)
        else:
            await self._execute_boss_vector_charge(target, ability, final_damage, camera, ctx, spin_duration=1.2, shake_level=SHAKE_MEDIUM)

    async def attack_tail_quake(self, target, ability, final_damage, camera, ctx):
        from game.combat.battle_logic import wait_seconds
        from settings import SHAKE_HEAVY, C_ORANGE
        if self.is_player:
            from game.minigames.tail_quake import execute_tail_quake_attack
            await execute_tail_quake_attack(self, target, ability, final_damage, camera, ctx)
            if camera:
                camera.reset_to_battle_view()
            await wait_seconds(1.0)
        else:
            await self._execute_boss_vector_charge(target, ability, final_damage, camera, ctx, spin_duration=0.0, shake_level=SHAKE_HEAVY)

    async def attack_meteor_stomp(self, target, ability, final_damage, camera, ctx):
        from game.combat.battle_logic import wait_seconds
        from settings import SHAKE_HEAVY
        if self.is_player:
            from game.minigames.meteor_stomp import execute_meteor_stomp_attack
            await execute_meteor_stomp_attack(self, target, ability, final_damage, camera, ctx)
            if camera:
                camera.reset_to_battle_view()
            await wait_seconds(1.0)
        else:
            await self._execute_boss_vector_charge(target, ability, final_damage, camera, ctx, spin_duration=0.0, shake_level=SHAKE_HEAVY)
