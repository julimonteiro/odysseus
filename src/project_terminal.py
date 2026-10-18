"""Explicit !commands are human terminal requests, never model/tool instructions."""
import asyncio
import os
import signal


def command_from_message(message):
    if isinstance(message, str) and message.startswith('!'):
        return message[1:].strip() or None
    return None


async def execute_command(command, cwd, timeout=120, on_output=None):
    if not command or len(command) > 32768:
        raise ValueError('A command is required (maximum 32768 characters)')
    # Avoid passing server API keys and internal authorization tokens to child
    # processes. A login shell still loads the user's normal shell profile.
    names = {'PATH', 'HOME', 'USER', 'LOGNAME', 'SHELL', 'LANG', 'LC_ALL', 'TMPDIR', 'SSH_AUTH_SOCK', 'TERM', 'SYSTEMROOT', 'COMSPEC'}
    env = {k: v for k, v in os.environ.items() if k in names}
    env.setdefault('TERM', 'dumb')
    if os.name == 'nt':
        args = [os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/s', '/c', command]
    else:
        shell = os.environ.get('SHELL', '/bin/sh')
        args = [shell, '-lc', command]
    proc = await asyncio.create_subprocess_exec(*args, cwd=cwd, env=env, stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, start_new_session=(os.name != 'nt'))
    output = bytearray()
    truncated = False
    timed_out = False

    async def drain():
        nonlocal truncated
        while True:
            chunk = await proc.stdout.read(4096)
            if not chunk:
                break
            room = max(0, 262144 - len(output))
            output.extend(chunk[:room])
            if on_output is not None and room:
                await on_output(chunk[:room].decode('utf-8', errors='replace'))
            if len(chunk) > room:
                truncated = True
        await proc.wait()

    def kill():
        try:
            if os.name == 'nt':
                proc.kill()
            else:
                os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    try:
        await asyncio.wait_for(drain(), timeout)
    except asyncio.TimeoutError:
        timed_out = True
        kill()
        await proc.wait()
    except BaseException:
        kill()
        await proc.wait()
        raise
    return {'output': output.decode('utf-8', errors='replace'), 'exit_code': proc.returncode,
            'timed_out': timed_out, 'truncated': truncated, 'cwd': cwd}
