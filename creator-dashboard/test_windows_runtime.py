import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import runtime_config


class WindowsRuntimeTests(unittest.TestCase):
    def test_windows_venv_uses_scripts_python(self):
        with patch.object(runtime_config,'os',SimpleNamespace(name='nt')):
            self.assertEqual(runtime_config.resolve_python(Path('application')),Path('application/.venv/Scripts/python.exe'))

    def test_finds_edge_outside_path_in_program_files_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='Program Files ') as tmp:
            browser=Path(tmp)/'Microsoft/Edge/Application/msedge.exe';browser.parent.mkdir(parents=True);browser.touch()
            env={'ProgramFiles':tmp}
            with patch.object(runtime_config,'os',SimpleNamespace(name='nt',environ=env)),patch.object(runtime_config.shutil,'which',return_value=None):
                self.assertEqual(runtime_config.find_browser(),str(browser))

    def test_finds_per_user_chrome_and_respects_explicit_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            browser=Path(tmp)/'Google/Chrome/Application/chrome.exe';browser.parent.mkdir(parents=True);browser.touch()
            with patch.object(runtime_config,'os',SimpleNamespace(name='nt',environ={'LOCALAPPDATA':tmp})),patch.object(runtime_config.shutil,'which',return_value=None):
                self.assertEqual(runtime_config.find_browser(),str(browser))
            with patch.object(runtime_config,'os',SimpleNamespace(name='nt',environ={'HYPERFRAMES_BROWSER_PATH':str(browser)})):
                self.assertEqual(runtime_config.find_browser(),str(browser))
