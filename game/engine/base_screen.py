class BaseScreen:
    def on_enter(self):
        """Called when transitioning into this screen."""
        pass

    def on_exit(self):
        """Called when transitioning away from this screen."""
        pass

    def update(self, dt: float):
        """Optional frame update called by the game loop."""
        pass
