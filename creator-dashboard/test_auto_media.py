"""Offline regression tests for Commons image sourcing and safe automatic drafting."""
from __future__ import annotations
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
import auto_media
import media_library
import video_drafter as vd
import video_templates
import remotion_adapter


def image() -> bytes:
    out=io.BytesIO()
    Image.new("RGB",(160,120),(20,99,140)).save(out,"PNG")
    return out.getvalue()


def page(license_name="CC0 1.0", url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Server_rack.png/960px-Server_rack.png"):
    return {"title":"File:Server_rack.png","imageinfo":[{
        "thumburl":url,
        "descriptionurl":"https://commons.wikimedia.org/wiki/File:Server_rack.png",
        "extmetadata":{"LicenseShortName":{"value":license_name},
                       "Artist":{"value":"<a>Example photographer</a>"}}}]}


class AutoMediaTests(unittest.TestCase):
    def test_strict_license_and_url_allowlist(self):
        self.assertEqual(auto_media._license({"LicenseShortName":{"value":"CC0 1.0"}}),"cc0 1.0")
        self.assertEqual(auto_media._license({"LicenseShortName":{"value":"Public domain"}}),"public domain")
        for license_text in ("CC BY-SA 4.0","CC BY-NC","All rights reserved",""):
            self.assertIsNone(auto_media._license({"LicenseShortName":{"value":license_text}}))
        self.assertFalse(auto_media._wikimedia_thumbnail("https://127.0.0.1/private"))
        self.assertFalse(auto_media._wikimedia_thumbnail("https://evil.example.com/wikipedia/commons/thumb/p.png"))
        self.assertFalse(auto_media._wikimedia_thumbnail("http://upload.wikimedia.org/wikipedia/commons/a.png"))
        self.assertTrue(auto_media._wikimedia_thumbnail(page()["imageinfo"][0]["thumburl"]))

    def test_provenance_preserving_automatic_import(self):
        with tempfile.TemporaryDirectory() as dirname:
            root=Path(dirname)
            original=media_library.save
            plan={"scenes":[{"id":"scene-1","onScreenText":"Server rack","narration":"Ini rak server."}]}
            with patch.object(auto_media,"_search",return_value=[page()]),\
                 patch.object(auto_media,"_download",return_value=image()),\
                 patch.object(auto_media.media_library,"save",side_effect=lambda payload:original(payload,root=root)):
                report=auto_media.suggest(plan)
            self.assertEqual(len(report["assets"]),1)
            self.assertEqual(len(report["warnings"]),0)
            asset_id=plan["scenes"][0]["assetId"]
            meta,_=media_library.get(asset_id,root=root)
            self.assertIn("Lisensi: cc0 1.0",meta["source"])
            self.assertIn("Example photographer",meta["creator"])
            self.assertEqual(meta["rightsBasis"],"external_metadata_unverified")
            self.assertTrue(report["assets"][0]["rightsReviewRequired"])

    def test_invalid_license_and_missing_match_retain_illustration(self):
        plan={"scenes":[{"id":"scene-1","onScreenText":"Server rack"}]}
        with patch.object(auto_media,"_search",return_value=[page("CC BY-SA 4.0")]),\
             patch.object(auto_media,"_download") as no_download:
            report=auto_media.suggest(plan)
        self.assertEqual(report["assets"],[])
        self.assertNotIn("assetId",plan["scenes"][0])
        self.assertTrue(report["warnings"])
        no_download.assert_not_called()

    def test_automated_job_retains_approvals_and_auto_render_opt_in(self):
        with tempfile.TemporaryDirectory() as dirname,\
             patch.object(vd,"JOBS",{}),patch.object(vd,"JOB_DIR",Path(dirname)),\
             patch.object(vd.threading.Thread,"start"),\
             patch.object(vd.auto_media,"suggest",return_value={"assets":[],"warnings":[]}) as suggest,\
             patch.object(vd,"approve_job") as approve:
            job_id=vd.start_job({"topic":"Keamanan siber pemula","script":"Periksa sistem sebelum diserang.",
                  "researchMode":"provided","engine":"remotion","smartTemplate":True,
                  "autoMedia":True,"autoRender":True,"captionStyle":"pop","voiceMode":"none"})["jobId"]
            vd._run_job(job_id)
            job=vd.job_status(job_id)
            self.assertEqual(job["status"],"awaiting_scene_plan",job.get("error"))
            self.assertEqual(job["templateId"],video_templates.recommend(job["topic"])["id"])
            self.assertEqual(job["scenePlan"]["captionStyle"],"pop")
            self.assertEqual(job["autoMediaReport"]["assets"],[])
            suggest.assert_called_once()
            approve.assert_called_once_with(job_id,"scene_plan")
            approve.reset_mock()
            vd._continue_job(job_id, "scene_plan")
            self.assertEqual(vd.job_status(job_id)["status"],"awaiting_storyboard")
            approve.assert_called_once_with(job_id, "storyboard")
            props,_=remotion_adapter.manifest(job["scenePlan"],vd.ASPECT_RATIOS["9:16"])
            self.assertEqual(props["captionStyle"],"pop")

    def test_api_rejects_invalid_automation_flags_without_job(self):
        with patch.object(vd,"JOBS",{}):
            for key,value in (("autoMedia","yes"),("autoRender",1),("smartTemplate",None)):
                with self.subTest(key=key),self.assertRaises(ValueError):
                    vd.start_job({"topic":"Contoh","engine":"remotion",key:value})


if __name__=="__main__":
    unittest.main()
