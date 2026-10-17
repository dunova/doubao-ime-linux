import json
import os
from pathlib import Path
import socket
import subprocess
import time

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'bridge'))
from runtime import ROOT, STATE
path=STATE/'keyboard-test.sock'
rows=[]
def call(command):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
        s.settimeout(3);s.connect(str(path));s.sendall((command+'\n').encode())
        data=bytearray()
        while b'\n' not in data:
            chunk=s.recv(65536)
            if not chunk: raise RuntimeError('Broker disconnected')
            data.extend(chunk)
    return json.loads(data)
def check(name,ok,**details):
    rows.append({'test':name,'pass':bool(ok),**details});print(('PASS ' if ok else 'FAIL ')+name,flush=True)
def type_text(text):
    for c in text:
        result=call('K '+str(ord(c.upper()))+' 0')
        call('K '+str(ord(c.upper()))+' 1')
    return result
def wait_ready(path, broker, timeout=45):
    """Wait for a live listener, including when a previous run left a socket."""
    deadline=time.monotonic()+timeout
    while True:
        code=broker.poll()
        if code is not None:
            raise RuntimeError(f'Keyboard broker exited during startup (status {code}); see work/keyboard-broker-test.log')
        remaining=deadline-time.monotonic()
        if remaining<=0:
            raise TimeoutError(f'Keyboard broker did not listen on {path} within {timeout:g}s; see work/keyboard-broker-test.log')
        try:
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as probe:
                probe.settimeout(min(.2,remaining));probe.connect(str(path))
            return
        except (FileNotFoundError,ConnectionRefusedError,socket.timeout):
            time.sleep(min(.1,max(0,deadline-time.monotonic())))


def main():
    env=dict(os.environ,DOUBAO_KEYBOARD_SOCKET=str(path))
    log=(STATE/'keyboard-broker-test.log').open('w')
    broker=subprocess.Popen(['/usr/bin/python3',str(ROOT/'bridge/keyboard_broker.py')],env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        wait_ready(path,broker)
        call('F')
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as invalid:
            invalid.settimeout(3);invalid.connect(str(path));invalid.sendall(b'\xff\n')
            check('malformed client disconnected',invalid.recv(1024)==b'')
        check('broker survives malformed client',call('F')['result']==0)
        state=type_text('nihao')
        check('official preedit',state['preedit']=="ni'hao",preedit=state['preedit'])
        words=state['candidates'].splitlines()
        check('official candidates include 你好',words[0]=='你好',candidates=words[:12])
        state=call('S 0');check('select first candidate',state['commit']=='你好',state=state)
        for index in (1,10):
            call('F');state=type_text('nihao');words=state['candidates'].splitlines()
            expected=words[index];state=call('S '+str(index))
            if index==10:
                check('partial candidate keeps remaining pinyin',state['preedit'].startswith(expected) and state['preedit'].endswith('hao') and not state['commit'],expected=expected,state=state)
                state=call('S 0');check('complete partial conversion',state['commit']==expected+'好',state=state)
            else:
                check('select candidate '+str(index),state['commit']==expected,expected=expected,state=state)
        call('F');type_text('nihao');state=call('K 8 0')
        check('Backspace updates composition',state['preedit']=="ni'ha",state=state)
        state=call('K 27 0');check('Escape clears composition',not state['preedit'] and not state['commit'])
        type_text('ni');call('R');state=call('F')
        check('new focus drops previous composition',not state['preedit'] and not state['commit'])
    finally:
        broker.terminate()
        try:broker.wait(8)
        except subprocess.TimeoutExpired:broker.kill();broker.wait()
        log.close()
        (STATE/'keyboard-rpc.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    return 0 if rows and all(r['pass'] for r in rows) else 1


if __name__=='__main__':
    raise SystemExit(main())
