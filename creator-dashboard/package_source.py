"""Portable source packaging used by the Windows PowerShell entry point."""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

EXCLUDED_DIRS={'.git','.data','.ui-audit','_package-staging','node_modules','.venv','venv','__pycache__',
               '.pytest_cache','.mypy_cache','.ruff_cache','.runtime','.pnpm-store','.uv-cache','.next',
               'dist','dist-electron','release','coverage','htmlcov','output','outputs','exports','renders',
               'uploads','tmp','cache','storage','.hyperframes','.thumbnails','.aws','.ssh','.codex','.cache'}
EXCLUDED_NAMES={'config.toml','.coverage','thumbs.db','.ds_store','desktop.ini','credentials.json','service-account.json','auth.json','tokens.json','secrets.json'}
EXCLUDED_EXTENSIONS={'.pyc','.pyo','.log','.tmp','.temp','.bak','.key','.pem','.pfx','.mp4','.mov','.mkv','.webm','.avi','.m4v','.mp3','.m4a','.aac','.wav','.flac'}
SECRET=re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:ghp_|github_pat_|glpat-|sk-proj-)[A-Za-z0-9_-]{24,}|\bAKIA[A-Z0-9]{16}\b')


def include(relative, directory=False):
    path=PurePosixPath(str(relative).replace('\\','/'))
    parts=tuple(part.casefold() for part in path.parts)
    if not parts or parts[0]=='references':return False
    dirs=parts if directory else parts[:-1]
    if any(part in EXCLUDED_DIRS for part in dirs):return False
    for index,part in enumerate(dirs):
        if part=='projects' and 'src' not in parts[:index]:return False
        if part=='build' and not '/'.join(parts).startswith('creator-dashboard/apps/short-video-factory/build'):return False
    name=parts[-1]
    if directory:return name not in EXCLUDED_DIRS
    if name.startswith('.env') and name!='.env.example':return False
    if name in EXCLUDED_NAMES or path.suffix.casefold() in EXCLUDED_EXTENSIONS:return False
    if len(parts)==1 and name.startswith('creator-control-center-') and name.endswith('.zip'):return False
    return True


def package(root: Path, version: str, keep_staging=False):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}',version):raise ValueError('Invalid package version')
    root=root.resolve();name='creator-control-center-'+version
    container=root/'_package-staging'
    if container.is_symlink():raise ValueError('Staging directory cannot be a symlink')
    container.mkdir(exist_ok=True,mode=0o700)
    stage=Path(tempfile.mkdtemp(prefix=name+'-',dir=container))
    archive=root/(name+'.zip');temporary=None;count=0
    try:
        tracked=None
        if (root/'.git').exists():
            raw=subprocess.check_output(['git','-C',str(root),'ls-files','-z'])
            tracked=set(raw.decode('utf-8').split('\0'))
        stack=[root]
        while stack:
            directory=stack.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    source=Path(entry.path);relative=source.relative_to(root)
                    info=entry.stat(follow_symlinks=False)
                    if entry.is_symlink() or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024):continue
                    if entry.is_dir(follow_symlinks=False):
                        if include(relative.as_posix(),True):stack.append(source)
                        continue
                    if not stat.S_ISREG(info.st_mode) or not include(relative.as_posix()):continue
                    if tracked is not None and relative.as_posix() not in tracked:continue
                    if not source.resolve().is_relative_to(root):raise ValueError('Source escapes package root')
                    # Credentials are never rewritten into a distributable: abort instead.
                    if info.st_size<=2_000_000:
                        body=source.read_bytes()
                        if b'\x00' not in body[:4096] and SECRET.search(body):
                            raise ValueError('Secret-like content found in '+relative.as_posix())
                    destination=stage/relative;destination.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(source,destination);count+=1
        if archive.is_symlink():raise ValueError('Archive target cannot be a symlink')
        fd,path=tempfile.mkstemp(dir=root,prefix='.package-',suffix='.tmp');os.close(fd);temporary=Path(path)
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,strict_timestamps=False) as output:
            for source in sorted(stage.rglob('*')):
                if source.is_file():output.write(source,(PurePosixPath(name)/source.relative_to(stage).as_posix()).as_posix())
        with temporary.open('rb') as source:digest=hashlib.file_digest(source,'sha256').hexdigest()
        temporary.replace(archive)
        return {'archive':str(archive),'files':count,'bytes':archive.stat().st_size,'sha256':digest,
                'staging':str(stage) if keep_staging else None}
    finally:
        if temporary:temporary.unlink(missing_ok=True)
        if not keep_staging:shutil.rmtree(stage,ignore_errors=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',default=datetime.now().strftime('%Y%m%d-%H%M'))
    parser.add_argument('--keep-staging',action='store_true')
    args=parser.parse_args()
    print(json.dumps(package(Path(__file__).resolve().parent.parent,args.version,args.keep_staging),indent=2))


if __name__=='__main__':main()
