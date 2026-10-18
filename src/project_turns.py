"""Narrow integration seams between Projects and upstream chat streaming."""
import asyncio
import json
from fastapi import HTTPException
from routes.project_routes import project_owner
from src.auth_helpers import effective_user
from src.projects import ProjectStore, ProjectError
from src.project_changes import ProjectChanges
from src.project_terminal import execute_command


PROJECT_FILE_TOOLS = frozenset({'get_workspace','ls','glob','grep','read_file','write_file','edit_file','apply_patch','todowrite','update_plan'})


def project_agent_tools(project, disabled=(), plan_mode=False):
    """Expose a small language-independent file toolset; never grant privileges."""
    if not project:
        return set()
    tools = set(PROJECT_FILE_TOOLS) - set(disabled or ())
    if plan_mode:
        from src.tool_security import PLAN_MODE_READONLY_TOOLS
        tools.intersection_update(PLAN_MODE_READONLY_TOOLS)
    return tools


def resolve_project_context(request, session_id, posted_project, references, store=None):
    store = store or ProjectStore()
    owner = effective_user(request) or '_local'
    project = store.for_session(owner, session_id)
    if posted_project and (not project or project['id'] != posted_project):
        raise ProjectError('Project selection changed; reopen the chat before sending', 409)
    if project:
        project_owner(request)
    if references and not project:
        raise ProjectError('File references require a project chat')
    text = store.references(owner, project['id'], references) if references and project else ''
    return project, text


async def settle_project_predecessor(session_id, timeout=10):
    """Finish the replaced run's snapshot cleanup before acquiring its directory."""
    from src import agent_runs
    run = agent_runs.get_active_run(session_id)
    if run is None or run.task is None:
        return
    agent_runs.stop(session_id, run.run_id)
    done, _ = await asyncio.wait({run.task}, timeout=timeout)
    if not done:
        raise HTTPException(409, 'The previous operation is stopping. Wait for cleanup, then retry.')


def begin_project_review(owner, project, session_id):
    if not project:
        return None
    try:
        return ProjectChanges(ProjectStore()).begin(owner or '_local', project['id'], session_id)
    except ProjectError as exc:
        raise HTTPException(exc.status, str(exc)) from exc


def finish_project_review(turn, interrupted=False):
    if not turn:
        return None
    return ProjectChanges(ProjectStore()).finish(turn, interrupted)


async def terminal_stream(command, original_message, cwd, sess, session_manager, turn=None):
    """Stream explicit human shell output and persist it as a normal chat exchange."""
    from core.models import ChatMessage
    prefix = f'Terminal · {cwd}\n\n```text\n'
    chunks = []
    queue = asyncio.Queue(maxsize=64)

    async def output(text):
        await queue.put(text)

    sess.add_message(ChatMessage('user', original_message))
    session_manager.save_sessions()
    task = asyncio.create_task(execute_command(command, cwd, on_output=output))
    interrupted = True
    text = prefix
    try:
        yield f'data: {json.dumps({"type": "model_info", "model": "Terminal", "suffix": "Direct command"})}\n\n'
        yield f'data: {json.dumps({"delta": prefix})}\n\n'
        while not task.done() or not queue.empty():
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=0.15)
            except asyncio.TimeoutError:
                continue
            chunks.append(chunk)
            yield f'data: {json.dumps({"delta": chunk})}\n\n'
        result = await task
        ending = '\n```\nExit code: ' + str(result['exit_code'])
        if result['timed_out']:
            ending += ' · stopped after 120 seconds'
        if result['truncated']:
            ending += ' · output limited to 256 KiB'
        text = prefix + ''.join(chunks) + ending
        sess.add_message(ChatMessage('assistant', text, metadata={'terminal': True, 'exit_code': result['exit_code']}))
        session_manager.save_sessions()
        interrupted = False
        yield f'data: {json.dumps({"delta": ending})}\n\n'
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        finish_project_review(turn, interrupted)
    if turn:
        yield f'data: {json.dumps({"type": "project_review", "id": turn})}\n\n'
    yield 'data: [DONE]\n\n'
