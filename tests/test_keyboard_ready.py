"""Regression coverage for issue #3: stale sockets are not readiness."""
from pathlib import Path
import socket
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from integration_keyboard import wait_ready


class KeyboardReadiness(unittest.TestCase):
    def test_missing_or_stale_socket_waits_for_listener(self):
        for stale in (False, True):
            with self.subTest(stale=stale), tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'broker.sock'
                if stale:
                    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as old:
                        old.bind(str(path))
                errors=[]
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
                    def start():
                        try:
                            path.unlink(missing_ok=True)
                            listener.bind(str(path));listener.listen(1)
                        except Exception as exc:errors.append(exc)
                    timer=threading.Timer(.05,start);timer.start()
                    try:
                        wait_ready(path,SimpleNamespace(poll=lambda:None),timeout=2)
                        listener.settimeout(1)
                        connection,_=listener.accept();connection.close()
                    finally:timer.join()
                self.assertEqual(errors,[])

    def test_stale_socket_times_out_without_listener(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'broker.sock'
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as old:
                old.bind(str(path))
            with self.assertRaisesRegex(TimeoutError,'did not listen.*broker.sock'):
                wait_ready(path,SimpleNamespace(poll=lambda:None),timeout=.03)
            self.assertTrue(path.exists())  # Probing must not delete another owner's path.

    def test_missing_socket_times_out(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(TimeoutError,'did not listen'):
                wait_ready(Path(directory)/'missing.sock',SimpleNamespace(poll=lambda:None),timeout=.03)

    def test_early_exit_reports_status_and_log(self):
        with self.assertRaisesRegex(RuntimeError,r'status 7.*keyboard-broker-test.log'):
            wait_ready(Path('/unused.sock'),SimpleNamespace(poll=lambda:7))

    def test_permission_errors_are_not_retried_as_startup(self):
        with patch('integration_keyboard.socket.socket',side_effect=PermissionError('denied')):
            with self.assertRaises(PermissionError):
                wait_ready(Path('/unused.sock'),SimpleNamespace(poll=lambda:None))


if __name__=='__main__':unittest.main()
