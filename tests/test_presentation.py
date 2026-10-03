import asyncio
import unittest
from pathlib import Path

from engine.config import PresentationConfig
from robot_choose_sequence import run_sequence


ROOT = Path(__file__).resolve().parents[1]


class FakeRobot:
    def __init__(self):
        self.calls = []

    async def play_sfx(self, name):
        self.calls.append(("play_sfx", name))

    async def move_backward(self, tiles):
        self.calls.append(("move_backward", tiles))

    async def turn_left(self, degrees):
        self.calls.append(("turn_left", degrees))

    async def turn_right(self, degrees):
        self.calls.append(("turn_right", degrees))


class PresentationTests(unittest.TestCase):
    def test_sequence_assets_exist(self):
        config = PresentationConfig(str(ROOT / "sequence.json"))
        self.assertEqual(len(config.slides), 6)
        self.assertEqual(config.slides[0].type, "calibration")
        for slide in config.slides:
            src = slide.get("src")
            if src:
                with self.subTest(slide=slide.id):
                    self.assertTrue((ROOT / src).is_file(), src)

    def test_champion_sequence_targets_selected_robot(self):
        expected = {
            "DinoByte": [
                ("play_sfx", "whoosh.wav"),
                ("move_backward", 1.0),
                ("turn_left", 90.0),
                ("move_backward", 1.0),
            ],
            "PenLinux": [
                ("play_sfx", "whoosh.wav"),
                ("move_backward", 1.0),
                ("turn_right", 90.0),
                ("move_backward", 2.0),
            ],
        }
        for champion, calls in expected.items():
            with self.subTest(champion=champion):
                db, pen = FakeRobot(), FakeRobot()
                asyncio.run(run_sequence(db, pen, champion))
                self.assertEqual(db.calls if champion == "DinoByte" else pen.calls, calls)
                self.assertEqual(pen.calls if champion == "DinoByte" else db.calls, [])


if __name__ == "__main__":
    unittest.main()
