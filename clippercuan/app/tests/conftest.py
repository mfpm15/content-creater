"""Tes tidak menyentuh data asli maupun drive C:.

CLIPPER_HOME dan temp dialihkan ke <repo>/.data/tmp sebelum modul `clipper` diimpor oleh test mana pun,
lalu folder CLIPPER_HOME tes dihapus di akhir sesi.
"""
import os
import shutil
import tempfile
from pathlib import Path

_TMP = Path(__file__).resolve().parents[3] / ".data" / "tmp"
_TMP.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(_TMP)
_HOME = tempfile.mkdtemp(dir=_TMP, prefix="clipper-test-")
os.environ["CLIPPER_HOME"] = _HOME


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_HOME, ignore_errors=True)
