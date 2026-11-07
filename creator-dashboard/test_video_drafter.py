from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import video_drafter


class VideoDrafterTest(unittest.TestCase):
    def setUp(self):
        self.workspace=tempfile.TemporaryDirectory()
        root=Path(self.workspace.name)
        self.patches=[patch.object(video_drafter,'JOBS',{}),patch.object(video_drafter,'JOB_DIR',root/'jobs'),patch.object(video_drafter,'VIDEOS_DIR',root/'videos')]
        for item in self.patches:item.start()

    def tearDown(self):
        for item in reversed(self.patches):item.stop()
        self.workspace.cleanup()

    def test_options_expose_render_adapters_and_primary_models(self):
        with patch.dict(video_drafter.os.environ, {}, clear=True), \
             patch.object(video_drafter.tavily_research, "available", return_value=False):
            opts = video_drafter.options()
        self.assertEqual([item["id"] for item in opts["engines"]], ["opuscar", "threejs", "lottie", "continuous", "remotion"])
        self.assertEqual(opts["defaultEngine"], "opuscar")
        self.assertFalse(next(item for item in opts["engines"] if item["id"] == "threejs").get("disabled", False))
        self.assertEqual(opts["workflow"], ["brief", "research", "narration", "scene_plan", "storyboard", "render"])
        self.assertEqual(opts["research"]["provider"], "Tavily")
        self.assertFalse(opts["research"]["ready"])
        self.assertFalse(opts["research"]["required"])
        self.assertEqual(opts["research"]["requiredForModes"], ["web"])
        model_ids = [item["id"] for item in opts["models"]]
        self.assertEqual(model_ids, [
            "cc/claude-sonnet-5-5",
            "ms/GPT-5.6-Think-Deeper",
            "cc/claude-haiku-5-5",
        ])
        self.assertFalse(any("gemini" in model.lower() or "opus" in model.lower() for model in model_ids))
        self.assertEqual(opts["defaultModel"], "cc/claude-sonnet-5-5")

    def test_legacy_or_unsupported_video_model_falls_back_to_default_sonnet(self):
        with patch.object(video_drafter, "LLM_MODEL", "ag/gemini-3.8-flash-high"), \
             patch.object(video_drafter.threading.Thread, "start"):
            options = video_drafter.options()
            self.assertEqual(options["defaultModel"], "cc/claude-sonnet-5-5")
            result = video_drafter.start_job({
                "topic": "Uji AI video", "engine": "remotion",
                "model": "cc/claude-opus-5-5",
            })
            job = video_drafter.job_status(result["jobId"])
            self.assertEqual(job["model"], "cc/claude-sonnet-5-5")

    def test_explicit_timecodes_and_fields_are_preserved(self):
        scenes = video_drafter.parse_explicit_scenes("00:00-00:07 Narasi: Pembuka asli\nVisual: Kota pagi\nTeks layar: Mulai\nSFX: whoosh\n\n00:07-00:20 Narasi: Isi asli\nVisual: Grafik data")
        self.assertEqual(len(scenes), 2)
        self.assertEqual((scenes[0]["start"], scenes[0]["end"]), (0, 7))
        self.assertEqual(scenes[0]["narration"], "Pembuka asli")
        self.assertEqual(scenes[0]["soundCue"], "whoosh")
        self.assertEqual(scenes[1]["end"], 20)

    def test_fallback_without_timecode_is_proportional(self):
        plan = video_drafter.normalize_scene_plan({}, "Kopi", "Pendek. Kalimat kedua jauh lebih panjang untuk menjelaskan proses seduh kopi.", 30)
        self.assertEqual(len(plan["scenes"]), 2)
        self.assertEqual(plan["scenes"][0]["start"], 0)
        self.assertEqual(plan["scenes"][-1]["end"], 30)
        self.assertGreater(plan["scenes"][1]["duration"], plan["scenes"][0]["duration"])

    def test_llm_scene_count_remains_dynamic(self):
        source = {"scenes": [{"narration": f"Bagian {index}", "type": "story"} for index in range(7)]}
        plan = video_drafter.normalize_scene_plan(source, "Dinamis", "", 70)
        self.assertEqual(len(plan["scenes"]), 7)
        composition = video_drafter.generate_composition(plan, video_drafter.ASPECT_RATIOS["16:9"])
        self.assertEqual(composition.count('<section class="scene'), 7)
        self.assertIn('data-duration="70"', composition)

    def test_narration_subtitle_and_sound_mapping(self):
        plan = video_drafter.normalize_scene_plan({}, "Tes", "0-5 Narasi: Halo dunia\nTeks layar: HALO\nSFX: bell", 60)
        manifest = video_drafter.audio_manifest(plan)
        self.assertEqual(manifest["voice"][0]["text"], "Halo dunia")
        self.assertEqual(manifest["subtitles"][0]["end"], 5)
        self.assertEqual(manifest["soundCues"][0], {"at": 0, "cue": "bell"})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "subtitles.srt"
            video_drafter.write_subtitles(path, plan)
            self.assertIn("00:00:05,000", path.read_text(encoding="utf-8"))

    def test_visual_grammar_matches_scene_type(self):
        plan = {"topic": "Jenis", "duration": 10, "scenes": [{"id": "scene-1", "start": 0, "end": 10, "duration": 10, "narration": "Data 80%", "visual": "grafik", "onScreenText": "80%", "soundCue": "", "type": "data"}]}
        result = video_drafter.generate_composition(plan, video_drafter.ASPECT_RATIOS["9:16"], model="model-rahasia", engine="opuscar")
        self.assertIn('class="visual-canvas-box data-viz"', result)
        self.assertIn('grid-template-rows:minmax(0,28%) minmax(0,1fr)', result)
        self.assertIn('.subtitle-capsule{position:relative', result)
        self.assertIn('max-height:760px', result)
        self.assertNotIn('min-height:700px', result)
        self.assertNotIn('<p>grafik</p>', result)  # Teks prompt mentah tidak ditampilkan
        self.assertNotIn('model-rahasia', result)  # Nama model tidak boleh dibakar ke video
        self.assertNotIn('model-watermark', result)

    def test_visual_router_follows_user_meaning_not_only_scene_type(self):
        base = {"topic": "Dinamis", "duration": 8}
        forest = {**base, "scenes": [{"id": "scene-1", "start": 0, "end": 8, "duration": 8, "narration": "Air mengalir melewati hutan.", "visual": "sungai mengalir di antara hutan dan pegunungan", "onScreenText": "ALIRAN ALAM", "soundCue": "", "type": "story"}]}
        product = {**base, "scenes": [{"id": "scene-1", "start": 0, "end": 8, "duration": 8, "narration": "Perangkat dibuka lapis demi lapis.", "visual": "produk hardware meledak menjadi lapisan komponen", "onScreenText": "DI DALAM PRODUK", "soundCue": "", "type": "story"}]}
        forest_html = video_drafter.generate_composition(video_drafter.normalize_scene_plan(forest, "Alam", "", 8), video_drafter.ASPECT_RATIOS["9:16"], engine="opuscar")
        product_html = video_drafter.generate_composition(video_drafter.normalize_scene_plan(product, "Hardware", "", 8), video_drafter.ASPECT_RATIOS["9:16"], engine="opuscar")
        self.assertIn('data-family="nature"', forest_html)
        self.assertIn('class="sun-disc"', forest_html)
        self.assertIn('data-family="device"', product_html)
        self.assertIn('class="device-shell"', product_html)
        self.assertNotEqual(forest_html, product_html)

    def test_scene_descriptor_preserves_directorial_fields(self):
        source = {"scenes": [{"narration": "Paket bergerak.", "visual": "paket mengikuti rute", "type": "story", "subject": "paket", "action": "melaju", "setting": "kota", "camera": "follow route", "transition": "route-wipe", "colorMood": "hangat"}]}
        scene = video_drafter.normalize_scene_plan(source, "Logistik", "", 10)["scenes"][0]
        self.assertEqual(scene["visualFamily"], "journey")
        self.assertEqual(scene["subject"], "paket")
        self.assertEqual(scene["camera"], "follow route")
        self.assertEqual(scene["transition"], "route-wipe")
        self.assertEqual(scene["colorMood"], "hangat")

    def test_cyber_topic_does_not_force_every_scene_to_network(self):
        source = {"scenes": [
            {"narration": "Analis memeriksa bukti.", "visual": "Analis membuka bukti temuan dari timeline audit.", "type": "data"},
            {"narration": "Agen masuk ke simulasi.", "visual": "Agen AI memasuki gerbang lingkungan simulasi terisolasi.", "type": "process"},
            {"narration": "Node menyebar.", "visual": "Diagram jaringan dengan node dan server yang saling terhubung.", "type": "story"},
        ]}
        scenes = video_drafter.normalize_scene_plan(source, "keamanan siber 2027 dan agentic ai pentesting", "", 15)["scenes"]
        self.assertEqual([scene["visualFamily"] for scene in scenes], ["evidence", "portal", "network"])
        html = video_drafter.generate_composition({"topic": "cyber", "duration": 15, "scenes": scenes}, video_drafter.ASPECT_RATIOS["9:16"], engine="opuscar")
        self.assertIn('data-family="evidence"', html)
        self.assertIn('data-family="portal"', html)
        self.assertIn('data-family="network"', html)
        self.assertNotIn('class="visual-canvas-box radar-viz"', html)

    def test_visual_instructions_never_become_labels_or_fake_metrics(self):
        source = {"scenes": [
            {"narration": "Kota berubah.", "visual": "Format vertikal 9:16. Kota digital malam hari. Kamera menukik.", "onScreenText": "KOTA MASA DEPAN", "type": "story"},
            {"narration": "Dua prinsip seimbang.", "visual": "Timbangan menyeimbangkan kecepatan dengan governance.", "onScreenText": "KECEPATAN + GOVERNANCE", "type": "comparison"},
        ]}
        plan = video_drafter.normalize_scene_plan(source, "topik bebas", "", 10)
        html = video_drafter.generate_composition(plan, video_drafter.ASPECT_RATIOS["9:16"], engine="opuscar")
        self.assertEqual([s["visualFamily"] for s in plan["scenes"]], ["cityscape", "balance"])
        self.assertNotIn("FORMAT VERTIKAL", html)
        self.assertNotIn("METODE LAMA", html)
        self.assertNotIn("99% Otonom", html)
        self.assertNotIn("98.7", html)
        self.assertIn('data-family="cityscape"', html)
        self.assertIn('data-action="balance"', html)
        self.assertNotIn("Fase 1", html)
        self.assertNotIn("Puncak", html)

    def test_automatic_cross_domain_routing_uses_scene_content(self):
        source = {"scenes": [
            {"narration": "Air mengalir melalui hutan.", "visual": "Sungai melewati hutan dan pegunungan.", "type": "story"},
            {"narration": "Dokumen diperiksa.", "visual": "Laporan dan bukti diperiksa dengan kaca pembesar.", "type": "story"},
            {"narration": "Kota tumbuh.", "visual": "Skyline gedung kota digital muncul dari tanah.", "type": "story"},
            {"narration": "Dua kepentingan diseimbangkan.", "visual": "Timbangan menjaga keseimbangan dua prinsip.", "type": "comparison"},
        ]}
        scenes = video_drafter.normalize_scene_plan(source, "tema apa pun", "", 20)["scenes"]
        self.assertEqual([scene["visualFamily"] for scene in scenes], ["nature", "evidence", "cityscape", "balance"])
        self.assertTrue(all(scene["subject"] == "" for scene in scenes))

    def test_threejs_composition_generates_webgl_canvas_and_lights(self):
        plan = {"topic": "3D Cyber", "duration": 15, "scenes": [{"id": "scene-1", "start": 0, "end": 15, "duration": 15, "narration": "Dunia 3D", "visual": "grid", "onScreenText": "CYBER WORLD", "soundCue": "", "type": "story"}]}
        result = video_drafter.generate_composition(plan, video_drafter.ASPECT_RATIOS["9:16"], model="model-rahasia", engine="threejs")
        self.assertIn('id="webglCanvas"', result)
        self.assertIn('THREE.WebGLRenderer', result)
        self.assertIn('THREE.BoxGeometry', result)
        self.assertNotIn('THREE.IcosahedronGeometry', result)
        self.assertIn('window.__timelines.video', result)
        self.assertNotIn('model-rahasia', result)
        self.assertNotIn('class="watermark"', result)

    def test_procedural_audio_uses_scene_sound_cues(self):
        plan = video_drafter.normalize_scene_plan({}, "Audio", "0-1 Narasi: Halo\nSFX: bell", 1)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bed.wav"
            video_drafter._write_procedural_audio(output, plan, sample_rate=8000)
            self.assertGreater(output.stat().st_size, 8000)

    def test_start_job_selects_adapter_and_keeps_valid_duration(self):
        with patch.object(video_drafter.threading, "Thread"):
            result = video_drafter.start_job({"topic": "Tes", "engine": "lottie", "duration": 30, "model": "cc/claude-sonnet-5-5"})
        job = video_drafter.job_status(result["jobId"])
        self.assertEqual(job["engine"], "lottie")
        self.assertEqual(job["duration"], 30)
        self.assertEqual(job["model"], "cc/claude-sonnet-5-5")
        self.assertEqual(job["researchMode"], "planner")
        self.assertEqual(job["status"], "queued")

    def test_title_only_planner_uses_selected_model_and_detailed_prompt(self):
        captured = {}
        def fake_call(prompt, model=""):
            if 'TAHAP 1 — PENULISAN NARASI' in prompt:
                return '{"narration":"Sebuah perubahan dimulai."}'
            captured["prompt"] = prompt
            captured["model"] = model
            return '{"creativeDirection":{"logline":"Transformasi"},"scenes":[{"start":0,"end":15,"narration":"Sebuah perubahan dimulai.","onScreenText":"MULAI BERUBAH","visual":"Satu objek berubah bentuk lalu membuka dunia baru.","type":"story","shotPurpose":"hook","camera":"macro push-in","lighting":"high contrast","transition":"shape match","continuity":"bentuk diteruskan"}]}'
        with patch.object(video_drafter.threading, "Thread"):
            result = video_drafter.start_job({"topic": "Masa depan kerja", "duration": 15, "model": "ms/GPT-5.6-Think-Deeper", "researchMode": "planner"})
        with patch.object(video_drafter, "_call_9router", side_effect=fake_call):
            video_drafter._run_job(result["jobId"])
        job = video_drafter.job_status(result["jobId"])
        self.assertEqual(captured["model"], "ms/GPT-5.6-Think-Deeper")
        self.assertIn("creative director", captured["prompt"])
        self.assertIn("KONTRAK ENGINE: opuscar", captured["prompt"])
        self.assertIn("foreground, midground, background", captured["prompt"])
        self.assertEqual(job["status"], "awaiting_scene_plan")
        self.assertEqual(job["scenePlan"]["creativeDirection"]["logline"], "Transformasi")

    def test_llm_falls_back_to_next_model_on_503_but_not_on_client_error(self):
        import urllib.error
        calls = []

        def down_first(prompt, model=""):
            calls.append(model)
            if model == "ms/GPT-5.6-Think-Deeper":
                raise urllib.error.HTTPError("u", 503, "Service Unavailable", {}, None)
            return '{"ok":true}'
        with patch.object(video_drafter, "_call_9router", side_effect=down_first):
            self.assertEqual(video_drafter._call_llm("p", "ms/GPT-5.6-Think-Deeper"), '{"ok":true}')
        self.assertEqual(calls, ["ms/GPT-5.6-Think-Deeper", "cc/claude-sonnet-5-5"])

        def bad_request(prompt, model=""):
            raise urllib.error.HTTPError("u", 400, "Bad Request", {}, None)
        with patch.object(video_drafter, "_call_9router", side_effect=bad_request) as call:
            with self.assertRaises(urllib.error.HTTPError):
                video_drafter._call_llm("p", "ms/GPT-5.6-Think-Deeper")
            self.assertEqual(call.call_count, 1)

        def all_down(prompt, model=""):
            raise urllib.error.HTTPError("u", 503, "Service Unavailable", {}, None)
        with patch.object(video_drafter, "_call_9router", side_effect=all_down) as call:
            with self.assertRaises(urllib.error.HTTPError):
                video_drafter._call_llm("p")
            self.assertEqual(call.call_count, len(video_drafter.DEFAULT_MODELS))

    def test_workflow_requires_ordered_approvals(self):
        plan = video_drafter.normalize_scene_plan({"scenes":[{"start":0,"end":15,"narration":"Adegan pembuka.","visualFamily":"kinetic-type"}]}, "Tes", "", 15)
        with patch.object(video_drafter.threading, "Thread"):
            result = video_drafter.start_job({"topic": "Tes"})
            job_id = result["jobId"]
            video_drafter._update_job(job_id, {"status": "awaiting_scene_plan", "scenePlan": plan})
            video_drafter.approve_job(job_id, "scene_plan")
        with self.assertRaises(ValueError):
            video_drafter.approve_job(job_id, "storyboard")

    def test_detailed_storyboard_and_edit_preserve_timecodes(self):
        source = {"scenes": [{
            "start": 2, "end": 9, "narration": "Produk bergerak menuju pelanggan.",
            "visual": "Paket mengikuti jalur kota.", "visualFamily": "journey",
            "shotPurpose": "reveal", "composition": "diagonal route with upper negative space",
            "foreground": "penanda rute", "midground": "paket", "background": "kota",
            "camera": "medium tracking shot", "lighting": "golden hour",
            "typography": "judul kiri atas", "continuity": "garis berlanjut ke shot berikutnya",
        }]}
        plan = video_drafter.normalize_scene_plan(source, "Logistik", "", 15)
        self.assertEqual((plan["scenes"][0]["start"], plan["scenes"][0]["end"]), (2, 9))
        board = video_drafter._storyboard(plan)
        self.assertEqual(board[0]["shotPurpose"], "reveal")
        self.assertEqual(board[0]["camera"], "medium tracking shot")
        self.assertIn("foreground", board[0])
        self.assertIn("continuity", board[0])

    def test_delete_video_rejects_unsafe_slug_and_removes_project(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(video_drafter, "VIDEOS_DIR", Path(directory)):
            target = Path(directory) / "project-aman"
            target.mkdir()
            (target / "metadata.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                video_drafter.delete_video("../project-aman")
            result = video_drafter.delete_video("project-aman")
            self.assertTrue(result["ok"])
            self.assertFalse(target.exists())

    def test_update_job_plan_saves_editor_fields(self):
        with patch.object(video_drafter.threading, "Thread"):
            result = video_drafter.start_job({"topic": "Editor", "duration": 15})
        job_id = result["jobId"]
        video_drafter._update_job(job_id, {"status": "awaiting_scene_plan"})
        payload = {"stage": "scene_plan", "scenePlan": {"scenes": [{
            "start": 0, "end": 15, "narration": "Narasi hasil edit.",
            "visual": "Hutan berkabut.", "visualFamily": "nature",
            "composition": "subjek kecil dengan ruang teks luas", "camera": "slow push-in",
        }]}}
        job = video_drafter.update_job_plan(job_id, payload)
        self.assertEqual(job["scenePlan"]["scenes"][0]["narration"], "Narasi hasil edit.")
        self.assertEqual(job["scenePlan"]["scenes"][0]["composition"], "subjek kecil dengan ruang teks luas")

    def test_options_report_tavily_when_key_is_present(self):
        with patch.dict(video_drafter.os.environ, {"TAVILY_API_KEY": "tvly-test"}, clear=True):
            opts = video_drafter.options()
        self.assertEqual(opts["research"]["provider"], "Tavily")
        self.assertTrue(opts["research"]["ready"])

    def test_research_web_fails_closed_without_api_key(self):
        with patch.dict(video_drafter.os.environ, {}, clear=True), \
             patch.object(video_drafter.tavily_research, "available", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "Web Search tidak tersedia"):
                video_drafter._research_web("Topik", "Konteks")

    def test_research_web_uses_tavily_and_keeps_claims_unverified(self):
        payload = {"answer": "Ringkasan.", "results": [
            {"title": "Sumber A", "url": "https://example.org/a", "content": "isi a"},
            {"title": "Duplikat", "url": "https://example.org/a", "content": "dup"},
            {"title": "Bukan web", "url": "javascript:alert(1)", "content": "x"}]}
        with patch.dict(video_drafter.os.environ, {"TAVILY_API_KEY": "tvly-test"}, clear=True), \
             patch.object(video_drafter.tavily_research, "_post", return_value=payload) as post, \
             patch.object(video_drafter.subprocess, "run", side_effect=AssertionError("Tidak boleh memakai subprocess")):
            result = video_drafter._research_web("Topik", "Konteks")
        self.assertEqual(post.call_args.args[0], video_drafter.tavily_research.URL)
        self.assertEqual(result["provider"], "Tavily")
        self.assertEqual([s["url"] for s in result["sources"]], ["https://example.org/a"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["sources"][0]["claimVerification"], "unverified")

    def test_research_web_reports_tavily_failure_without_leaking_key(self):
        with patch.dict(video_drafter.os.environ, {"TAVILY_API_KEY": "tvly-secret-value"}, clear=True), \
             patch.object(video_drafter.tavily_research, "_post", side_effect=OSError("down tvly-secret-value")):
            with self.assertRaisesRegex(RuntimeError, "Riset Tavily gagal") as caught:
                video_drafter._research_web("Topik", "")
        self.assertNotIn("tvly-secret-value", str(caught.exception))

    def test_default_model_is_sonnet_and_fallback_order_is_sonnet_gpt_haiku(self):
        self.assertEqual(video_drafter.DEFAULT_MODELS[0]["id"], "cc/claude-sonnet-5-5")
        calls = []

        def always_down(prompt, model=""):
            calls.append(model)
            import urllib.error
            raise urllib.error.HTTPError("u", 503, "x", {}, None)
        with patch.object(video_drafter, "_call_9router", side_effect=always_down):
            with self.assertRaises(Exception):
                video_drafter._call_llm("p", "cc/claude-sonnet-5-5")
        self.assertEqual(calls, ["cc/claude-sonnet-5-5", "ms/GPT-5.6-Think-Deeper", "cc/claude-haiku-5-5"])

    def test_tavily_direct_key_is_not_leaked_to_render_environment(self):
        with patch.dict(video_drafter.os.environ, {"TAVILY_API_KEY": "tvly-secret-value"}):
            self.assertNotIn("TAVILY_API_KEY", video_drafter.render_environment())

    def test_llm_total_budget_stops_retries_and_reports_slow_model(self):
        calls = []

        def slow(prompt, model=""):
            calls.append(model)
            raise TimeoutError("timed out")
        with patch.object(video_drafter, "PLAN_BUDGET", 0), patch.object(video_drafter, "_call_9router", side_effect=slow):
            with self.assertRaisesRegex(RuntimeError, "terlalu lama"):
                video_drafter._call_llm("p", "cc/claude-sonnet-5-5")
        self.assertEqual(calls, ["cc/claude-sonnet-5-5"])

    def test_research_context_contains_sources_and_urls(self):
        research = {
            "summary": "Ringkasan terverifikasi.",
            "sources": [{
                "id": 1,
                "title": "Dokumentasi Resmi",
                "publisher": "example.org",
                "url": "https://example.org/report",
            }],
        }
        context = video_drafter._research_context(research)
        self.assertIn("Ringkasan terverifikasi", context)
        self.assertIn("[1] Dokumentasi Resmi", context)
        self.assertIn("https://example.org/report", context)

    def test_research_web_requires_sources(self):
        with patch.dict(video_drafter.os.environ, {"TAVILY_API_KEY": "tvly-test"}, clear=True), \
             patch.object(video_drafter.tavily_research, "_post", return_value={"results": []}):
            with self.assertRaisesRegex(RuntimeError, "tidak menghasilkan sumber"):
                video_drafter._research_web("Topik", "")

    def test_motion_contract_and_lottie_adapter(self):
        plan = video_drafter.normalize_scene_plan({}, "Data", "Data naik 80%.", 15)
        self.assertIn("direction", plan["scenes"][0]["motion"])
        result = video_drafter.generate_lottie(plan, video_drafter.ASPECT_RATIOS["9:16"])
        self.assertEqual(result["v"], "5.12.2")
        self.assertEqual(result["op"], 450)
        self.assertEqual(len([layer for layer in result["layers"] if layer["ty"] == 4]), 1)
        self.assertTrue(any(layer["ty"] == 5 for layer in result["layers"]))


if __name__ == "__main__":
    unittest.main()
