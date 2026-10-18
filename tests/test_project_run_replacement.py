import asyncio
import pytest
from src import agent_runs
from src.project_turns import settle_project_predecessor

@pytest.mark.asyncio
async def test_replacement_waits_for_existing_run_cleanup():
    cleaned=asyncio.Event()
    async def stream():
        try:
            yield 'data: ready\n\n'
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(.01)
            cleaned.set()
    run=agent_runs.start('replacement-test',stream())
    await asyncio.sleep(.01)
    await settle_project_predecessor('replacement-test')
    assert cleaned.is_set() and run.task.done()
    assert not agent_runs.is_active('replacement-test')

@pytest.mark.asyncio
async def test_missing_run_is_noop():
    await settle_project_predecessor('no-run')

@pytest.mark.asyncio
async def test_cleanup_timeout_does_not_start_a_replacement(monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    gate=asyncio.Event()
    task=asyncio.create_task(gate.wait())
    run=SimpleNamespace(task=task,run_id='old')
    monkeypatch.setattr(agent_runs,'get_active_run',lambda session:run)
    monkeypatch.setattr(agent_runs,'stop',lambda session,identity:True)
    try:
        with pytest.raises(HTTPException) as caught:
            await settle_project_predecessor('s',timeout=.01)
        assert caught.value.status_code==409 and not task.done()
    finally:
        task.cancel()
        await asyncio.gather(task,return_exceptions=True)
