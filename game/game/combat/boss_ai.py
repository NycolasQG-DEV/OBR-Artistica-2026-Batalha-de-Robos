import random

def choose_boss_action(boss, player, battle_state):
    # boss and player are RobotBase instances
    # battle_state is BattleLogic instance
    
    attacks = [(f"atk{i}", ability) for i, ability in enumerate(boss.abilities)]
    if not attacks:
        return {"attack": "atk0"}

    # Rastreia minijogos do robô IA para garantir ciclo sem repetições
    if hasattr(boss, "get_next_available_attack"):
        num_attacks = len(attacks)
        available_keys = [f"atk{i}" for i in range(num_attacks)]
        used_keys = getattr(boss, "used_attack_keys", [])
        remaining_keys = [k for k in available_keys if k not in used_keys]

        if not remaining_keys:
            boss.used_attack_keys = []
            remaining_keys = list(available_keys)
            last_used = getattr(boss, "last_used_attack_key", None)
            if last_used and len(remaining_keys) > 1 and last_used in remaining_keys:
                filtered = [k for k in remaining_keys if k != last_used]
                if filtered:
                    remaining_keys = filtered

        remaining_attacks = [pair for pair in attacks if pair[0] in remaining_keys]
        if not remaining_attacks:
            remaining_attacks = attacks

        weights = []
        for key, ability in remaining_attacks:
            weight = ability.damage
            if player and hasattr(player, "hp") and player.hp <= ability.damage:
                weight *= 3.0
            weights.append(weight)

        chosen_key, chosen_ability = random.choices(remaining_attacks, weights=weights, k=1)[0]
        boss.record_attack_used(chosen_key)
        return {"attack": chosen_key}

    # Fallback genérico caso boss não seja RobotBase
    weights = []
    for key, ability in attacks:
        weight = ability.damage
        if player and hasattr(player, "hp") and player.hp <= ability.damage:
            weight *= 3.0
        weights.append(weight)
        
    chosen_key, chosen_ability = random.choices(attacks, weights=weights, k=1)[0]
    return {"attack": chosen_key}
