from game.champions.dinobyte import DinoByteRobot
from game.champions.penlinux import PenLinuxRobot

ROBOT_REGISTRY = {
    "DinoByte": DinoByteRobot,
    "PenLinux": PenLinuxRobot
}

def get_robot_class(name_code: str):
    return ROBOT_REGISTRY.get(name_code, DinoByteRobot)
