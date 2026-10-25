"""Buscador local de Compras Ágiles. Python 3.12+, sin dependencias externas."""
import argparse
import html
import csv
import io
import ipaddress
import json
import os
import getpass
import re
import socket
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import threading
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sync import Store, Synchronizer, connection_status, opportunities, timestamp
from excel import export_xlsx
from avisos import AlertCenter, desktop_alerts

ROOT = Path(__file__).parent
MAX_BYTES = 10 * 1024 * 1024
HOSTS = {"www.mercadopublico.cl", "api.mercadopublico.cl", "datos-abiertos.chilecompra.cl", "www.chilecompra.cl"}
TERMS = re.compile(r"\b(?:pendon(?:es)?|rollers?|mini[\s-]*pendon(?:es)?)\b")


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value).lower()) if not unicodedata.combining(c))


def official_url(value):
    p = urllib.parse.urlsplit(value)
    if p.scheme != 'https' or p.hostname not in HOSTS or p.username or p.password or p.port not in (None, 443):
        raise ValueError('Usa una URL HTTPS de uno de los dominios oficiales admitidos.')
    return value


def text_values(value):
    if isinstance(value, dict):
        return ' '.join(text_values(v) for v in value.values())
    if isinstance(value, list):
        return ' '.join(text_values(v) for v in value)
    return '' if value is None else str(value)


def get(record, *names):
    fields = {normalize(k).replace(' ', '_'): v for k, v in record.items()}
    for name in names:
        value = fields.get(name)
        if value is not None and value != '':
            return value
    return None


def display(value):
    return text_values(value) if value is not None else None


def parse_records(content):
    content = content.lstrip('\ufeff').strip()
    if not content:
        raise ValueError('El archivo está vacío.')
    if content[0] in '[{':
        records = json.loads(content)
        if isinstance(records, dict):
            records = records.get('compras', records.get('records'))
        if not isinstance(records, list):
            raise ValueError('JSON: se espera una lista de compras o un objeto con "compras" o "records".')
    else:
        try:
            dialect = csv.Sniffer().sniff(content[:8192], delimiters=',;\t')
        except csv.Error:
            dialect = csv.excel
        records = list(csv.DictReader(io.StringIO(content), dialect=dialect))
    if any(not isinstance(r, dict) for r in records):
        raise ValueError('Cada compra debe ser un objeto con campos.')
    return records


def search(content, source):
    official_url(source)
    records = parse_records(content)
    results, excluded, matched_without_id = [], 0, 0
    for record in records:
        kind = normalize(get(record, 'tipo', 'modalidad', 'tipo_compra') or '').strip()
        if kind not in ('compra agil', 'compras agiles'):
            excluded += 1
            continue
        if not TERMS.search(normalize(text_values(record))):
            continue
        code = display(get(record, 'id', 'codigo', 'codigo_compra', 'codigoexterno'))
        if not code:
            matched_without_id += 1
            continue
        link = display(get(record, 'enlace', 'url', 'link'))
        try:
            if link:
                official_url(link)
        except ValueError:
            link = None
        items = get(record, 'items', 'productos')
        # Never infer budget, quantities, deadlines, or item completeness.
        results.append({
            'id': code,
            'organismo': display(get(record, 'organismo', 'comprador', 'institucion')),
            'cantidad': display(get(record, 'cantidad')),
            'presupuesto': display(get(record, 'presupuesto', 'monto_estimado')),
            'fecha_cierre': display(get(record, 'fecha_cierre', 'fechacierre')),
            'enlace': link,
            'items_disponibles': bool(items),
            'coincidencias': sorted(set(m.group() for m in TERMS.finditer(normalize(text_values(record))))),
            'items': items,
        })
    return {
        'resultados': results,
        'fuente': source,
        'consultado_en': datetime.now(timezone.utc).isoformat(),
        'registros_leidos': len(records),
        'excluidos_por_modalidad': excluded,
        'coincidencias_sin_id': matched_without_id,
        'cobertura': 'Solo los registros y campos importados. No se acredita cobertura nacional, vigencia ni completitud de ítems. La URL de procedencia de un archivo subido es declarada por el usuario; no se verifica su autenticidad.',
    }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('La fuente redirige. Ingresa directamente la URL oficial final; no se siguen redirecciones.')


def download(url):
    official_url(url)
    host = urllib.parse.urlsplit(url).hostname
    for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise ValueError('La dirección de la fuente no es pública.')
    request = urllib.request.Request(url, headers={'Accept': 'application/json,text/csv', 'User-Agent': 'BuscadorPendones/1.0'})
    # Standard TLS verification and configured platform HTTPS proxy are retained.
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=25) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('La fuente excede el límite de 10 MiB. Usa una exportación más acotada.')
    return data.decode('utf-8-sig')


def ticket_window():
    """Native masked dialog; clipboard and credential never go to stdout or disk."""
    import tkinter as tk
    from tkinter import messagebox
    try:
        root = tk.Tk()
    except tk.TclError:
        raise RuntimeError('No hay una pantalla gráfica disponible.') from None
    root.title('Buscador de Pendones · Ticket de ChileCompra')
    root.geometry('560x240')
    root.resizable(False, False)
    result = []
    tk.Label(root, text='Copia el ticket del correo y pulsa «Pegar ticket».', font=('Arial', 12)).pack(pady=(20, 8))
    entry = tk.Entry(root, show='*', width=58)
    entry.pack(padx=20, pady=8)
    status = tk.Label(root, text='El ticket se oculta y no se guarda en archivos.')
    status.pack(pady=5)

    def paste():
        try:
            value = root.clipboard_get().strip()
        except tk.TclError:
            messagebox.showerror('Portapapeles vacío', 'Primero copia el ticket desde el correo.', parent=root)
            return
        entry.delete(0, tk.END)
        entry.insert(0, value)
        status.config(text='Ticket pegado (oculto). Pulsa «Iniciar buscador».')

    def submit(event=None):
        value = entry.get().strip()
        if not value:
            messagebox.showerror('Falta el ticket', 'Pega o escribe el ticket antes de continuar.', parent=root)
            return
        result.append(value)
        root.destroy()

    buttons = tk.Frame(root)
    buttons.pack(pady=15)
    tk.Button(buttons, text='Pegar ticket', command=paste, width=18).pack(side=tk.LEFT, padx=8)
    tk.Button(buttons, text='Iniciar buscador', command=submit, width=18).pack(side=tk.LEFT, padx=8)
    root.bind('<Return>', submit)
    entry.focus_set()
    root.mainloop()
    return result[0] if result else None


class Handler(BaseHTTPRequestHandler):
    store = None
    worker = None
    alerts = None
    frame_origins = ["'self'"]

    @staticmethod
    def local_time(value):
        parsed = timestamp(value)
        if parsed is None:
            return 'Ninguna registrada'
        try:
            zone = ZoneInfo('America/Santiago')
        except ZoneInfoNotFoundError:
            # Windows may have no IANA database. Keep the page usable without
            # guessing Chile's offset or daylight-saving rules.
            return parsed.astimezone(timezone.utc).strftime('%d/%m/%Y %H:%M:%S UTC') + ' (zona de Chile no disponible)'
        return parsed.astimezone(zone).strftime('%d/%m/%Y %H:%M:%S %Z')

    @staticmethod
    def result_rows(results):
        rows = ''
        for result in results:
            esc = lambda value: html.escape(str(value)) if value is not None else 'No informado'
            cells = ''.join('<td>' + esc(result.get(k)) + '</td>' for k in ('id', 'organismo', 'cantidad', 'presupuesto', 'fecha_cierre'))
            cells += '<td><a href="' + esc(result['enlace']) + '">Detalle API (requiere ticket)</a></td>'
            location = ', '.join(result.get('donde_coincide') or []) or 'Ver texto e ítems'
            cells += '<td><strong>Encontrado en: ' + esc(location) + '</strong><br><strong>Título:</strong> ' + esc(result.get('titulo')) + '<br><strong>Descripción:</strong> ' + esc(result.get('descripcion')) + '<br><strong>Ítems:</strong> ' + esc(json.dumps(result.get('items_coincidentes') or result['items'], ensure_ascii=False)) + '</td>'
            rows += '<tr>' + cells + '</tr>'
        return rows

    def home_page(self):
        document = (ROOT / 'static' / 'index.html').read_text()
        if not self.store:
            return document.encode()
        state = connection_status(self.store, self.worker)
        meta = state['sincronizacion']
        data = opportunities(self.store, TERMS, normalize)
        values = {
            'server-state': 'Activo · respuesta generada por el servidor',
            'ticket-state': 'Configurado en el proceso (valor oculto)' if state['ticket_configurado'] else 'Ausente en el proceso',
            'connection-state': meta.get('conexion', 'Todavía sin respuesta de la API') + (' · HTTP ' + meta['http_status'] if meta.get('http_status') else ''),
            'last-connection': self.local_time(meta.get('ultima_conexion_exitosa')),
            'last-sync': self.local_time(meta.get('ultima_sincronizacion')),
            'sync-progress': f"{meta.get('estado', 'iniciando')} · trabajador {'activo' if state['trabajador_activo'] else 'detenido'} · fase {meta.get('fase', 'sin iniciar')} · páginas {meta.get('paginas_leidas', '0')}/{meta.get('paginas_totales') or '?'} · detalles guardados {state['detalles_guardados']} · pendientes {state['detalles_pendientes']}",
            'next-sync': 'Después de terminar este ciclo' if meta.get('estado') == 'sincronizando' else self.local_time(meta.get('reintentar_desde') or meta.get('proximo_intento')),
            'connection-error': meta.get('error_conexion') or meta.get('error') or 'Ninguno registrado',
            'status': f"{len(data['resultados'])} coincidencias en los datos reales recibidos de ChileCompra. {data['coincidencias_en_items']} tienen coincidencias en ítems; {data['coincidencias_items_sin_titulo']} de ellas no mencionan el término en el título. {data['pendientes']} detalles pendientes. Los resultados son parciales mientras la sincronización no esté completa. Fechas ambiguas omitidas: {data['fecha_no_interpretable']}.",
            'coverage': data['cobertura'],
        }
        for element, value in values.items():
            pattern = r'(<(?:dd|p) id="' + element + r'"[^>]*>).*?(</(?:dd|p)>)'
            document = re.sub(pattern, lambda m: m[1] + html.escape(str(value)) + m[2], document, flags=re.S)
        summary = ('Servidor activo. Ticket: ' + ('configurado' if state['ticket_configurado'] else 'ausente')
                   + '. Estado: ' + meta.get('estado', 'iniciando')
                   + '. Última sincronización completada: ' + self.local_time(meta.get('ultima_sincronizacion'))
                   + '. ' + meta.get('error', ''))
        document = document.replace('<!--SERVER_STATUS-->', html.escape(summary))
        document = document.replace('<tbody></tbody>', '<tbody>' + self.result_rows(data['resultados']) + '</tbody>')
        if data['resultados']:
            document = document.replace('<table hidden id="results">', '<table id="results">')
        return document.encode()

    def alerts_page(self):
        center = self.alerts
        events = center.history()
        meta = self.store.metadata()
        esc = lambda value: html.escape(str(value))
        body = '''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="refresh" content="30"><title>Avisos · Buscador de Pendones</title><link rel="stylesheet" href="./style.css"></head><body><main><h1>Avisos de compras</h1><p><a href="./monitor">Ver compras</a> · <a href="./avisos">Actualizar avisos</a></p>'''
        body += '<p>Avisos: ' + ('activados' if center.enabled() else 'silenciados') + '. Ventana de escritorio: ' + ('activa' if center.desktop_active else 'no activa en este proceso; aquí puedes consultar el historial') + '.</p>'
        body += '<p>Se avisa de coincidencias recién detectadas, incluso al descargar los ítems de una compra antigua. No significa necesariamente una publicación nueva. La primera revisión establece un punto de partida sin generar avisos por lo ya conocido. No se repiten avisos para el mismo ID.</p>'
        body += '<p>El programa debe estar abierto y ChileCompra debe permitir actualizar. Si hay cuota agotada o detalles pendientes, la detección será parcial o tardía. Revisa la vigencia antes de ofertar.</p>'
        body += '<p>Última revisión de la caché para avisos: ' + esc(self.local_time(meta.get('avisos_ultima_revision'))) + '. Estado de sincronización: ' + esc(meta.get('estado', 'iniciando')) + '. ' + esc(meta.get('error') or meta.get('avisos_error') or '') + '</p>'
        if not events:
            body += '<p>Todavía no hay nuevas coincidencias registradas después del punto de partida. Esto no significa que no existan oportunidades.</p>'
        else:
            body += '<p>' + str(len(events)) + ' avisos guardados. Se muestran los 100 más recientes.</p><div class="table-wrap"><table><thead><tr><th>Detectado</th><th>ID</th><th>Título</th><th>Encontrado en</th></tr></thead><tbody>'
            for event in events[:100]:
                body += '<tr><td>' + esc(self.local_time(event['detectado_en'])) + '</td><td>' + esc(event['id']) + '</td><td>' + esc(event['titulo']) + '</td><td>' + esc(', '.join(event['donde_coincide'])) + '</td></tr>'
            body += '</tbody></table></div>'
        return (body + '</main></body></html>').encode()

    def monitor_page(self):
        state = connection_status(self.store, self.worker)
        meta = state['sincronizacion']
        data = opportunities(self.store, TERMS, normalize)
        def escape(value):
            return html.escape(str(value)) if value is not None else 'No informado'
        def local_time(value):
            return escape(self.local_time(value))
        fields = {
            'Servidor': 'Activo',
            'Ticket': 'Configurado (valor oculto)' if state['ticket_configurado'] else 'Ausente en el proceso',
            'Trabajador': 'Activo' if state['trabajador_activo'] else 'Detenido',
            'Conexión API': meta.get('conexion', 'Sin comprobar') + (' · HTTP ' + meta['http_status'] if meta.get('http_status') else ''),
            'Estado': meta.get('estado', 'iniciando'),
            'Progreso': f"Fase {meta.get('fase', 'sin iniciar')}; páginas {meta.get('paginas_leidas', '0')}/{meta.get('paginas_totales') or '?'}; detalles guardados {state['detalles_guardados']}; pendientes {state['detalles_pendientes']}",
            'Error de diagnóstico': meta.get('error_conexion') or meta.get('error') or 'Ninguno registrado',
        }
        rows = ''.join('<tr><th>' + escape(k) + '</th><td>' + escape(v) + '</td></tr>' for k, v in fields.items())
        rows += '<tr><th>Última conexión exitosa</th><td>' + local_time(meta.get('ultima_conexion_exitosa')) + '</td></tr>'
        rows += '<tr><th>Última sincronización completa</th><td>' + local_time(meta.get('ultima_sincronizacion')) + '</td></tr>'
        rows += '<tr><th>Próximo intento</th><td>' + ('Después de terminar este ciclo' if meta.get('estado') == 'sincronizando' else local_time(meta.get('reintentar_desde') or meta.get('proximo_intento'))) + '</td></tr>'
        purchases = self.result_rows(data['resultados'])
        document = '''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="refresh" content="30"><title>Buscador de Pendones · Vista compatible</title><link rel="stylesheet" href="./style.css"></head><body><main><h1>Buscador de Pendones</h1><p>Se incluyen coincidencias en el título O en la descripción O en los ítems. Cada resultado indica dónde se encontró el término.</p><p>Vista compatible con Internet Explorer y navegadores sin JavaScript. Esta página se actualiza cada 30 segundos; el servidor consulta ChileCompra por separado.</p><p><a href="./monitor">Actualizar ahora</a> · <a href="./">Vista moderna</a> · <a href="./avisos">Avisos de nuevas coincidencias</a></p><h2>Conexión y sincronización</h2><table><tbody>'''
        document += rows + '</tbody></table><h2>Resultados disponibles</h2><p><a class="download-button" href="./descargar.xlsx">Descargar Excel</a></p><p>Exporta las coincidencias automáticas disponibles al descargar. Si la carga está incompleta, se indicará en la hoja Estado.</p><p>'
        document += str(len(data['resultados'])) + ' coincidencias reales en la caché consultada. Durante la carga los resultados son parciales; cero coincidencias no acredita ausencia de oportunidades.</p><p>' + escape(data['cobertura']) + '</p>'
        document += '<p><strong>Coincidencias en ítems: ' + str(data['coincidencias_en_items']) + '. Con coincidencia en ítems y sin mención en el título: ' + str(data['coincidencias_items_sin_titulo']) + '.</strong> Detalles todavía pendientes de revisar: ' + str(data['pendientes']) + '.</p>'
        document += '<p>Compras sin ítems: ' + str(data['sin_items']) + '. Fechas ambiguas omitidas: ' + str(data['fecha_no_interpretable']) + '.</p>'
        document += '<div class="table-wrap"><table><thead><tr><th>ID</th><th>Organismo</th><th>Cantidad</th><th>Presupuesto</th><th>Cierre</th><th>Enlace</th><th>Ítems de la fuente</th></tr></thead><tbody>' + purchases + '</tbody></table></div></main></body></html>'
        return document.encode()
    def send(self, status, body, content_type='application/json; charset=utf-8', download_name=None):
        try:
            self._send(status, body, content_type, download_name)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            # A browser refresh or closed tab can disconnect during headers/body.
            # This does not stop the independent ChileCompra worker.
            self.close_connection = True

    def _send(self, status, body, content_type, download_name=None):
        data = json.dumps(body, ensure_ascii=False).encode() if isinstance(body, dict) else body
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        if download_name:
            self.send_header('Content-Disposition', f'attachment; filename="{download_name}"')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors " + ' '.join(self.frame_origins))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == '/avisos':
            if self.alerts is None:
                return self.send(503, {'error': 'Centro de avisos no iniciado.'})
            return self.send(200, self.alerts_page(), 'text/html; charset=utf-8')
        routes = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/legacy.js': ('legacy.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if path == '/descargar.xlsx':
            if self.store is None:
                return self.send(503, {'error': 'Almacenamiento no iniciado.'})
            data = opportunities(self.store, TERMS, normalize)
            return self.send(200, export_xlsx(data), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'pendones.xlsx')
        if path == '/monitor':
            if self.store is None:
                return self.send(503, {'error': 'Almacenamiento no iniciado.'})
            return self.send(200, self.monitor_page(), 'text/html; charset=utf-8')
        if path == '/api/health':
            return self.send(200, {'estado': 'ok', 'modo': 'api_oficial_v2', 'cobertura_nacional_verificada': False,
                                   'ticket_configurado': bool(os.environ.get('CHILECOMPRA_TICKET'))})
        if path == '/api/estado':
            if self.store is None:
                return self.send(503, {'error': 'Almacenamiento no iniciado.'})
            return self.send(200, connection_status(self.store, self.worker))
        if path == '/api/oportunidades':
            if self.store is None:
                return self.send(503, {'error': 'Almacenamiento de sincronización no iniciado.'})
            return self.send(200, opportunities(self.store, TERMS, normalize))
        if path not in routes:
            return self.send(404, {'error': 'No encontrado'})
        name, mime = routes[path]
        body = self.home_page() if path == '/' else (ROOT / 'static' / name).read_bytes()
        self.send(200, body, mime)

    def do_POST(self):
        if self.path != '/api/buscar':
            return self.send(404, {'error': 'No encontrado'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length <= 0 or length > MAX_BYTES:
                return self.send(413, {'error': 'Solicitud vacía o superior a 10 MiB.'})
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('La solicitud debe ser un objeto JSON.')
            source = payload.get('fuente', '')
            if not isinstance(source, str):
                raise ValueError('La fuente debe ser una URL.')
            official_url(source)
            content = payload.get('contenido')
            if content is None:
                content = download(source)
            if not isinstance(content, str):
                raise ValueError('El contenido debe ser texto CSV o JSON.')
            self.send(200, search(content, source))
        except (ValueError, TypeError, UnicodeError, csv.Error) as exc:
            self.send(400, {'error': str(exc)})
        except (urllib.error.URLError, TimeoutError, OSError):
            self.send(502, {'error': 'No fue posible consultar la fuente oficial. Revisa acceso de red, disponibilidad y permisos. No se generaron resultados.'})

    def log_message(self, fmt, *args):
        # Do not log user payloads or source URLs containing possible credentials.
        pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--data-dir', default=str(ROOT / 'data'))
    parser.add_argument('--ask-ticket', action='store_true', help='Pedir el ticket con entrada oculta para ejecución local; no se guarda en disco.')
    parser.add_argument('--ticket-window', action='store_true', help='Abrir una ventana con entrada oculta y botón Pegar ticket.')
    parser.add_argument('--open-browser', action='store_true', help='Abrir la vista compatible en el navegador de este equipo.')
    parser.add_argument('--frame-origin', action='append', default=[], help='Origen HTTPS exacto autorizado para incrustar la aplicación; se puede repetir.')
    notifications = parser.add_mutually_exclusive_group()
    notifications.add_argument('--desktop-alerts', action='store_true', help='Abrir el panel de avisos en pantalla (automático en Windows).')
    notifications.add_argument('--no-desktop-alerts', action='store_true', help='Ejecutar sin ventana de avisos; el historial sigue disponible.')
    args = parser.parse_args()
    if args.ask_ticket and args.ticket_window:
        parser.error('Elige --ask-ticket o --ticket-window, no ambos.')
    for origin in args.frame_origin:
        parsed = urllib.parse.urlsplit(origin)
        if parsed.scheme != 'https' or not parsed.hostname or not re.fullmatch(r'[A-Za-z0-9.-]+(?::[0-9]+)?', parsed.netloc) or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or '*' in origin or any(c.isspace() for c in origin):
            parser.error('--frame-origin debe ser un origen HTTPS exacto, sin ruta, credenciales ni comodines.')
    Handler.frame_origins = ["'self'", *args.frame_origin]
    if args.ticket_window:
        try:
            value = ticket_window()
        except (ImportError, RuntimeError):
            parser.error('No está disponible la interfaz gráfica. Instala Python con Tcl/Tk o usa --ask-ticket.')
        if value is None:
            parser.exit(0, 'Inicio cancelado; no se inició el buscador.\n')
        os.environ['CHILECOMPRA_TICKET'] = value
    if args.ask_ticket:
        if not sys.stdin.isatty():
            parser.error('--ask-ticket requiere una terminal interactiva para evitar mostrar la credencial.')
        os.environ['CHILECOMPRA_TICKET'] = getpass.getpass('Ticket ChileCompra (entrada oculta; no se guarda): ').strip()
    Handler.store = Store(Path(args.data_dir) / 'compras.sqlite3')
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    Handler.alerts = AlertCenter(Handler.store)
    loader = lambda: opportunities(Handler.store, TERMS, normalize)
    Handler.alerts.observe(loader()['resultados'])
    Handler.alerts.start(loader)
    Handler.worker = Synchronizer(Handler.store).start()
    print(f'Buscador de Pendones escuchando en {args.host}:{args.port}', flush=True)
    if args.open_browser:
        threading.Timer(0.5, webbrowser.open, args=(f'http://127.0.0.1:{args.port}/monitor',)).start()
    if not args.no_desktop_alerts and (sys.platform == 'win32' or args.desktop_alerts):
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            desktop_alerts(Handler.alerts, args.port)
        except (ImportError, RuntimeError):
            print('No se pudo abrir el panel gráfico de avisos. El buscador sigue activo; consulta el historial en la página de avisos.', flush=True)
            server_thread.join()
        finally:
            server.shutdown()
            server.server_close()
    else:
        server.serve_forever()
