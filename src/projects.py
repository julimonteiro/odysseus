"""Directory-backed projects. Fork extension; no changes to upstream session schema."""
from contextlib import contextmanager
from pathlib import Path
import json
import os
import sqlite3
import time
import uuid


class ProjectError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def checked_path(root, relative):
    from src.tool_execution import _resolve_tool_path_in_workspace
    if not isinstance(relative, str) or not relative or os.path.isabs(relative):
        raise ProjectError('Use a relative project path')
    if any(part == '..' for part in Path(relative).parts):
        raise ProjectError('Path must stay inside the project')
    try:
        return Path(_resolve_tool_path_in_workspace(root, relative))
    except ValueError as exc:
        raise ProjectError(str(exc), 403) from exc


EXCLUDED_DIRS = {'.git', '.hg', '.svn', 'node_modules', 'venv', '.venv', '__pycache__', '.next', 'dist', 'build', '.superpowers'}
MAX_FILES = 2000


def scan_text(root, max_bytes=20 * 1024 * 1024, per_file=1024 * 1024):
    """Bounded, deterministic text inventory with explicit coverage metadata."""
    files, excluded, visited, total = {}, [], 0, 0
    directories = 0
    truncated = False
    for base, dirs, names in os.walk(root, followlinks=False):
        directories += 1
        if directories > MAX_FILES:
            truncated = True
            break
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS and not Path(base, d).is_symlink())
        for name in sorted(names):
            visited += 1
            if visited > MAX_FILES:
                truncated = True
                break
            p = Path(base, name)
            rel = p.relative_to(root).as_posix()
            try:
                if p.is_symlink():
                    raise ProjectError('symlink')
                safe = checked_path(root, rel)
                if not safe.is_file():
                    raise ProjectError('not a regular file')
                if safe.stat().st_size > per_file:
                    raise ProjectError('file size limit')
                with safe.open('rb') as fh:
                    data = fh.read(per_file + 1)
                if len(data) > per_file:
                    raise ProjectError('file size limit')
                if b'\x00' in data:
                    raise ProjectError('binary')
                text = data.decode('utf-8')
                if total + len(data) > max_bytes:
                    truncated = True
                    raise ProjectError('total size limit')
                total += len(data)
                files[rel] = text
            except (OSError, UnicodeError, ProjectError) as exc:
                excluded.append({'path': rel, 'reason': str(exc) if isinstance(exc, ProjectError) else 'unreadable or non-UTF8'})
        if visited > MAX_FILES:
            break
    return {'files': files, 'coverage': {'excluded': excluded, 'truncated': truncated, 'bytes': total,
            'file_count': len(files), 'limits': {'files': MAX_FILES, 'total_bytes': max_bytes, 'file_bytes': per_file},
            'ignored_directories': sorted(EXCLUDED_DIRS)}}


class ProjectStore:
    def __init__(self, directory=None):
        if directory is None:
            from src.constants import DATA_DIR
            directory = Path(DATA_DIR) / 'projects'
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db_path = self.directory / 'projects.sqlite3'
        with self.connect() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, owner TEXT NOT NULL,
                name TEXT NOT NULL, root TEXT NOT NULL, parent_id TEXT, archived INTEGER DEFAULT 0,
                created_at REAL NOT NULL);
              CREATE TABLE IF NOT EXISTS memberships (session_id TEXT PRIMARY KEY, owner TEXT NOT NULL, project_id TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS turns (id TEXT PRIMARY KEY, owner TEXT NOT NULL, project_id TEXT NOT NULL,
                session_id TEXT, root TEXT NOT NULL, status TEXT NOT NULL, pid INTEGER, started REAL NOT NULL,
                finished REAL, summary TEXT);
              CREATE INDEX IF NOT EXISTS turns_session_history ON turns(owner,session_id,started DESC,id DESC);
            ''')
        try:
            self.db_path.chmod(0o600)
        except OSError:
            pass

    @contextmanager
    def connect(self, write=False):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            if write:
                db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def list(self, owner):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM projects WHERE owner=? AND archived=0 ORDER BY created_at', (owner,))]

    def get(self, owner, project_id):
        with self.connect() as db:
            r = db.execute('SELECT * FROM projects WHERE id=? AND owner=?', (project_id, owner)).fetchone()
        if not r:
            raise ProjectError('Project not found', 404)
        if r['archived']:
            raise ProjectError('Project is archived', 409)
        from src.tool_execution import vet_workspace
        if not vet_workspace(r['root']):
            raise ProjectError('Project directory is unavailable or no longer permitted', 409)
        return dict(r)

    def create(self, owner, name, root='', parent_id=None):
        from src.tool_execution import vet_workspace
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
            raise ProjectError('Project name is required (maximum 100 characters)')
        parent = self.get(owner, parent_id) if parent_id else None
        resolved = vet_workspace(root or (parent['root'] if parent else ''))
        if not resolved:
            raise ProjectError('Choose an existing permitted directory')
        p = {'id': uuid.uuid4().hex, 'owner': owner, 'name': name.strip(), 'root': resolved,
             'parent_id': parent_id, 'archived': 0, 'created_at': time.time()}
        with self.connect(True) as db:
            db.execute('INSERT INTO projects VALUES (:id,:owner,:name,:root,:parent_id,:archived,:created_at)', p)
        return p

    def _assert_idle(self, db, roots):
        for r in db.execute("SELECT * FROM turns WHERE status='running'").fetchall():
            try:
                os.kill(r['pid'], 0)
            except ProcessLookupError:
                db.execute("UPDATE turns SET status='interrupted',finished=? WHERE id=?", (time.time(), r['id']))
                continue
            except (PermissionError, OSError):
                pass
            for root in roots:
                try:
                    common = os.path.commonpath([root, r['root']])
                except ValueError:
                    continue
                if common in (root, r['root']):
                    raise ProjectError('Another tracked operation is active in this directory. Wait for it to finish.', 409)

    def archive(self, owner, project_id):
        with self.connect(True) as db:
            if not db.execute("SELECT 1 FROM projects WHERE id=? AND owner=? AND archived=0", (project_id, owner)).fetchone():
                raise ProjectError("Project not found", 404)
            rows = db.execute("""WITH RECURSIVE subtree(id, root) AS (
                SELECT id, root FROM projects WHERE id=? AND owner=? AND archived=0
                UNION ALL SELECT p.id, p.root FROM projects p JOIN subtree s ON p.parent_id=s.id
                WHERE p.owner=? AND p.archived=0
            ) SELECT id, root FROM subtree""", (project_id, owner, owner)).fetchall()
            self._assert_idle(db, [r['root'] for r in rows])
            for r in rows:
                db.execute('DELETE FROM memberships WHERE project_id=? AND owner=?', (r['id'], owner))
                db.execute('UPDATE projects SET archived=1 WHERE id=? AND owner=?', (r['id'], owner))

    def attach(self, owner, project_id, session_id):
        p = self.get(owner, project_id)
        with self.connect(True) as db:
            old = db.execute('SELECT * FROM memberships WHERE session_id=?', (session_id,)).fetchone()
            if old and old['owner'] != owner:
                raise ProjectError('Chat belongs to another user', 403)
            roots = [p['root']]
            if old:
                prior = db.execute('SELECT root FROM projects WHERE id=?', (old['project_id'],)).fetchone()
                if prior:
                    roots.append(prior['root'])
            self._assert_idle(db, roots)
            db.execute('INSERT OR REPLACE INTO memberships VALUES (?,?,?)', (session_id, owner, project_id))

    def for_session(self, owner, session_id):
        with self.connect() as db:
            r = db.execute('SELECT project_id FROM memberships WHERE session_id=? AND owner=?', (session_id, owner)).fetchone()
        return self.get(owner, r['project_id']) if r else None

    def memberships(self, owner):
        with self.connect() as db:
            return {r['session_id']: r['project_id'] for r in db.execute('SELECT * FROM memberships WHERE owner=?', (owner,))}

    def prune_memberships(self, owner, valid_session_ids):
        """Remove deleted chats only within this owner’s memberships."""
        valid = set(valid_session_ids)
        with self.connect(True) as db:
            stale = [(r["session_id"], owner) for r in db.execute(
                "SELECT session_id FROM memberships WHERE owner=?", (owner,)) if r["session_id"] not in valid]
            db.executemany("DELETE FROM memberships WHERE session_id=? AND owner=?", stale)

    def detach(self, owner, session_id):
        p = self.for_session(owner, session_id)
        with self.connect(True) as db:
            if p:
                self._assert_idle(db, [p['root']])
            db.execute('DELETE FROM memberships WHERE session_id=? AND owner=?', (session_id, owner))

    def git_info(self, owner, project_id):
        import subprocess
        p = self.get(owner, project_id)
        def git(*args):
            return subprocess.run(['git', '-c', 'core.fsmonitor=false', '-C', p['root'], *args],
                                  capture_output=True, text=True, timeout=3)
        try:
            info = git('rev-parse', '--show-toplevel')
            if info.returncode:
                return {'repository': False, 'branch': None, 'detached': False}
            branch = git('symbolic-ref', '--quiet', '--short', 'HEAD')
            if branch.returncode == 0:
                return {'repository': True, 'branch': branch.stdout.strip()[:200], 'detached': False}
            commit = git('rev-parse', '--short', 'HEAD')
            return {'repository': True, 'branch': None, 'detached': True, 'commit': commit.stdout.strip()[:40]}
        except (OSError, subprocess.TimeoutExpired):
            return {'repository': False, 'branch': None, 'detached': False, 'unavailable': True}

    def files(self, owner, project_id, query=''):
        p = self.get(owner, project_id)
        inventory = scan_text(p['root'], max_bytes=20*1024*1024)
        return {'files': [name for name in inventory['files'] if query.casefold() in name.casefold()][:200],
                'coverage': inventory['coverage']}

    def browse(self, owner, project_id, relative='.'):
        p = self.get(owner, project_id)
        target = checked_path(p['root'], relative)
        if not target.is_dir():
            raise ProjectError('Directory not found', 404)
        entries = []
        for x in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold())):
            rel = x.relative_to(p['root']).as_posix()
            if x.is_symlink() or x.name in EXCLUDED_DIRS:
                continue
            try:
                checked_path(p['root'], rel)
            except ProjectError:
                continue
            entries.append({'name': x.name, 'path': rel, 'directory': x.is_dir()})
            if len(entries) == 500:
                break
        return {'path': relative, 'entries': entries}

    def mkdir(self, owner, project_id, relative):
        p = self.get(owner, project_id)
        target = checked_path(p['root'], relative)
        target.mkdir(parents=True, exist_ok=False)
        return {'path': target.relative_to(p['root']).as_posix()}

    def references(self, owner, project_id, paths):
        if not isinstance(paths, list) or len(paths) > 12 or not all(isinstance(p, str) for p in paths):
            raise ProjectError('Select up to 12 project files')
        p = self.get(owner, project_id)
        out, total = [], 0
        for rel in dict.fromkeys(paths):
            target = checked_path(p['root'], rel)
            try:
                if not target.is_file():
                    raise ProjectError(f'Not a regular project file: {rel}')
                with target.open('rb') as f:
                    data = f.read(65537)
            except OSError as exc:
                raise ProjectError(f'Cannot read project file: {rel}', 404) from exc
            if len(data) > 65536 or total + len(data) > 131072:
                raise ProjectError('File reference exceeds the 64 KiB per-file or 128 KiB total limit')
            if b'\x00' in data:
                raise ProjectError('Binary files cannot be included as text references')
            try:
                text = data.decode('utf-8')
            except UnicodeError as exc:
                raise ProjectError('File reference must be UTF-8 text') from exc
            total += len(data)
            from src.prompt_security import untrusted_context_message
            out.append(untrusted_context_message(f'project file {rel}', text)['content'])
        return '\n\n'.join(out)
