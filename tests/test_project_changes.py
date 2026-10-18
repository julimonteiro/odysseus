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

def test_delete_project_is_atomic_while_child_directory_has_active_turn(setup,tmp_path):
    s,c,p,root=setup
    other=tmp_path/'other';other.mkdir()
    child=s.create('alice','Child',str(other),p['id']);s.attach('alice',p['id'],'keep-chat')
    turn=c.begin('alice',child['id'],'running')
    with pytest.raises(ProjectError):s.archive('alice',p['id'])
    assert len(s.list('alice'))==2
    assert s.memberships('alice')=={'keep-chat':p['id']}
    c.finish(turn);s.archive('alice',p['id'])
    assert s.list('alice')==[]

def test_conversation_reviews_are_owned_paginated_and_survive_project_removal(setup):
    s,c,p,root=setup
    (root/'code.py').write_text('a=1\n')
    first=c.begin('alice',p['id'],'chat-a');(root/'code.py').write_text('a=2\n');c.finish(first)
    other=c.begin('alice',p['id'],'chat-b');(root/'code.py').write_text('a=3\n');c.finish(other)
    second=c.begin('alice',p['id'],'chat-a');(root/'code.py').write_text('a=4\n');c.finish(second)
    s.archive('alice',p['id'])
    page=c.list_session('alice','chat-a',limit=1)
    assert [r['id'] for r in page['reviews']]==[second]
    older=c.list_session('alice','chat-a',cursor=page['next_cursor'],limit=1)
    assert [r['id'] for r in older['reviews']]==[first] and older['next_cursor'] is None
    assert c.list_session('bob','chat-a')['reviews']==[]
    assert c.session_file_diff('alice','chat-a',first,'code.py')['after']=='a=2\n'
    with pytest.raises(ProjectError):c.session_file_diff('alice','chat-b',first,'code.py')
    with pytest.raises(ProjectError):c.list_session('alice','chat-a',cursor=other)
