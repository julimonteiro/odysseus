"""Bounded before/after snapshots, including changes made by shell commands."""
from pathlib import Path
import json
import os
import time
import uuid
from src.projects import ProjectError, scan_text


class ProjectChanges:
    def __init__(self, store):
        self.store = store
        self.directory = store.directory / 'reviews'
        self.directory.mkdir(exist_ok=True)

    def _path(self, turn_id, kind):
        if not isinstance(turn_id, str) or len(turn_id) != 32 or any(c not in '0123456789abcdef' for c in turn_id):
            raise ProjectError('Review not found', 404)
        return self.directory / f'{turn_id}-{kind}.json'

    def _write(self, turn, kind, data):
        p = self._path(turn, kind)
        temp = p.with_suffix('.tmp')
        with temp.open('w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        temp.chmod(0o600)
        os.replace(temp, p)

    def begin(self, owner, project_id, session_id):
        p = self.store.get(owner, project_id)
        turn = uuid.uuid4().hex
        with self.store.connect(True) as db:
            self.store._assert_idle(db, [p['root']])
            db.execute('INSERT INTO turns (id,owner,project_id,session_id,root,status,pid,started) VALUES (?,?,?,?,?,?,?,?)',
                       (turn, owner, project_id, session_id, p['root'], 'running', os.getpid(), time.time()))
        try:
            baseline = scan_text(p['root'])
            self._write(turn, 'before', baseline)
        except BaseException:
            with self.store.connect(True) as db:
                db.execute("UPDATE turns SET status='incomplete',finished=? WHERE id=?", (time.time(), turn))
            raise
        return turn

    def finish(self, turn, interrupted=False):
        with self.store.connect() as db:
            r = db.execute('SELECT * FROM turns WHERE id=?', (turn,)).fetchone()
        if not r:
            raise ProjectError('Review not found', 404)
        status = 'interrupted' if interrupted else 'complete'
        try:
            before = json.loads(self._path(turn, 'before').read_text())
            after = scan_text(r['root'])
            excluded_before = {x['path'] for x in before['coverage']['excluded']}
            excluded_after = {x['path'] for x in after['coverage']['excluded']}
            partial = before['coverage']['truncated'] or after['coverage']['truncated']
            changes = []
            for rel in sorted(before['files'].keys() | after['files'].keys()):
                if rel in excluded_before or rel in excluded_after:
                    continue
                old, new = before['files'].get(rel), after['files'].get(rel)
                # An incomplete scan cannot prove addition/deletion.
                if partial and (old is None or new is None):
                    continue
                if old != new:
                    changes.append({'path': rel, 'status': 'added' if old is None else 'deleted' if new is None else 'modified',
                                    'before': old or '', 'after': new or ''})
            result = {'id': turn, 'status': status, 'partial': partial, 'changes': changes,
                      'coverage': {'before': before['coverage'], 'after': after['coverage'],
                                   'excluded': before['coverage']['excluded'] + after['coverage']['excluded']},
                      'note': 'Changes since the turn started; concurrent manual edits can also appear.'}
            self._write(turn, 'result', result)
        except Exception as exc:
            status = 'incomplete'
            result = {'id': turn, 'status': status, 'partial': True, 'changes': [],
                      'coverage': {}, 'note': 'Comparison unavailable; this is not evidence that no files changed.'}
            self._write(turn, 'result', result)
        with self.store.connect(True) as db:
            summary = {**result, 'changes': [{'path': c['path'], 'status': c['status']} for c in result['changes']]}
            db.execute('UPDATE turns SET status=?,finished=?,summary=? WHERE id=?', (status, time.time(), json.dumps(summary), turn))
        return result

    def list(self, owner, project_id):
        self.store.get(owner, project_id)
        with self.store.connect() as db:
            rows = db.execute('SELECT * FROM turns WHERE owner=? AND project_id=? ORDER BY started DESC LIMIT 50', (owner, project_id)).fetchall()
        return [{**{k: r[k] for k in ['id', 'session_id', 'status', 'started', 'finished']},
                 'summary': json.loads(r['summary']) if r['summary'] else None} for r in rows]

    def file_diff(self, owner, project_id, turn, relative):
        self.store.get(owner, project_id)
        with self.store.connect() as db:
            r = db.execute('SELECT * FROM turns WHERE id=? AND owner=? AND project_id=?', (turn, owner, project_id)).fetchone()
        if not r:
            raise ProjectError('Review not found', 404)
        try:
            result = json.loads(self._path(turn, 'result').read_text())
        except FileNotFoundError as exc:
            raise ProjectError('Review has not finished', 409) from exc
        for c in result['changes']:
            if c['path'] == relative:
                return c
        raise ProjectError('Changed file not found', 404)
