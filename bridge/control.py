#!/usr/bin/env python3
import argparse
from gi.repository import Gio, GLib

parser = argparse.ArgumentParser()
parser.add_argument('command', choices=['start', 'stop', 'toggle', 'cancel', 'status', 'organize-on', 'organize-off'], nargs='?', default='status')
args = parser.parse_args()
if args.command in ('organize-on', 'organize-off'):
    from organize import runtime_ready, set_enabled
    import json
    active = args.command == 'organize-on'
    if active and not runtime_ready():
        parser.exit(1, '请先运行 python3 scripts/prepare_organize.py\n')
    set_enabled(active)
    print(json.dumps({'smart_text_organization':active}))
    parser.exit(0)
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
try:
    result = bus.call_sync('org.doubaoime.Voice1', '/org/doubaoime/Voice', 'org.doubaoime.Voice1',
        'Status' if args.command == 'status' else 'Command',
        None if args.command == 'status' else GLib.Variant('(s)', (args.command,)), None,
        Gio.DBusCallFlags.NONE, 5000, None)
    print(result.unpack()[0])
except GLib.Error as error:
    parser.exit(1, str(error)+'\n')
