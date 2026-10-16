#!/usr/bin/env python3
"""Prepare a separate, pinned official text-organization runtime."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from runtime import ROOT, STATE, VERSION, KEYBOARD_PREFIX, ORGANIZE_PREFIX, executable, wine

PINNED = {
    'ImeService.exe': '38742f838d58b6e5b87a08564c6917da1d75ac6b81ec6ee3388ffaaac7c9f3ad',
    'applogrs.dll': '157744a0efe5371f9492b1920f1f8dc6e8bd7981e11b7f3f9bffa028711f7756',
    'sscronet.dll': '837bbff44bc1a3dd364db7534027d243c122f30ec8d7e95f9aaafa9454a6506f',
}

def exports(path):
    output = subprocess.check_output(['objdump', '-p', str(path)], text=True)
    section = output.split('[Ordinal/Name Pointer]')[1].split('The Function Table')[0]
    names = re.findall(r'\b[0-9a-f]{4}\s+(\S+)\s*$', section, re.M)
    if not names or any(not re.fullmatch(r'[A-Za-z_?][A-Za-z_0-9?@$]*', n) for n in names):
        raise RuntimeError('Unexpected DLL exports')
    return names

def prepare():
    if VERSION != '0.9.2.7': raise RuntimeError('Organizer is pinned to 0.9.2.7')
    if os.environ.get('DOUBAO_MANAGED_PREFIX') != str(ORGANIZE_PREFIX):
        raise RuntimeError('Use the private organize prefix wrapper')
    if (ORGANIZE_PREFIX / 'system.reg').exists() and not (ORGANIZE_PREFIX / '.doubao-organize-managed').exists():
        raise RuntimeError('Refusing an unowned prefix')
    source = KEYBOARD_PREFIX / 'drive_c/DoubaoIme/versions' / ('v'+VERSION)
    for name, expected in PINNED.items():
        if hashlib.sha256((source/name).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Unsupported official component: '+name)
    ORGANIZE_PREFIX.mkdir(parents=True, exist_ok=True)
    (ORGANIZE_PREFIX/'.doubao-organize-managed').touch(mode=0o600)
    with (STATE/'prepare-organize.log').open('w') as log:
        subprocess.run([wine(), 'wineboot', '-u'], stdout=log, stderr=log, check=True, timeout=120)
        target = ORGANIZE_PREFIX / 'drive_c/DoubaoIme/versions' / ('v'+VERSION)
        if not target.exists(): shutil.copytree(source, target)
        for dll, stem, custom in [
            ('applogrs', 'organize_identity', {'AppLog_init'}),
            ('sscronet', 'organize_transport', {'Cronet_UrlRequest_InitWithParams', 'Cronet_UrlRequestCallback_CreateWith'}),
        ]:
            original = target/(dll+'_original.dll')
            if not original.exists(): shutil.copy2(source/(dll+'.dll'), original)
            if hashlib.sha256(original.read_bytes()).hexdigest() != PINNED[dll+'.dll']:
                raise RuntimeError('Original DLL checksum mismatch')
            definition = ROOT/'build'/(stem+'.def')
            definition.write_text('LIBRARY '+dll+'\nEXPORTS\n'+''.join(
                n+'='+dll+'_original.'+n+'\n' for n in exports(original) if n not in custom))
            subprocess.run([executable('mingw_cc', 'x86_64-w64-mingw32-gcc'),
                '-shared', '-O0', '-nostdlib', '-fno-builtin', '-fno-stack-protector',
                '-Wl,--entry=DllMainCRTStartup', str(ROOT/'bridge'/(stem+'.c')), str(definition),
                '-lkernel32', '-luser32', '-o', str(target/(dll+'.dll'))],
                check=True, stdout=log, stderr=log)
        # A separate command-line runtime needs no desktop settings or accounts.
        # Disable native update and voice hotkeys in its default profile.
        from runtime import config_path
        import json
        config = config_path(ORGANIZE_PREFIX)
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps({'schemaVersion':7,'keyboard':{},
            'update':{'automaticUpdateEnabled':False},
            'voice':{'enableGlobalVoiceShortcut':False,'enableVoiceShortcut':False}}))
        manifest = {name:hashlib.sha256((target/name).read_bytes()).hexdigest()
                    for name in ['ImeService.exe','applogrs.dll','sscronet.dll',
                                 'applogrs_original.dll','sscronet_original.dll']}
        (ORGANIZE_PREFIX/'.organize-checksums.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('Prepared isolated official organizer '+VERSION)

if __name__ == '__main__':
    os.umask(0o077)
    parser=argparse.ArgumentParser();parser.add_argument('--inside',action='store_true');args=parser.parse_args()
    if args.inside:prepare()
    else:subprocess.run([sys.executable,str(ROOT/'scripts/headless.py'),'--prefix','organize','--',
        sys.executable,str(Path(__file__).resolve()),'--inside'],check=True)
