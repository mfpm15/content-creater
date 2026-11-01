"""Private article writes and recoverable commits of source plus derived documents."""
import json
import os
import shutil
import tempfile
import threading
from pathlib import Path

LOCK = threading.RLock()
JOURNAL = '.article-transaction.json'


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.write-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        Path(name).replace(path)
    finally:
        Path(name).unlink(missing_ok=True)


def json_bytes(data) -> bytes:
    return json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2).encode('utf-8')


def _target(directory, relative):
    path=Path(relative)
    if path.is_absolute() or not path.parts or any(part in {'.','..'} for part in path.parts):
        raise ValueError('Invalid article transaction path')
    target=directory/path
    if target.is_symlink() or not target.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Article transaction cannot follow symbolic links')
    return target


def recover(directory: Path) -> None:
    """Roll back an interrupted commit before exposing article files again."""
    with LOCK:
        journal=directory/JOURNAL
        if journal.is_symlink():raise ValueError('Invalid article recovery journal')
        if not journal.exists():return
        data=json.loads(journal.read_text('utf-8'))
        stage_name=data.get('stage','')
        if not isinstance(stage_name,str) or not stage_name.startswith('.edit-') or '/' in stage_name or '\\' in stage_name:
            raise ValueError('Invalid article recovery journal')
        stage=_target(directory,stage_name)
        entries=data.get('files')
        if not isinstance(entries,list) or not entries:raise ValueError('Invalid article recovery files')
        # Validate all backup paths first; an incomplete journal must not erase data.
        for entry in entries:
            _target(directory,entry['name'])
            if entry['existed'] and not _target(stage/'before',entry['name']).is_file():
                raise ValueError('Article recovery backup is missing')
        for entry in entries:
            target=_target(directory,entry['name'])
            if entry['existed']:
                original=_target(stage/'before',entry['name']).read_bytes()
                if not target.is_file() or target.read_bytes()!=original:atomic_bytes(target,original)
            else:target.unlink(missing_ok=True)
        journal.unlink()
        shutil.rmtree(stage)


def commit(directory: Path, updates: dict[str, bytes | None], article: dict, render) -> None:
    """Render everything first; publish a journal before changing any live file."""
    with LOCK:
        recover(directory)
        stage=Path(tempfile.mkdtemp(dir=directory,prefix='.edit-'))
        journal=directory/JOURNAL
        try:
            # Only copy assets belonging to this article; no arbitrary directory traversal.
            for image in article.get('images',[]):
                key=image['id']
                if not isinstance(key,str) or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in key):
                    raise ValueError('Invalid article image ID')
                for extension in ('png','jpg'):
                    name=f'images/{key}.{extension}'
                    source=_target(directory,name)
                    if source.is_file():atomic_bytes(stage/name,source.read_bytes())
            for name,body in updates.items():
                if body is None:_target(stage,name).unlink(missing_ok=True)
                else:atomic_bytes(_target(stage,name),body)
            render(article,stage,stage)
            names=list(dict.fromkeys([*updates,'article.md','image-prompts.md','article.docx']))
            entries=[]
            for name in names:
                target=_target(directory,name)
                existed=target.is_file()
                if existed:atomic_bytes(_target(stage/'before',name),target.read_bytes())
                entries.append({'name':name,'existed':existed})
            atomic_bytes(journal,json_bytes({'stage':stage.name,'files':entries}))
            try:
                for entry in entries:
                    name=entry['name']
                    if name in updates and updates[name] is None:_target(directory,name).unlink(missing_ok=True)
                    else:atomic_bytes(_target(directory,name),_target(stage,name).read_bytes())
            except BaseException:
                recover(directory)
                raise
            journal.unlink()
        finally:
            # Keep backups if rollback itself failed; the next read retries recovery.
            if not journal.exists():shutil.rmtree(stage,ignore_errors=True)
