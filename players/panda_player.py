import sys
import math
from PySide6.QtWidgets import QWidget, QFrame, QSizePolicy
from PySide6.QtCore import Qt, QTimer
from players.base_player import BaseSlidePlayer
from engine.config import SlideConfig

try:
    from panda3d.core import WindowProperties, FrameBufferProperties, GraphicsPipe, GraphicsEngine
    from direct.showbase.ShowBase import ShowBase
    _HAS_PANDA = True
except ImportError:
    _HAS_PANDA = False

class PandaSlidePlayer(BaseSlidePlayer):
    def __init__(self, config: SlideConfig, parent=None):
        super().__init__(config, parent)

        self.panda_container = QFrame(self)
        self.panda_container.setStyleSheet("background-color: #050811; border-radius: 8px;")
        self.panda_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.panda_container)

        self.panda_app = None
        self.cube = None
        self.task = None

    async def prepare(self):
        if not _HAS_PANDA:
            return

        # Initialize embedded Panda3D if not already initialized
        if self.panda_app is None and self.panda_container.winId():
            try:
                self.panda_app = ShowBase(windowType='none')
                self.panda_app.makeDefaultPipe()

                wp = WindowProperties()
                wp.setParentWindow(int(self.panda_container.winId()))
                wp.setOrigin(0, 0)
                wp.setSize(self.panda_container.width() or 800, self.panda_container.height() or 600)

                self.panda_win = self.panda_app.openWindow(props=wp)

                if self.panda_win:
                    # Setup 3D Scene: Rotating Cube / Gem
                    self.cube = self.panda_app.loader.loadModel("models/box")
                    if self.cube:
                        self.cube.reparentTo(self.panda_app.render)
                        self.cube.setScale(1.5)
                        color = self.config.get("cube_color", [0.0, 0.8, 1.0, 1.0])
                        self.cube.setColor(color[0], color[1], color[2], color[3])

                    self.panda_app.cam.setPos(0, -7, 0)
                    self.panda_app.cam.lookAt(0, 0, 0)
            except Exception as e:
                print(f"[PandaSlidePlayer] Erro na inicialização 3D: {e}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if _HAS_PANDA and self.panda_app and hasattr(self, 'panda_win') and self.panda_win:
            try:
                wp = WindowProperties()
                wp.setSize(max(100, self.panda_container.width()), max(100, self.panda_container.height()))
                self.panda_win.requestProperties(wp)
            except Exception as e:
                pass

    async def play(self):
        if self.panda_app:
            speed = float(self.config.get("rotation_speed", 45.0))

            def _spin_task(task):
                if self.cube and self.panda_app:
                    dt = self.panda_app.clock.getDt()
                    self.cube.setHpr(self.cube.getH() + speed * dt, self.cube.getP() + speed * 0.5 * dt, 0)
                    self.panda_app.taskMgr.step()
                return task.cont

            self.task = self.panda_app.taskMgr.add(_spin_task, "SpinCubeTask")

    async def stop(self):
        if self.panda_app and self.task:
            self.panda_app.taskMgr.remove(self.task)
            self.task = None

