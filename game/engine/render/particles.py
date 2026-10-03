# visuals/particles.py — sistema de partículas 3D simples
import random
import math
from settings import ROBOT_BOX_SCALE
from engine.render.geometry import lc, grid_to_world


class Particle3D:
    def __init__(self, render, loader, wx: float, wy: float, color):
        ang = random.uniform(0, math.tau)
        spd = random.uniform(1.5, 4.5)
        self.vx  = math.cos(ang) * spd
        self.vy  = math.sin(ang) * spd
        self.vz  = random.uniform(2.0, 5.0)
        self.wx  = float(wx)
        self.wy  = float(wy)
        self.wz  = ROBOT_BOX_SCALE[2] * 0.5
        self.life     = random.uniform(0.4, 0.9)
        self.max_life = self.life

        self.node = loader.loadModel("models/misc/rgbCube")
        if self.node and not self.node.isEmpty():
            self.node.reparentTo(render)
            s = random.uniform(0.05, 0.15)
            self.node.setScale(s, s, s)
            self.node.setColor(lc(*color))
            self._update_pos()

    def _update_pos(self):
        if self.node and not self.node.isEmpty():
            pos = grid_to_world(self.wx, self.wy)
            self.node.setPos(pos.getX() + self.vx * 0.01,
                             pos.getY() + self.vy * 0.01,
                             self.wz)

    def update(self, dt: float) -> bool:
        self.life -= dt
        if self.life <= 0:
            if self.node and not self.node.isEmpty():
                self.node.removeNode()
            return False
        self.vz  -= 9.8 * dt
        self.wz  += self.vz * dt
        self.wx  += self.vx * dt * 0.3
        self.wy  += self.vy * dt * 0.3
        t = self.life / self.max_life
        if self.node and not self.node.isEmpty():
            pos = grid_to_world(self.wx, self.wy)
            self.node.setPos(pos.getX(), pos.getY(), self.wz)
            s = t * random.uniform(0.05, 0.15)
            self.node.setScale(max(0.01, s), max(0.01, s), max(0.01, s))
        return True


class PowerUpParticle3D:
    def __init__(self, render, loader, wx: float, wy: float, color):
        self.vx  = random.uniform(-0.15, 0.15)
        self.vy  = random.uniform(-0.15, 0.15)
        self.vz  = random.uniform(1.6, 2.8)  # Constant upward speed
        self.wx  = float(wx) + random.uniform(-0.3, 0.3)
        self.wy  = float(wy) + random.uniform(-0.3, 0.3)
        self.wz  = random.uniform(0.1, 0.4)  # Start near base of robot
        self.life     = random.uniform(0.7, 1.4)
        self.max_life = self.life

        self.node = loader.loadModel("models/misc/rgbCube")
        if self.node and not self.node.isEmpty():
            self.node.reparentTo(render)
            s = random.uniform(0.035, 0.08)
            self.node.setScale(s, s, s)
            self.node.setColor(lc(*color))
            self._update_pos()

    def _update_pos(self):
        if self.node and not self.node.isEmpty():
            pos = grid_to_world(self.wx, self.wy)
            self.node.setPos(pos.getX(), pos.getY(), self.wz)

    def update(self, dt: float) -> bool:
        self.life -= dt
        if self.life <= 0:
            if self.node and not self.node.isEmpty():
                self.node.removeNode()
            return False
        # Move up (constant upward speed, no gravity decay)
        self.wz  += self.vz * dt
        self.wx  += self.vx * dt
        self.wy  += self.vy * dt
        t = self.life / self.max_life
        if self.node and not self.node.isEmpty():
            pos = grid_to_world(self.wx, self.wy)
            self.node.setPos(pos.getX(), pos.getY(), self.wz)
            s = t * random.uniform(0.035, 0.08)
            self.node.setScale(max(0.01, s), max(0.01, s), max(0.01, s))
        return True
