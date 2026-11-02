import tempfile
import subprocess
import unittest
import zipfile
from pathlib import Path

import package_source


class SourcePackageTests(unittest.TestCase):
    def test_git_checkout_only_packages_versioned_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            subprocess.run(['git','init','-q',str(root)],check=True)
            (root/'main.py').write_text('source')
            subprocess.run(['git','-C',str(root),'add','main.py'],check=True)
            (root/'untracked-settings.txt').write_text('private local settings')
            result=package_source.package(root,'tracked')
            with zipfile.ZipFile(result['archive']) as archive:
                self.assertEqual(archive.namelist(),['creator-control-center-tracked/main.py'])
    def test_keeps_source_build_projects_and_excludes_private_generated_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=['AGENTS.md','setup-core.bat','creator-dashboard/server.py',
                    'creator-dashboard/apps/short-video-factory/build/scripts/post-install.js',
                    'creator-dashboard/apps/short-video-factory/build/vite-plugins/dev.ts',
                    'creator-dashboard/apps/opencreator/apps/daemon/src/projects/manager.ts',
                    'creator-dashboard/apps/opencreator/apps/web/src/features/projects/page.tsx','.env.example']
            excluded=['.env','.env.local','credentials.json','model.key','.data/private.json',
                      'node_modules/pkg/index.js','creator-dashboard/.venv/pyvenv.cfg',
                      'creator-dashboard/output/article.json','projects/user/private.json',
                      'references/vendor/README.md','build/result.js','.aws/credentials']
            for name in source+excluded:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
            result=package_source.package(root,'test')
            with zipfile.ZipFile(result['archive']) as archive:
                names={name.removeprefix('creator-control-center-test/') for name in archive.namelist()}
            self.assertEqual(names,set(source));self.assertEqual(len(result['sha256']),64)
            self.assertFalse(list((root/'_package-staging').iterdir()))

    def test_rejects_secret_content_versions_and_does_not_follow_links(self):
        with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as other:
            root=Path(tmp);outside=Path(other)/'private.txt';outside.write_text('private')
            try:
                (root/'linked.txt').symlink_to(outside)
                (root/'linked-dir').symlink_to(Path(other),target_is_directory=True)
            except (OSError,NotImplementedError) as error:self.skipTest(f'Symlink unavailable: {error}')
            (root/'safe.py').write_text('source')
            result=package_source.package(root,'safe')
            with zipfile.ZipFile(result['archive']) as archive:self.assertEqual(len(archive.namelist()),1)
            for version in ['../outside','unsafe/path','']:
                with self.assertRaises(ValueError):package_source.package(root,version)
            (root/'sensitive.txt').write_text('-----BEGIN '+'PRIVATE KEY-----\nsynthetic')
            with self.assertRaisesRegex(ValueError,'Secret-like'):package_source.package(root,'blocked')
            self.assertFalse((root/'creator-control-center-blocked.zip').exists())
