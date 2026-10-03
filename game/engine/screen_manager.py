from engine.base_screen import BaseScreen

class ScreenManager:
    def __init__(self):
        self.screens = {}
        self.current_name = None

    def register(self, name: str, screen: BaseScreen):
        self.screens[name] = screen

    def show(self, name: str):
        if self.current_name == name:
            return
        if self.current_name and self.current_name in self.screens:
            self.screens[self.current_name].on_exit()
        self.current_name = name
        if name in self.screens:
            self.screens[name].on_enter()

    def update(self, dt: float):
        if self.current_name and self.current_name in self.screens:
            screen = self.screens[self.current_name]
            screen.update(dt)
