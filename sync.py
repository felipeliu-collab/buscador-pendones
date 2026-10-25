"""Cliente de la API Compra Ágil v2, según guía oficial de mayo de 2026.

https://www.chilecompra.cl/wp-content/uploads/2026/05/Documentacion_API_Compra_Agil-2-1.pdf
"""
import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = 'https://api2.mercadopublico.cl/v2/compra-agil'
INTERVAL = 3600
MAX_DAILY = 9000  # Conservative local budget, not a claim about the assigned quota.


def now():
    return datetime.now(timezone.utc)


def iso(value):
    return value.isoformat(timespec='seconds')


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result if result.tzinfo else None
    except ValueError:
        return None


class SourceError(Exception):
    pass


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise SourceError('La API redirigió la solicitud. No se reenvía el ticket a otra URL.')


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS compras (
                    codigo TEXT PRIMARY KEY, listado TEXT NOT NULL,
                    detalle TEXT, pendiente INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS meta (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS consumo (dia TEXT PRIMARY KEY, cantidad INTEGER NOT NULL);
            ''')

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def metadata(self):
        with self.connect() as db:
            return dict(db.execute('SELECT clave, valor FROM meta'))

    def set_meta(self, **values):
        with self.connect() as db:
            db.executemany('INSERT OR REPLACE INTO meta VALUES (?, ?)', [(k, str(v)) for k, v in values.items()])

    def reserve_request(self):
        # UTC buckets deliberately use a lower local cap; remote quota remains authoritative.
        day = now().date().isoformat()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT cantidad FROM consumo WHERE dia=?', (day,)).fetchone()
            count = row[0] if row else 0
            if count >= MAX_DAILY:
                raise SourceError('Presupuesto local diario agotado (9.000 solicitudes). Sincronización pendiente.')
            db.execute('INSERT OR REPLACE INTO consumo VALUES (?, ?)', (day, count + 1))

    def ingest(self, rows, cursor, bootstrap=False):
        with self.connect() as db:
            for row in rows:
                code = row['codigo']
                old = db.execute('SELECT listado FROM compras WHERE codigo=?', (code,)).fetchone()
                serialized = json.dumps(row, ensure_ascii=False, sort_keys=True)
                changed = not old or old[0] != serialized
                if changed:
                    db.execute('''INSERT INTO compras(codigo, listado, pendiente) VALUES (?, ?, 1)
                        ON CONFLICT(codigo) DO UPDATE SET listado=excluded.listado, pendiente=1''', (code, serialized))
            db.execute('INSERT OR REPLACE INTO meta VALUES (?, ?)', ('cursor', cursor))
            if bootstrap:
                db.execute('INSERT OR REPLACE INTO meta VALUES (?, ?)', ('inicio_completado', 'si'))

    def pending(self):
        with self.connect() as db:
            return [(code, json.loads(data)) for code, data in db.execute('SELECT codigo, listado FROM compras WHERE pendiente=1 ORDER BY codigo')]

    def save_detail(self, code, detail):
        with self.connect() as db:
            db.execute('UPDATE compras SET detalle=?, pendiente=0 WHERE codigo=?', (json.dumps(detail, ensure_ascii=False), code))

    def snapshot(self):
        with self.connect() as db:
            return [(json.loads(row), json.loads(detail) if detail else None, pending)
                    for row, detail, pending in db.execute('SELECT listado, detalle, pendiente FROM compras ORDER BY codigo')]


def compact(data):
    """Retain demand data only; supplier quotations and personal data are not cached."""
    keys = ('codigo', 'nombre', 'descripcion', 'estado', 'fechas', 'institucion', 'montos', 'presupuesto', 'productos_solicitados', 'links')
    return {key: data[key] for key in keys if key in data}


class API:
    def __init__(self, store):
        self.store = store

    def get(self, code=None, params=None):
        ticket = os.environ.get('CHILECOMPRA_TICKET')
        if not ticket:
            raise SourceError('Falta CHILECOMPRA_TICKET. Solicita tu ticket oficial y configúralo de forma segura.')
        self.store.reserve_request()
        url = BASE + ('/' + urllib.parse.quote(code, safe='') if code else '')
        if params:
            url += '?' + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={'ticket': ticket, 'Accept': 'application/json', 'User-Agent': 'BuscadorPendones/2.0'})
        try:
            with urllib.request.build_opener(SafeRedirect()).open(request, timeout=30) as response:
                raw = response.read(10 * 1024 * 1024 + 1)
                if len(raw) > 10 * 1024 * 1024:
                    raise SourceError('Respuesta oficial demasiado grande; no se procesó parcialmente.')
            data = json.loads(raw)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                # Stop the entire cycle. Honor Retry-After and at least 24 h to avoid a daily-quota loop.
                delay = 86400
                retry = exc.headers.get('Retry-After', '')
                if retry.isdigit():
                    delay = max(delay, int(retry))
                self.store.set_meta(reintentar_desde=iso(now() + timedelta(seconds=delay)))
                raise SourceError('API 429: cuota agotada. Consultas pausadas al menos 24 horas; revisar cuota asignada.') from None
            raise SourceError(f'La API respondió HTTP {exc.code}. Revisar ticket, permisos y disponibilidad.') from None
        except (urllib.error.URLError, OSError, ValueError):
            raise SourceError('No fue posible obtener JSON de la API oficial. Revisar red y disponibilidad.') from None
        if not isinstance(data, dict) or data.get('success') != 'OK' or not isinstance(data.get('payload'), dict):
            raise SourceError('La API no entregó una respuesta exitosa con el esquema documentado.')
        time.sleep(0.25)  # Sequential, bounded traffic. No parallel detail flood.
        return data['payload']


class Synchronizer:
    def __init__(self, store, api=None):
        self.store = store
        self.api = api or API(store)
        self.lock = threading.Lock()

    def run(self):
        if not self.lock.acquire(blocking=False):
            return
        try:
            meta = self.store.metadata()
            retry = timestamp(meta.get('reintentar_desde'))
            if retry and retry > now():
                return
            if not os.environ.get('CHILECOMPRA_TICKET') and isinstance(self.api, API):
                raise SourceError('Falta CHILECOMPRA_TICKET. El monitoreo no está activo.')
            end = now()
            self.store.set_meta(estado='sincronizando', ultimo_intento=iso(end))
            initial = meta.get('inicio_completado') != 'si'
            params = {'tamano_pagina': 50, 'ordenar_por': 'FechaUltimaModificacion'}
            if initial:
                # Seed all open purchases nationwide, not only purchases with title matches.
                params.update(estado='publicada', publicado_hasta=iso(end))
            else:
                start = timestamp(meta.get('cursor'))
                if start is None:
                    raise SourceError('Cursor inválido. Revisar almacenamiento antes de sincronizar.')
                # Include every state so closure/cancellation removes old opportunities.
                params.update(cambio_desde=iso(start - timedelta(minutes=5)), cambio_hasta=iso(end))
            rows = {}
            page = 1
            while True:
                payload = self.api.get(params={**params, 'numero_pagina': page})
                pagination = payload.get('paginacion', {})
                items = payload.get('items')
                total = pagination.get('total_paginas')
                if (not isinstance(items, list) or type(total) is not int or total < 0
                        or pagination.get('numero_pagina') != page):
                    raise SourceError('Paginación oficial inesperada: no se adelantó el cursor.')
                for row in items:
                    if not isinstance(row, dict) or not isinstance(row.get('codigo'), str) or not row['codigo']:
                        raise SourceError('Registro sin código: no se adelantó el cursor.')
                    rows[row['codigo']] = compact(row)
                if page >= total:
                    break
                page += 1
            self.store.ingest(list(rows.values()), iso(end), bootstrap=initial)
            for code, row in self.store.pending():
                if row.get('estado', {}).get('codigo') != 'publicada':
                    self.store.save_detail(code, row)
                    continue
                detail = self.api.get(code=code)
                if detail.get('codigo') != code:
                    raise SourceError('El detalle no corresponde al código solicitado.')
                self.store.save_detail(code, compact(detail))
            self.store.set_meta(estado='actualizado', ultima_sincronizacion=iso(now()), error='')
        except (SourceError, sqlite3.Error) as exc:
            self.store.set_meta(estado='pendiente', error=str(exc))
        except Exception:
            # Unexpected schemas must be visible, never reported as an empty successful scan.
            self.store.set_meta(estado='error', error='Respuesta inesperada o fallo interno: sincronización incompleta. Revisar el adaptador y la documentación oficial.')
        finally:
            self.lock.release()

    def start(self):
        def loop():
            while True:
                self.run()
                time.sleep(INTERVAL)
        thread = threading.Thread(target=loop, daemon=True, name='chilecompra-hourly')
        thread.start()
        return thread


def opportunities(store, match, normalize):
    result, missing_items, unknown_dates, pending = [], 0, 0, 0
    current = now()
    for listed, detail, waiting in store.snapshot():
        pending += bool(waiting)
        # Never present an older detail as current while its modification is pending.
        if waiting or not detail or detail.get('estado', {}).get('codigo') != 'publicada':
            continue
        closing = timestamp(detail.get('fechas', {}).get('fecha_cierre'))
        if closing is None:
            unknown_dates += 1
            continue
        if closing <= current:
            continue
        products = detail.get('productos_solicitados')
        if not isinstance(products, list) or not products:
            missing_items += 1
            products = []
        demand = ' '.join(str(detail.get(k) or '') for k in ('nombre', 'descripcion'))
        product_text = ' '.join(str(p.get(k) or '') for p in products if isinstance(p, dict) for k in ('nombre', 'descripcion'))
        hits = sorted(set(m.group() for m in match.finditer(normalize(demand + ' ' + product_text))))
        if not hits:
            continue
        matching_products = [p for p in products if isinstance(p, dict) and match.search(normalize(str(p.get('nombre') or '') + ' ' + str(p.get('descripcion') or '')))]
        quantities = [str(p['cantidad']) + (' ' + str(p['unidad_medida']) if p.get('unidad_medida') else '') for p in matching_products if p.get('cantidad') is not None]
        budget = detail.get('presupuesto') or {}
        amount = budget.get('monto_disponible')
        if amount is None:
            amount = budget.get('presupuesto_estimado')
        currency = budget.get('moneda') or ''
        code = detail['codigo']
        result.append({
            'id': code, 'organismo': (detail.get('institucion') or {}).get('organismo_comprador'),
            'cantidad': '; '.join(quantities) or None,
            'presupuesto': (str(amount) + ' ' + currency).strip() if amount is not None else None,
            'fecha_cierre': detail['fechas']['fecha_cierre'],
            # This is the documented official detail resource, not an invented portal URL.
            'enlace': BASE + '/' + urllib.parse.quote(code, safe=''),
            'enlace_requiere_ticket': True,
            'items': products, 'items_disponibles': bool(products), 'coincidencias': hits,
        })
    return {
        'resultados': result, 'sincronizacion': store.metadata(), 'pendientes': pending,
        'sin_items': missing_items, 'fecha_no_interpretable': unknown_dates,
        'fuente': BASE, 'intervalo_segundos': INTERVAL,
        'cobertura': 'Fuente: Dirección ChileCompra, API Compra Ágil v2. Se consultan todas las regiones sin filtrar palabras en el listado. Los resultados son compras publicadas con cierre futuro según los datos recibidos. La cobertura depende de la API y de completar listado y detalles; no incluye adjuntos ni ítems omitidos por la fuente. Los cambios pueden tardar hasta el siguiente ciclo y el tiempo de procesamiento.',
    }
