import asyncio
import pytest
from src.project_terminal import command_from_message, execute_command

@pytest.mark.parametrize('text,result',[('!pwd','pwd'),('! git status','git status'),('hi !pwd',None),(' !pwd',None),('!',None)])
def test_prefix_is_exactly_first_character(text,result):
    assert command_from_message(text)==result

@pytest.mark.asyncio
async def test_terminal_runs_in_workspace_without_llm_and_does_not_persist_cd(tmp_path):
    r=await execute_command('pwd',str(tmp_path.resolve()))
    assert r['exit_code']==0 and str(tmp_path.resolve()) in r['output']
    r=await execute_command("printf 'hello terminal'",str(tmp_path.resolve()))
    assert r['output']=='hello terminal'

@pytest.mark.asyncio
async def test_terminal_timeout_kills_group_and_reports_failure(tmp_path):
    r=await execute_command('sleep 10',str(tmp_path.resolve()),timeout=0.1)
    assert r['timed_out'] and r['exit_code']!=0

@pytest.mark.asyncio
async def test_terminal_stream_disconnect_after_first_event_stops_child(monkeypatch,tmp_path):
    from src.project_turns import terminal_stream
    from types import SimpleNamespace
    finished=[];cancelled=[]
    async def long_command(*args,**kwargs):
        try:await asyncio.sleep(10)
        finally:cancelled.append(True)
    monkeypatch.setattr('src.project_turns.execute_command',long_command)
    monkeypatch.setattr('src.project_turns.finish_project_review',lambda turn,interrupted:finished.append((turn,interrupted)))
    gen=terminal_stream('sleep 10','!sleep 10',str(tmp_path),SimpleNamespace(add_message=lambda m:None),SimpleNamespace(save_sessions=lambda:None),'turn')
    await anext(gen);await asyncio.sleep(0)
    await gen.aclose()
    assert cancelled and finished==[('turn',True)]
