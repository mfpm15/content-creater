import base64
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import wave

import voice_preview


def fake_provider(command, **kwargs):
    folder=Path(command[3])
    folder.mkdir(parents=True,exist_ok=True)
    with wave.open(str(folder/"scene-1.wav"),"wb") as wav:
        wav.setparams((1,2,24000,0,"NONE","not compressed"))
        raw=bytearray()
        for i in range(24000):
            value=int(5000*math.sin(i*2*math.pi*220/24000))
            raw.extend(value.to_bytes(2,"little",signed=True))
        wav.writeframes(raw)
    class Result:
        returncode=0
    return Result()


class VoicePreviewTests(unittest.TestCase):
    def test_valid_sample_uses_real_worker_contract_and_pcm_gate(self):
        with patch.object(voice_preview,"resolve_python",return_value=Path(sys.executable)), \
             patch.object(voice_preview.subprocess,"run",side_effect=fake_provider) as worker:
            result=voice_preview.preview({"language":"id","text":"Halo, ini suara uji."})
        self.assertEqual(result["voice"],"id-ID-ArdiNeural")
        self.assertEqual(result["mime"],"audio/wav")
        self.assertAlmostEqual(result["duration"],1.0)
        self.assertTrue(base64.b64decode(result["audioBase64"]).startswith(b"RIFF"))
        command=worker.call_args.args[0]
        self.assertEqual(Path(command[1]),voice_preview.WORKER)

    def test_reject_bad_input_before_network(self):
        for payload in ({}, {"language":"fr","text":"Halo"},
                        {"language":"id","text":"A"*200},
                        {"language":"id","text":"Halo","mode":"music"}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                voice_preview.preview(payload)

    def test_provider_failure_is_visible_and_not_replaced_by_music(self):
        class Failed:
            returncode=1
        with patch.object(voice_preview,"resolve_python",return_value=Path(sys.executable)), \
             patch.object(voice_preview.subprocess,"run",return_value=Failed()):
            with self.assertRaisesRegex(RuntimeError,"Sintesis Edge-TTS gagal"):
                voice_preview.preview({"language":"id","text":"Halo"})

if __name__=="__main__":
    unittest.main()
