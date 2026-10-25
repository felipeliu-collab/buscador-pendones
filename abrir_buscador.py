"""Lanzador para acceso directo de Windows; no almacena ni imprime el ticket."""
import json
import subprocess
import sys
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


def running():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3) as response:
            health = json.load(response)
        return isinstance(health, dict) and health.get('estado') == 'ok' and health.get('modo') == 'api_oficial_v2'
    except (OSError, ValueError, urllib.error.URLError):
        return False


def main():
    if sys.version_info < (3, 12):
        print('Se requiere Python 3.12 o superior.')
        return 1
    if running():
        webbrowser.open('http://127.0.0.1:8000/monitor')
        return 0
    root = Path(__file__).resolve().parent
    print('Se abrira la ventana para pegar el ticket de ChileCompra.', flush=True)
    print('Deja esta ventana abierta mientras uses el buscador. Para detenerlo, cierrala.', flush=True)
    try:
        return subprocess.call([sys.executable, str(root / 'app.py'), '--ticket-window', '--open-browser'], cwd=root)
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
