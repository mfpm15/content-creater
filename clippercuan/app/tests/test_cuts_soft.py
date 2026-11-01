"""Dissolve/crossfade antar sudut kamera (skor scene kecil per frame) harus terdeteksi; gerak tangan/kepala tidak."""
from clipper import shots


def test_hard_cut_uses_peak_time():
    assert shots.cuts_from_events([(5.0, 0.62)]) == [5.0]


def test_crossfade_cluster_counts_as_one_cut_at_its_middle():
    ev = [(3.0 + i * 0.07, 0.04) for i in range(15)]          # ~1 detik, total 0.6
    cuts = shots.cuts_from_events(ev)
    assert len(cuts) == 1 and 3.3 < cuts[0] < 3.7


def test_small_motion_is_not_a_cut():
    ev = [(6.2 + i * 0.1, 0.016) for i in range(7)]           # gerak tangan: puncak < SOFT_PEAK, total kecil
    assert shots.cuts_from_events(ev) == []


def test_separate_groups_and_empty():
    ev = [(2.0, 0.5), (9.0, 0.45)]
    assert shots.cuts_from_events(ev) == [2.0, 9.0]
    assert shots.cuts_from_events([]) == []
