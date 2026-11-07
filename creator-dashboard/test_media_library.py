"""Regression tests: image uploads, provenance, sandboxed staging and Remotion manifests."""
from __future__ import annotations

import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import media_library
import remotion_adapter
import video_drafter as vd


def png() -> bytes:
    image = Image.new("RGB", (160, 120), (30, 150, 170))
    buffer=io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def record(data: bytes, rights=True) -> dict:
    return {
        "name": "Server rack sample.png",
        "creator": "Foto sendiri",
        "source": "Foto milik sendiri, lisensi komersial",
        "rightsConfirmed": rights,
        "base64": base64.b64encode(data).decode("ascii"),
    }


class MediaLibraryTests(unittest.TestCase):
    def test_valid_image_and_provenance_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            asset=media_library.save(record(png()),root=root)
            self.assertTrue(asset["rightsConfirmed"])
            self.assertEqual(asset["mime"], "image/png")
            self.assertEqual(asset["width"],160)
            self.assertEqual(media_library.catalogue(root=root)[0]["id"],asset["id"])
            meta, src=media_library.get(asset["id"],root=root)
            self.assertEqual(meta["source"],"Foto milik sendiri, lisensi komersial")
            self.assertEqual(src.read_bytes(),png())
            out=media_library.stage(asset["id"],root / "render-public",root=root)
            self.assertEqual(out["publicFile"],"media/"+meta["filename"])
            self.assertEqual((root/"render-public"/out["publicFile"]).read_bytes(),png())

    def test_refuse_untrusted_images_or_missing_rights(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for payload in (
                record(png(), rights=False),
                record(b"<svg onload='alert(1)'></svg>"),
                record(b"hello"),
                {**record(png()),"base64":"**??"},
            ):
                with self.subTest(payload=str(payload)[:60]), self.assertRaises(ValueError):
                    media_library.save(payload,root=root)
            for name in ("../x","a"*32+"../", "https://example.com","a"*33):
                with self.assertRaises(ValueError):
                    media_library.get(name,root=root)
            self.assertFalse(media_library.catalogue(root=root))

    def test_media_checksum_prevents_modified_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); asset=media_library.save(record(png()),root=root)
            meta, path=media_library.get(asset["id"],root=root)
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError,"Ukuran media"):
                media_library.get(asset["id"],root=root)

    def test_storyboard_asset_roundtrips_and_manifest_is_sandboxed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            asset=media_library.save(record(png()),root=root)
            original=media_library.get
            with patch.object(media_library,"get",side_effect=lambda aid:original(aid,root=root)):
                plan=vd.normalize_scene_plan({"scenes":[{
                    "start":0,"end":2,"narration":"Inilah fasilitas penyimpanan data.",
                    "onScreenText":"Fasilitas Data","assetId":asset["id"],"visualFamily":"concept",
                }],"fps":30},"Fasilitas Data","",2)
                self.assertEqual(plan["scenes"][0]["assetId"],asset["id"])
                props, report=remotion_adapter.manifest(plan,{"width":320,"height":568})
                self.assertEqual(props["shots"][0]["assetFile"],"media/"+asset["filename"])
                self.assertTrue(report["manual_required"])
            with self.assertRaises(ValueError):
                vd.normalize_scene_plan({"scenes":[{
                    "start":0,"end":2,"narration":"Fasilitas",
                    "onScreenText":"Fasilitas","assetId":"../../bad.png",
                }]},"Fasilitas","",2)


if __name__ == "__main__":
    unittest.main()
