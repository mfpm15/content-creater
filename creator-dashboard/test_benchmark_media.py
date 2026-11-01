import tempfile
import unittest
from pathlib import Path

from benchmark_media import compare_cuts, measure


class BenchmarkTests(unittest.TestCase):
    def test_duplicate_predictions_cannot_inflate_recall(self):
        result = compare_cuts([1, 1.01, 3, 8], [1, 2, 3], .1)
        self.assertEqual(result['matched'], 2)
        self.assertEqual(result['false_positives'], 2)
        self.assertEqual(result['missed'], 1)
        self.assertEqual(result['precision'], .5)
        self.assertAlmostEqual(result['recall'], 2/3)

    def test_absent_ground_truth_stays_unmeasured(self):
        self.assertIsNone(compare_cuts([1], [], .1)['recall'])
        self.assertIsNone(compare_cuts([], [1], .1)['precision'])
        for tolerance in (0, float('nan'), float('inf')):
            with self.assertRaises(ValueError): compare_cuts([], [], tolerance)

    def test_wrong_hash_is_rejected_before_decoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'fixture.flac'
            path.write_bytes(b'not media')
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                measure(path, '0'*64)
