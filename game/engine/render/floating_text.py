# visuals/floating_text.py — textos 3D flutuantes no espaço da tela
from panda3d.core import Point3, TextNode
from direct.gui.OnscreenText import OnscreenText
from engine.render.geometry import grid_to_world


class FloatingText3D:
    def __init__(self, game, world_x: float, world_y: float,
                 text: str, color, size: float = 0.06):
        self.game    = game
        self.wx      = world_x
        self.wy      = world_y
        self.wz      = 1.5
        self.text    = text
        self.color   = color
        self.life    = 2.0
        self.max_life = 2.0
        self.vy      = 1.2   # unidades/s

        self._label = OnscreenText(
            text=text, pos=(0, 0), scale=size,
            fg=color, shadow=(0, 0, 0, 0.6),
            mayChange=True, align=TextNode.ACenter,
        )

    def update(self, dt: float) -> bool:
        self.life -= dt
        self.wz   += self.vy * dt
        if self.life <= 0:
            self._label.destroy()
            return False

        # Converte coordenadas do grid para o espaço de coordenadas 3D reais
        world_pos = grid_to_world(self.wx, self.wy)
        pos_3d = Point3(world_pos.getX(), world_pos.getY(), self.wz)

        # Import local para evitar import circular com app.py durante a inicialização
        from engine.app_core import game_instance

        # Projeta posição 3D para tela
        try:
            p3 = game_instance.cam.getRelativePoint(
                game_instance.render,
                game_instance.render.getPos() + pos_3d,
            )
        except Exception:
            pass

        # Usar project
        try:
            wp = game_instance.camLens.project(pos_3d - game_instance.camera.getPos())
        except Exception:
            pass

        # Fallback: posiciona usando get2dPoint
        try:
            p  = game_instance.camera.getRelativePoint(
                game_instance.render, pos_3d)
            pp = game_instance.camLens.project(p)
            sx =  pp[0]
            sy =  pp[1]
        except Exception:
            sx, sy = 0, 0

        alpha = (self.life / self.max_life) ** 0.7
        r, g, b, _ = self.color
        self._label.setFg((r, g, b, alpha))
        self._label.setPos(sx, sy)
        return True
