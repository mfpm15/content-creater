import unittest

import scene_motif
import remotion_adapter
import video_drafter as vd


def scenes(*rows):
    return [{"subject": s, "onScreenText": t, "narration": n, "visual": ""} for s, t, n in rows]


class SceneMotifTests(unittest.TestCase):
    def test_motif_follows_user_words_not_a_fixed_topic(self):
        cases = {
            "money": scenes(("Uang tabungan", "Dana darurat", "Sisihkan gaji setiap bulan"))[0],
            "tech": scenes(("Server data", "Cara kerja AI", "Komputer belajar dari data"))[0],
            "mountain": scenes(("Gunung", "Puncak", "Pendakian"))[0],
            "elephant": scenes(("Gajah", "Pasukan gajah", ""))[0],
            "water": scenes(("Laut", "Kapal berlayar", ""))[0],
            "heart": scenes(("Jantung", "Kesehatan", "Donor darah"))[0],
        }
        for expected, scene in cases.items():
            self.assertEqual(scene_motif.pick(scene), expected, scene)

    def test_explicit_motif_wins_and_unknown_values_are_ignored(self):
        scene = {"subject": "Gunung", "motif": "fire"}
        self.assertEqual(scene_motif.pick(scene), "fire")
        self.assertEqual(scene_motif.pick({"subject": "Gunung", "motif": "<script>"}), "mountain")

    def test_no_neighbours_repeat_and_films_show_variety(self):
        same = scenes(*[("Data server", "Teknologi komputer", "Aplikasi digital")] * 6)
        out = scene_motif.assign(same)
        self.assertTrue(all(a != b for a, b in zip(out, out[1:])), out)
        self.assertGreaterEqual(len(set(out)), 3, out)
        blank = scenes(*[("", "Halo", "Sambutan")] * 8)
        out = scene_motif.assign(blank)
        self.assertTrue(all(a != b for a, b in zip(out, out[1:])), out)
        self.assertTrue(set(out) <= set(scene_motif.MOTIFS))

    def test_manifest_carries_valid_motifs_and_karaoke_style(self):
        plan = vd.normalize_scene_plan({"scenes": [
            {"start": 0, "end": 3, "narration": "Menabung uang setiap bulan.", "onScreenText": "Menabung", "subject": "Uang"},
            {"start": 3, "end": 6, "narration": "Perjalanan panjang.", "onScreenText": "Rute", "subject": "Peta"}]}, "Tes", "", 6)
        props, _ = remotion_adapter.manifest(plan, {"width": 320, "height": 568})
        self.assertEqual([s["motif"] for s in props["shots"]], ["money", "map"])
        self.assertEqual(props["captionStyle"], "karaoke")


if __name__ == "__main__":
    unittest.main()
