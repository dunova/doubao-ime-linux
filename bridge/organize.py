"""Official smart text organization, with cancellation and transcript fallback.

The official executable and networking SDK run in their own pinned Wine prefix.
Speech text crosses stdin/stdout only; upstream logs and IDs are not persisted.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import signal
import tempfile
import sys
from cleanup import resolve_corrections, preservation_error
from runtime import ROOT, STATE, ORGANIZE_PREFIX, KEYBOARD_PREFIX, VERSION, config_path, wine

MAX_TEXT = 65536

class OrganizeError(RuntimeError):
    pass


def safe_text(value, multiline=True):
    if not isinstance(value, str) or not value.strip(): return False
    try:
        if len(value.encode('utf-8')) > MAX_TEXT: return False
    except UnicodeError: return False
    return not any((ord(c) < 32 and not (multiline and c == '\n')) or ord(c) == 127 for c in value)


def enabled():
    override = os.environ.get('DOUBAO_ORGANIZE_ENABLED')
    if override is not None: return override == '1'
    try:
        preference = STATE / 'smart-organize.json'
        if preference.exists():
            return json.loads(preference.read_text()).get('enabled') is True
        value = json.loads(config_path(KEYBOARD_PREFIX).read_text()).get('voice', {}).get('smartTextEnabled', False)
        return value is True
    except (OSError, ValueError, RuntimeError):
        return False


def set_enabled(value):
    if type(value) is not bool: raise ValueError('Expected a boolean preference')
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix='smart-organize-', dir=STATE)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump({'enabled':value}, stream); stream.write('\n')
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name, STATE/'smart-organize.json')
    finally:
        if os.path.exists(name): os.unlink(name)


def parse_sse(raw, original, status):
    if status != 200 or len(raw) > 1048576: raise OrganizeError('http-or-size')
    try: text = raw.decode('utf-8', errors='strict').replace('\r\n','\n')
    except UnicodeError: raise OrganizeError('invalid-utf8') from None
    complete = done = no_rewrite = False
    final = None
    fragments = []
    for block in text.split('\n\n'):
        if not block.strip(): continue
        event, data = '', []
        for line in block.split('\n'):
            if line.startswith(':'): continue
            if line.startswith('event:'): event = line[6:].strip()
            elif line.startswith('data:'): data.append(line[5:].lstrip(' '))
        if not event and not data: continue
        if done: raise OrganizeError('event-after-done')
        value = '\n'.join(data)
        if event == 'done':
            if value != '[DONE]' or not complete: raise OrganizeError('premature-done')
            done = True
            continue
        try: payload = json.loads(value)
        except (ValueError, TypeError): raise OrganizeError('invalid-json') from None
        if not isinstance(payload, dict): raise OrganizeError('invalid-payload')
        if event == 'scene.delta':
            if complete: raise OrganizeError('delta-after-completed')
            content = payload.get('content', '')
            if not isinstance(content,str): raise OrganizeError('invalid-content')
            flag = payload.get('no_rewrite', False)
            if type(flag) is not bool: raise OrganizeError('invalid-no-rewrite')
            no_rewrite = no_rewrite or flag
            fragments.append(content)
        elif event == 'scene.completed':
            if complete: raise OrganizeError('duplicate-completed')
            final = payload.get('content')
            if not isinstance(final,str): raise OrganizeError('missing-final-content')
            complete = True
        else:
            raise OrganizeError('remote-error' if event == 'scene.error' else 'unknown-event')
    if not complete or not done: raise OrganizeError('incomplete-stream')
    # The completed event is authoritative; it can revise the streamed layout.
    if no_rewrite:
        if final or any(fragments): raise OrganizeError('conflicting-no-rewrite')
        return original
    final = final.replace('\r\n','\n')
    if not safe_text(final): raise OrganizeError('unsafe-or-empty-result')
    return final


def runtime_ready():
    try:
        target = ORGANIZE_PREFIX/'drive_c/DoubaoIme/versions'/('v'+VERSION)
        manifest = json.loads((ORGANIZE_PREFIX/'.organize-checksums.json').read_text())
        for name in ('ImeService.exe','applogrs.dll','sscronet.dll','applogrs_original.dll','sscronet_original.dll'):
            if hashlib.sha256((target/name).read_bytes()).hexdigest() != manifest[name]: return False
        return True
    except (OSError, ValueError, KeyError): return False


class Organizer:
    def __init__(self, cancel):
        self.cancel = cancel
        self.process = self.reader = None
        self.status = None
        self.raw = bytearray()
        self.read_error = None
        self.ready = False

    async def start(self):
        if not runtime_ready(): raise OrganizeError('runtime-not-ready')
        try:
            credential = json.loads((STATE/'private/credentials.json').read_text())
            device_id = str(credential['device_id'])
            if not device_id.isascii() or not device_id.isdecimal() or not 0 < int(device_id) < 2**64:
                raise ValueError()
        except (OSError, ValueError, KeyError): raise OrganizeError('device-not-ready') from None
        env = dict(os.environ, DOUBAO_ORGANIZE_DEVICE_ID=device_id)
        self.process = await asyncio.create_subprocess_exec(sys.executable,
            str(ROOT/'scripts/headless.py'), '--prefix', 'organize', '--', wine(),
            rf'C:\DoubaoIme\versions\v{VERSION}\ImeService.exe',
            '--test-smart-organize', '--text', '__DOUBAO_UTF8_STDIN__',
            '--result-timeout-ms', '150000', '--warmup-ms', '12000',
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, env=env, start_new_session=True, limit=512*1024)
        self.reader = asyncio.create_task(self._read())

    async def _read(self):
        try:
            total = 0
            async for line in self.process.stdout:
                total += len(line)
                if total > 4*1048576: raise OrganizeError('oversized-native-output')
                if line.startswith(b'DOUBAO_READY'): self.ready = True
                elif line.startswith(b'DOUBAO_STATUS '): self.status = int(line[14:].strip())
                elif line.startswith(b'DOUBAO_SSE '):
                    self.raw.extend(bytes.fromhex(line[11:].decode('ascii').strip()))
                    if len(self.raw) > 1048576: raise OrganizeError('oversized-stream')
        except (ValueError, UnicodeError, OrganizeError) as error:
            self.read_error = type(error).__name__

    async def finish(self, text, timeout=25):
        if not safe_text(text): raise OrganizeError('unsafe-input')
        if self.cancel.is_set(): raise OrganizeError('cancelled')
        corrected = resolve_corrections(text)
        body = json.dumps({'query':corrected,'scene':6,'stream':True,
            'space_at_cn_en_nb':0,'space_at_newline':0},ensure_ascii=False,separators=(',',':'))+'\n'
        try:
            self.process.stdin.write(body.encode('utf-8'))
            await self.process.stdin.drain()
            deadline = asyncio.get_running_loop().time()+timeout
            while not self.reader.done():
                if self.cancel.is_set(): raise OrganizeError('cancelled')
                if asyncio.get_running_loop().time() > deadline: raise OrganizeError('timeout')
                await asyncio.sleep(.05)
            await self.reader
            if self.cancel.is_set(): raise OrganizeError('cancelled')
            if self.read_error or not self.ready: raise OrganizeError('invalid-native-output')
            result = parse_sse(bytes(self.raw), corrected, self.status)
            if preservation_error(corrected, result): raise OrganizeError('meaning-check')
            return result
        except (BrokenPipeError, ConnectionError): raise OrganizeError('native-exited') from None

    async def close(self):
        if self.process and self.process.returncode is None:
            try: self.process.terminate()
            except ProcessLookupError: pass
            try: await asyncio.wait_for(self.process.wait(), 12)
            except asyncio.TimeoutError:
                try: os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                await self.process.wait()
        if self.reader:
            self.reader.cancel()
            await asyncio.gather(self.reader, return_exceptions=True)
        self.raw.clear()
