import math
import tempfile
import unittest
import wave
from pathlib import Path

from voice_quality import require_audible


class VoiceQualityTests(unittest.TestCase):
    def sample(self, root: Path, amplitude=0, duration=1.0):
        file = root / "voice.wav"
        rate = 24000
        with wave.open(str(file), "wb") as wav:
            wav.setparams((1, 2, rate, 0, "NONE", "not compressed"))
            data = bytearray()
            for i in range(int(rate * duration)):
                sample = round(amplitude * math.sin(2 * math.pi * 220 * i / rate))
                data.extend(sample.to_bytes(2, "little", signed=True))
            wav.writeframes(data)
        return file

    def test_audible_neural_like_pcm_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            checked = require_audible(self.sample(Path(tmp), amplitude=6000))
            self.assertGreater(checked["rms_pcm16"], 1000)
            self.assertEqual(checked["duration"], 1)

    def test_silence_and_near_silence_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for amplitude in (0, 80):
                with self.subTest(amplitude=amplitude), self.assertRaisesRegex(ValueError, "senyap"):
                    require_audible(self.sample(Path(tmp), amplitude=amplitude))

    def test_too_short_and_corrupted_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "terlalu pendek"):
                require_audible(self.sample(root, amplitude=6000, duration=.05))
            bad = root / "broken.wav"
            bad.write_bytes(b"not a wav")
            with self.assertRaisesRegex(ValueError, "tidak dapat dibaca"):
                require_audible(bad)


if __name__ == "__main__":
    unittest.main()
