from types import SimpleNamespace
import pytest
from src.projects import ProjectStore, ProjectError
from src.project_turns import resolve_project_context

@pytest.fixture
def scoped(tmp_path,monkeypatch):
    root=(tmp_path/'work');root.mkdir();store=ProjectStore(tmp_path/'state');p=store.create('alice','Site',str(root));store.attach('alice',p['id'],'chat')
    request=SimpleNamespace(state=SimpleNamespace(current_user='alice'),app=SimpleNamespace())
    monkeypatch.setattr('src.project_turns.project_owner',lambda request:'alice')
    return store,p,request

def test_server_project_binding_overrides_browser_workspace(scoped):
    store,p,r=scoped
    project,refs=resolve_project_context(r,'chat',None,[],store)
    assert project['root']==p['root'] and refs==''
    with pytest.raises(ProjectError):resolve_project_context(r,'chat','wrong',[],store)

def test_archived_project_never_falls_back_to_global_workspace(scoped):
    s,p,r=scoped
    with s.connect(True) as db:db.execute('UPDATE projects SET archived=1 WHERE id=?',(p['id'],))
    with pytest.raises(ProjectError):resolve_project_context(r,'chat',None,[],s)
