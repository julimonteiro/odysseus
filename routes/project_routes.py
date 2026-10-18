"""Projects extension API: ownership and host access policy remain upstream-owned."""
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, Field
from core.middleware import require_admin
from src.auth_helpers import effective_user, is_delegated_credential
from src.projects import ProjectStore, ProjectError
from src.project_changes import ProjectChanges


class ProjectInput(BaseModel):
    name: str = Field(max_length=100)
    root: str = Field(default='', max_length=4096)
    parent_id: str | None = None


class PathInput(BaseModel):
    path: str = Field(max_length=4096)


class MembershipInput(BaseModel):
    project_id: str | None = None


def project_owner(request):
    require_admin(request)
    if is_delegated_credential(request):
        raise HTTPException(403, 'Host projects require an administrator browser session')
    return effective_user(request) or '_local'


def assert_chat_owner(owner, session_id):
    from core.database import SessionLocal, Session
    with SessionLocal() as db:
        s = db.query(Session).filter(Session.id == session_id).first()
        if not s or (s.owner or '_local') != owner:
            raise HTTPException(404, 'Chat not found')


def live_chat_ids(owner):
    from core.database import SessionLocal, Session
    with SessionLocal() as db:
        return {s.id for s in db.query(Session).all() if (s.owner or "_local") == owner}


def setup_project_routes(store=None):
    store = store or ProjectStore()
    changes = ProjectChanges(store)
    router = APIRouter(prefix='/api/projects', tags=['projects'])

    def call(fn, *args):
        try:
            return fn(*args)
        except ProjectError as exc:
            raise HTTPException(exc.status, str(exc)) from exc
        except (FileExistsError, PermissionError) as exc:
            raise HTTPException(409, 'Directory already exists or is not writable') from exc

    @router.get('')
    def list_projects(request: Request):
        owner = project_owner(request)
        store.prune_memberships(owner, live_chat_ids(owner))
        return {'projects': store.list(owner), 'memberships': store.memberships(owner)}

    @router.post('')
    def create_project(body: ProjectInput, request: Request):
        return call(store.create, project_owner(request), body.name, body.root, body.parent_id)

    @router.put('/sessions/{session_id}')
    def associate(session_id: str, body: MembershipInput, request: Request):
        owner = project_owner(request)
        assert_chat_owner(owner, session_id)
        if body.project_id:
            call(store.attach, owner, body.project_id, session_id)
        else:
            call(store.detach, owner, session_id)
        return {'ok': True}

    @router.get('/sessions/{session_id}')
    def session_project(session_id: str, request: Request):
        owner = project_owner(request)
        assert_chat_owner(owner, session_id)
        return {'project': call(store.for_session, owner, session_id)}

    @router.delete('/{project_id}')
    def archive(project_id: str, request: Request):
        owner = project_owner(request)
        store.prune_memberships(owner, live_chat_ids(owner))
        call(store.archive, owner, project_id)
        return {'ok': True, 'files_deleted': False}

    @router.get('/{project_id}/git')
    def git_info(project_id: str, request: Request):
        return call(store.git_info, project_owner(request), project_id)

    @router.get('/{project_id}/files')
    def files(project_id: str, request: Request, q: str = Query('', max_length=200)):
        return call(store.files, project_owner(request), project_id, q)

    @router.get('/{project_id}/browse')
    def browse(project_id: str, request: Request, path: str = Query('.', max_length=4096)):
        return call(store.browse, project_owner(request), project_id, path)

    @router.post('/{project_id}/directories')
    def mkdir(project_id: str, body: PathInput, request: Request):
        return call(store.mkdir, project_owner(request), project_id, body.path)

    @router.get('/{project_id}/reviews')
    def reviews(project_id: str, request: Request):
        return {'reviews': call(changes.list, project_owner(request), project_id)}

    @router.get('/{project_id}/reviews/{turn_id}/file')
    def diff_file(project_id: str, turn_id: str, request: Request, path: str = Query(..., max_length=4096)):
        return call(changes.file_diff, project_owner(request), project_id, turn_id, path)

    return router
