import json
import os
from typing import List, Dict, Any, Optional

class SlideConfig:
    def __init__(self, data: Dict[str, Any], default_wait_next: float = 5.0, default_order: int = 0):
        self.id: str = data.get("id", "slide_unknown")
        self.type: str = data.get("type", "html")
        self.wait_next: float = float(data.get("wait_next", data.get("duration", default_wait_next)))
        self.order: int = int(data.get("order", default_order))
        self.title: str = data.get("title", "")
        self.raw_data: Dict[str, Any] = data

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw_data.get(key, default)

class PresentationConfig:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.title = "Apresentação SlideEngine"
        self.loop = True
        self.default_wait_next = 5.0
        self.slides: List[SlideConfig] = []
        self.load()

    def load(self):
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"Arquivo de sequência não encontrado: {self.filepath}")

        with open(self.filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.title = data.get("title", self.title)
        self.loop = bool(data.get("loop", True))
        self.default_wait_next = float(data.get("default_wait_next", data.get("default_duration", 5.0)))

        raw_slides = data.get("slides", [])
        # Sort slides explicitly by 'order' attribute (or maintain position order)
        sorted_raw = sorted(enumerate(raw_slides), key=lambda item: (item[1].get("order", item[0] + 1), item[0]))
        self.slides = [SlideConfig(s, self.default_wait_next, default_order=idx+1) for idx, s in sorted_raw]

    def get_slide(self, index: int) -> Optional[SlideConfig]:
        if 0 <= index < len(self.slides):
            return self.slides[index]
        return None

