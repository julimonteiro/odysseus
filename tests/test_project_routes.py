from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from src.projects import ProjectStore
from routes.project_routes import setup_project_routes

@pytest.fixture
def api(tmp_path,monkeypatch):
    monkeypatch.setattr('routes.project_routes.live_chat_ids',lambda owner:set())
    monkeypatch.setattr('routes.project_routes.require_admin',lambda r:None)
    monkeypatch.setattr('routes.project_routes.is_delegated_credential',lambda r:False)
    app=FastAPI()
    @app.middleware('http')
    async def identity(request,call_next):
        request.state.current_user=request.headers.get('X-Test-User','alice')
        return await call_next(request)
    app.include_router(setup_project_routes(ProjectStore(tmp_path/'data')))
    return TestClient(app),tmp_path

def test_create_list_browse_and_isolation(api):
    c,path=api;root=path/'work';root.mkdir();(root/'a.txt').write_text('hello')
    r=c.post('/api/projects',json={'name':'Site','root':str(root)});assert r.status_code==200
    pid=r.json()['id']
    assert len(c.get('/api/projects').json()['projects'])==1
    assert c.get('/api/projects',headers={'X-Test-User':'bob'}).json()['projects']==[]
    assert c.get(f'/api/projects/{pid}/files').json()['files']==['a.txt']
    assert c.get(f'/api/projects/{pid}/files',headers={'X-Test-User':'bob'}).status_code==404
    assert c.post(f'/api/projects/{pid}/directories',json={'path':'../bad'}).status_code==400

def test_delegated_credentials_cannot_access_host(api,monkeypatch):
    c,path=api;monkeypatch.setattr('routes.project_routes.is_delegated_credential',lambda r:True)
    assert c.get('/api/projects').status_code==403
