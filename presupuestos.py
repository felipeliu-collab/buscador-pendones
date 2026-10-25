"""Compras bajo $100.000 CLP, sin filtrar producto ni hacer consultas nuevas."""
import html
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from excel import workbook
from sync import BASE, closing_time, iso, now

LIMIT = Decimal('100000')


def amount_clp(record):
    budget = record.get('presupuesto') or record.get('montos') or {}
    if not isinstance(budget, dict):
        return None
    value = budget.get('monto_disponible_clp')
    if value is None:
        if str(budget.get('moneda') or '').strip().upper() != 'CLP':
            return None
        value = budget.get('monto_disponible')
        if value is None:
            value = budget.get('presupuesto_estimado')
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        return None
    return result if result.is_finite() and result >= 0 else None


def budget_opportunities(store):
    results, missing_amount, ambiguous_date = [], 0, 0
    snapshot = store.snapshot()
    for listed, detail, pending in snapshot:
        record = detail if detail and not pending else listed
        if (record.get('estado') or {}).get('codigo') != 'publicada':
            continue
        amount = amount_clp(record)
        if amount is None:
            missing_amount += 1
            continue
        if amount >= LIMIT:
            continue
        closing = closing_time(record, listed)
        if closing is None:
            ambiguous_date += 1
            continue
        if closing <= now():
            continue
        results.append({
            'id': record['codigo'], 'titulo': record.get('nombre'),
            'descripcion': record.get('descripcion'),
            'organismo': (record.get('institucion') or {}).get('organismo_comprador'),
            'presupuesto_clp': str(amount), 'fecha_cierre': iso(closing),
            'detalle_pendiente': bool(pending or not detail),
            'items': record.get('productos_solicitados') or [],
            'enlace': BASE + '/' + quote(record['codigo'], safe=''),
        })
    results.sort(key=lambda row: (row['fecha_cierre'], row['id']))
    return {
        'resultados': results, 'sincronizacion': store.metadata(), 'fuente': BASE,
        'listado_guardado': len(snapshot), 'sin_monto_clp': missing_amount,
        'fechas_ambiguas': ambiguous_date,
        'cobertura': 'Solo el listado y los detalles oficiales ya descargados. No se garantiza cobertura nacional completa ni estado actualizado si la sincronización está pendiente. Se usa el presupuesto total informado en CLP o su conversión oficial a CLP; no se calculan tipos de cambio ni impuestos.',
    }


def money(value):
    text = f'{Decimal(value):,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    if text.endswith(',00'):
        text = text[:-3]
    return '$' + text + ' CLP'


def page(data):
    esc = lambda v: html.escape(str(v)) if v is not None else 'No informado'
    meta = data['sincronizacion']
    body = '''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="refresh" content="30"><title>Compras Ágiles menores a $100.000</title><link rel="stylesheet" href="./style.css"></head><body><main><h1>Compras Ágiles menores a $100.000</h1><p>De cualquier producto o servicio. Presupuesto total informado estrictamente menor a $100.000 CLP: las de exactamente $100.000 quedan fuera.</p><p><a href="./menores-100000">Actualizar vista</a> · <a href="./monitor">Buscador de Pendones</a></p><p><a class="download-button" href="./menores-100000.xlsx">Descargar Excel de compras menores a $100.000</a></p>'''
    body += '<aside><strong>' + str(len(data['resultados'])) + ' resultados en la caché disponible.</strong><p>Estado: ' + esc(meta.get('estado', 'iniciando')) + '. ' + esc(meta.get('error') or '') + '</p><p>' + esc(data['cobertura']) + '</p><p>Un monto de cero se muestra solo si la fuente lo informa; confirma el presupuesto en Mercado Público. Los avisos de pantalla actuales corresponden al buscador de pendones.</p></aside>'
    body += '<p>Compras publicadas sin monto CLP interpretable: ' + str(data['sin_monto_clp']) + '. Bajo el límite pero omitidas por fecha ambigua: ' + str(data['fechas_ambiguas']) + '.</p>'
    body += '<p>Se pueden mostrar compras con ítems pendientes si el listado permite verificar el monto y el cierre. Esta vista no hace consultas adicionales a la API. Los enlaces apuntan al recurso técnico de detalle, que requiere ticket; busca el ID en Mercado Público para ofertar.</p>'
    body += '<div class="table-wrap"><table><thead><tr><th>ID</th><th>Título</th><th>Organismo</th><th>Presupuesto total</th><th>Cierre</th><th>Detalle e ítems</th><th>Enlace</th></tr></thead><tbody>'
    for row in data['resultados']:
        body += '<tr><td>' + esc(row['id']) + '</td><td>' + esc(row['titulo']) + '</td><td>' + esc(row['organismo']) + '</td><td>' + esc(money(row['presupuesto_clp'])) + '</td><td>' + esc(row['fecha_cierre']) + '</td><td>' + ('Pendiente de descargar' if row['detalle_pendiente'] else 'Detalle descargado') + '</td><td><a href="' + esc(row['enlace']) + '">Detalle API</a></td></tr>'
    return (body + '</tbody></table></div></main></body></html>').encode()


def export(data):
    rows = [['ID', 'Título', 'Organismo', 'Presupuesto total CLP', 'Cierre informado', 'Detalle pendiente', 'Descripción', 'Enlace API (requiere ticket)']]
    for row in data['resultados']:
        rows.append([row['id'], row['titulo'], row['organismo'], row['presupuesto_clp'], row['fecha_cierre'], 'Sí' if row['detalle_pendiente'] else 'No', row['descripcion'], row['enlace']])
    meta = data['sincronizacion']
    status = [['Dato', 'Valor'], ['Filtro', 'Presupuesto total informado menor a 100.000 CLP; no es precio unitario.'],
              ['Exportado en UTC', iso(now())], ['Fuente', data['fuente']], ['Cobertura', data['cobertura']],
              ['Estado de sincronización', meta.get('estado')], ['Última sincronización completa', meta.get('ultima_sincronizacion')],
              ['Compras exportadas', len(data['resultados'])], ['Sin monto CLP interpretable', data['sin_monto_clp']],
              ['Fechas ambiguas omitidas', data['fechas_ambiguas']], ['Advertencia', 'Caché parcial. Confirma estado, presupuesto, impuestos y requisitos en Mercado Público antes de ofertar.']]
    return workbook([('Compras menores a 100000', rows), ('Estado', status)])
