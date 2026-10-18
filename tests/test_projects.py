from pathlib import Path
import pytest
from src.projects import ProjectStore, ProjectError

@pytest.fixture
def store(tmp_path):
    return ProjectStore(tmp_path / 'state')

@pytest.fixture
def root(tmp_path):
    p=tmp_path/'work';p.mkdir();return p.resolve()

def test_owned_projects_persist_and_inherit_root(store,root):
    p=store.create('alice','Site',str(root))
    child=store.create('alice','Backend','',p['id'])
    assert child['root']==str(root)
    assert len(ProjectStore(store.directory).list('alice'))==2
    assert store.list('bob')==[]
    with pytest.raises(ProjectError):store.get('bob',p['id'])

def test_association_requires_access_and_rejects_missing_binding(store,root):
    p=store.create('alice','Site',str(root));store.attach('alice',p['id'],'chat-1')
    assert store.for_session('alice','chat-1')['root']==str(root)
    assert store.for_session('bob','chat-1') is None
    with store.connect(True) as db:
        db.execute('UPDATE projects SET archived=1 WHERE id=?',(p['id'],))
    with pytest.raises(ProjectError):store.for_session('alice','chat-1')

def test_file_reference_confines_and_marks_untrusted(store,root,tmp_path):
    p=store.create('alice','Site',str(root));(root/'hello world.txt').write_text('Hello café')
    assert 'Hello café' in store.references('alice',p['id'],['hello world.txt'])
    assert 'untrusted' in store.references('alice',p['id'],['hello world.txt']).lower()
    outside=tmp_path/'outside.txt';outside.write_text('secret');(root/'link').symlink_to(outside)
    for name in ['../outside.txt','link','.env']:
        with pytest.raises(ProjectError):store.references('alice',p['id'],[name])

def test_binary_and_oversize_references_fail(store,root):
    p=store.create('alice','Site',str(root));(root/'x.bin').write_bytes(b'a\x00b');(root/'big.txt').write_text('x'*65537)
    for name in ['x.bin','big.txt']:
        with pytest.raises(ProjectError):store.references('alice',p['id'],[name])

def test_browse_and_folder_creation_remain_inside_project(store,root):
    p=store.create('alice','Site',str(root));store.mkdir('alice',p['id'],'src/new')
    (root/'src'/'new'/'a.py').write_text('x')
    assert store.files('alice',p['id'],'a.py')['files']==['src/new/a.py']
    with pytest.raises(ProjectError):store.mkdir('alice',p['id'],'../escape')

def test_project_with_chats_cannot_be_removed_until_chats_moved(store,root):
    p=store.create('alice','Site',str(root));store.attach('alice',p['id'],'chat')
    with pytest.raises(ProjectError):store.archive('alice',p['id'])
    store.detach('alice','chat');store.archive('alice',p['id'])
    assert store.list('alice')==[]

def test_git_branch_tracks_checkout_and_handles_non_repository(store,root):
    import subprocess
    p=store.create('alice','Site',str(root))
    assert store.git_info('alice',p['id'])['repository'] is False
    subprocess.run(['git','init','-b','main',str(root)],check=True,capture_output=True)
    assert store.git_info('alice',p['id'])['branch']=='main'
    subprocess.run(['git','-C',str(root),'symbolic-ref','HEAD','refs/heads/feature/demo'],check=True,capture_output=True)
    assert store.git_info('alice',p['id'])['branch']=='feature/demo'

def test_prune_deleted_chat_memberships_preserves_live_and_other_owners(store,root):
    p=store.create('alice','Site',str(root));other=store.create('bob','Other',str(root))
    store.attach('alice',p['id'],'deleted');store.attach('alice',p['id'],'live')
    store.attach('bob',other['id'],'bob-chat')
    store.prune_memberships('alice',{'live'})
    assert store.memberships('alice')=={'live':p['id']}
    assert store.memberships('bob')=={'bob-chat':other['id']}
    store.prune_memberships('alice',set());store.archive('alice',p['id'])
