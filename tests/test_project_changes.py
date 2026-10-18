import pytest
from src.projects import ProjectStore, ProjectError
from src.project_changes import ProjectChanges

@pytest.fixture
def setup(tmp_path):
    root=(tmp_path/'work');root.mkdir();root=root.resolve()
    store=ProjectStore(tmp_path/'state');p=store.create('alice','Site',str(root))
    return store,ProjectChanges(store),p,root

def test_snapshot_tracks_modified_added_deleted_and_preserves_git(setup):
    s,c,p,root=setup;(root/'a.txt').write_text('before\n');(root/'gone').write_text('deleted');(root/'.git').mkdir();(root/'.git'/'index').write_text('untouched')
    turn=c.begin('alice',p['id'],'chat')
    (root/'a.txt').write_text('after\n');(root/'new').write_text('new');(root/'gone').unlink()
    r=c.finish(turn)
    assert {x['path']:x['status'] for x in r['changes']}=={'a.txt':'modified','gone':'deleted','new':'added'}
    assert (root/'.git'/'index').read_text()=='untouched'
    assert c.file_diff('alice',p['id'],turn,'a.txt')['before']=='before\n'
    with pytest.raises(ProjectError):c.file_diff('bob',p['id'],turn,'a.txt')

def test_overlapping_roots_lock_and_release(setup):
    s,c,p,root=setup;(root/'sub').mkdir();q=s.create('alice','Sub',str(root/'sub'))
    t=c.begin('alice',p['id'],'one')
    with pytest.raises(ProjectError):c.begin('alice',q['id'],'two')
    with pytest.raises(ProjectError):s.archive('alice',p['id'])
    c.finish(t)
    c.finish(c.begin('alice',q['id'],'two'))

def test_sensitive_binary_coverage_and_missing_baseline(setup):
    s,c,p,root=setup;(root/'.env').write_text('TOKEN=secret');(root/'binary').write_bytes(b'\x00')
    t=c.begin('alice',p['id'],'one');r=c.finish(t)
    assert not r['changes']
    assert r['coverage']['excluded']
    assert 'secret' not in str(r)
