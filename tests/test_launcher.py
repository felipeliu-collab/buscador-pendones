import io
import unittest
from unittest.mock import patch

from abrir_buscador import main, running


class LauncherTests(unittest.TestCase):
    def test_existing_server_opens_browser_without_new_process(self):
        with patch('abrir_buscador.running', return_value=True), patch('abrir_buscador.webbrowser.open') as browser, patch('abrir_buscador.subprocess.call') as process:
            self.assertEqual(main(), 0)
            browser.assert_called_once_with('http://127.0.0.1:8000/monitor')
            process.assert_not_called()

    def test_absent_server_uses_gui_without_secret_arguments(self):
        with patch('abrir_buscador.running', return_value=False), patch('abrir_buscador.subprocess.call', return_value=0) as process, patch('builtins.print'):
            self.assertEqual(main(), 0)
            command = process.call_args.args[0]
            self.assertEqual(command[-2:], ['--ticket-window', '--open-browser'])
            self.assertEqual(len(command), 4)

    def test_health_rejects_unrelated_or_unavailable_server(self):
        with patch('abrir_buscador.urllib.request.urlopen') as request:
            request.return_value.__enter__.return_value = io.BytesIO(b'{"estado":"ok","modo":"otro"}')
            self.assertFalse(running())
            request.side_effect = ConnectionRefusedError()
            self.assertFalse(running())


if __name__ == '__main__':
    unittest.main()
