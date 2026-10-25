"""Buscador local de Compras Ágiles. Python 3.12+, sin dependencias externas."""
import argparse
import html
import csv
import io
import ipaddress
import json
import os
import re
import socket
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo
from sync import Store, Synchronizer, connection_status, opportunities, timestamp

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


class Handler(BaseHTTPRequestHandler):
    store = None
    worker = None

    def monitor_page(self):
        state = connection_status(self.store, self.worker)
        meta = state['sincronizacion']
        data = opportunities(self.store, TERMS, normalize)
        def escape(value):
            return html.escape(str(value)) if value is not None else 'No informado'
        def local_time(value):
            parsed = timestamp(value)
            return escape(parsed.astimezone(ZoneInfo('America/Santiago')).strftime('%d/%m/%Y %H:%M:%S %Z')) if parsed else 'Ninguna registrada'
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
        purchases = ''
        for result in data['resultados']:
            cells = ''.join('<td>' + escape(result.get(k)) + '</td>' for k in ('id', 'organismo', 'cantidad', 'presupuesto', 'fecha_cierre'))
            cells += '<td><a href="' + escape(result['enlace']) + '">Detalle API (requiere ticket)</a></td>'
            cells += '<td>' + escape(json.dumps(result['items'], ensure_ascii=False)) + '</td>'
            purchases += '<tr>' + cells + '</tr>'
        document = '''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="refresh" content="30"><title>Buscador de Pendones · Vista compatible</title><link rel="stylesheet" href="./style.css"></head><body><main><h1>Buscador de Pendones</h1><p>Vista compatible con Internet Explorer y navegadores sin JavaScript. Esta página se actualiza cada 30 segundos; el servidor consulta ChileCompra por separado.</p><p><a href="./monitor">Actualizar ahora</a> · <a href="./">Vista moderna</a></p><h2>Conexión y sincronización</h2><table><tbody>'''
        document += rows + '</tbody></table><h2>Resultados disponibles</h2><p>'
        document += str(len(data['resultados'])) + ' coincidencias reales en la caché consultada. Durante la carga los resultados son parciales; cero coincidencias no acredita ausencia de oportunidades.</p><p>' + escape(data['cobertura']) + '</p>'
        document += '<p>Compras sin ítems: ' + str(data['sin_items']) + '. Fechas ambiguas omitidas: ' + str(data['fecha_no_interpretable']) + '.</p>'
        document += '<div class="table-wrap"><table><thead><tr><th>ID</th><th>Organismo</th><th>Cantidad</th><th>Presupuesto</th><th>Cierre</th><th>Enlace</th><th>Ítems de la fuente</th></tr></thead><tbody>' + purchases + '</tbody></table></div></main></body></html>'
        return document.encode()
    def send(self, status, body, content_type='application/json; charset=utf-8'):
        data = json.dumps(body, ensure_ascii=False).encode() if isinstance(body, dict) else body
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        routes = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/legacy.js': ('legacy.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
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
        body = (ROOT / 'static' / name).read_bytes()
        if path == '/' and self.store:
            meta = self.store.metadata()
            summary = ('Servidor activo. Ticket: ' + ('configurado' if os.environ.get('CHILECOMPRA_TICKET') else 'ausente')
                       + '. Estado: ' + meta.get('estado', 'iniciando')
                       + '. Última sincronización completada: ' + meta.get('ultima_sincronizacion', 'ninguna')
                       + '. ' + meta.get('error', ''))
            body = body.replace(b'<!--SERVER_STATUS-->', html.escape(summary).encode())
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
    args = parser.parse_args()
    Handler.store = Store(Path(args.data_dir) / 'compras.sqlite3')
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    Handler.worker = Synchronizer(Handler.store).start()
    print(f'Buscador de Pendones escuchando en {args.host}:{args.port}', flush=True)
    server.serve_forever()
