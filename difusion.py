"""Búsqueda literal normalizada; no afirma haber leído documentos no disponibles."""
import html
import json
import re
from datetime import timedelta
from urllib.parse import urlsplit
from excel import workbook
from sync import opportunities, now, timestamp

TERMS = re.compile(r'\bdifusion\b')
DOCUMENTS = ('Documentos públicos: NO REVISADOS. El adaptador actual no dispone de una fuente '
             'documentada para enumerar y descargar todos los adjuntos públicos. Una compra cuya '
             'única coincidencia esté en un documento puede faltar. No se eluden permisos ni se consultan documentos privados.')


def diffusion_data(store, normalize):
    data = opportunities(store, TERMS, normalize)
    details = {d['codigo']: d for _, d, waiting in store.snapshot() if d and not waiting}
    current = now()
    unique = {}
    for row in data['resultados']:
        detail = details.get(row['id'], {})
        institution = detail.get('institucion') or {}
        row['region'] = institution.get('nombre_region') or institution.get('region')
        row['proxima_a_vencer'] = timestamp(row['fecha_cierre']) <= current + timedelta(hours=24)
        # Only accept an explicitly supplied official portal link; never synthesize one.
        row['enlace_directo'] = None
        links = detail.get('links') or {}
        values = links.values() if isinstance(links, dict) else links if isinstance(links, list) else []
        for value in values:
            if isinstance(value, str):
                parsed = urlsplit(value)
                if (parsed.scheme == 'https' and parsed.hostname in ('www.mercadopublico.cl', 'mercadopublico.cl')
                        and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment):
                    row['enlace_directo'] = value
                    break
        unique[row['id']] = row
    data['resultados'] = sorted(unique.values(), key=lambda r: (timestamp(r['fecha_cierre']), r['id']))
    data['busqueda'] = 'Difusión o difusion en título, descripción general o ítems'
    data['documentos'] = DOCUMENTS
    return data


def diffusion_excel(data):
    rows = [['ID', 'Institución', 'Región', 'Título', 'Descripción', 'Ítems', 'Cantidades',
             'Presupuesto', 'Fecha de cierre UTC', 'Coincidencia encontrada', 'Enlace directo oficial',
             'Detalle API (requiere ticket)', 'Vencimiento']]
    for r in data['resultados']:
        rows.append([r['id'], r['organismo'], r['region'], r['titulo'], r['descripcion'],
                     json.dumps(r['items'], ensure_ascii=False),
                     '; '.join(str(i.get('cantidad', 'No informada')) + ' ' + str(i.get('unidad_medida') or '') for i in r['items'] if isinstance(i, dict)),
                     r['presupuesto'], r['fecha_cierre'], ', '.join(r['donde_coincide']) + ': difusión / difusion',
                     r['enlace_directo'] or 'No entregado por la fuente; buscar por ID en Mercado Público',
                     r['enlace'], 'VENCE EN 24 HORAS' if r['proxima_a_vencer'] else 'Más de 24 horas'])
    meta = data['sincronizacion']
    status = [['Dato', 'Valor'], ['Búsqueda', data['busqueda']], ['Fuente', data['fuente']],
              ['Cobertura', data['cobertura']], ['Documentos', DOCUMENTS],
              ['Última sincronización completa', meta.get('ultima_sincronizacion')],
              ['Estado', meta.get('estado', 'Sin iniciar')], ['Detalles pendientes', data['pendientes']],
              ['Advertencia', 'Resultados parciales. Vigencia según última respuesta oficial recibida; confirmar antes de ofertar.'],
              ['Enlaces', 'Solo se usa un enlace directo si lo entrega la fuente. La URL API requiere ticket.'],
              ['Celdas', 'Textos de más de 32.767 caracteres se recortan por el límite de Excel.']]
    return workbook([('Difusión', rows), ('Cobertura', status)])


def diffusion_page(data):
    esc = lambda v: html.escape(str(v if v is not None else 'No informado'))
    meta = data['sincronizacion']
    body = '''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="refresh" content="30"><link rel="stylesheet" href="/style.css"><title>Compras Ágiles · Difusión</title></head><body><main><h1>Compras Ágiles · Difusión</h1><p>Todo Chile. Busca difusión y difusion en título, descripción e ítems. Solo publicadas con fecha de cierre futura interpretada sin ambigüedad. Ordenadas por cierre.</p><p><a href="/monitor">Otras búsquedas</a> · <a class="download-button" href="/difusion.xlsx">Descargar Excel</a></p><form method="post" action="/difusion/actualizar"><button>Actualizar búsqueda desde ChileCompra</button></form><form method="post" action="/difusion/horaria"><button>'''
    body += ('Desactivar' if meta.get('repetir_cada_hora', 'si') == 'si' else 'Activar') + ' repetición cada hora</button></form>'
    body += '<p>La actualización utiliza el trabajador compartido con las otras búsquedas. Respeta cuotas y pausas de la API; requiere mantener el programa abierto. La página refresca la caché cada 30 segundos.</p>'
    body += '<p><strong>Estado:</strong> ' + esc(meta.get('estado', 'Sin iniciar')) + ' · Conexión: ' + esc(meta.get('conexion', 'Sin comprobar')) + ' · Última sincronización completa (UTC): ' + esc(meta.get('ultima_sincronizacion')) + ' · Próximo intento (UTC): ' + esc(meta.get('reintentar_desde') or meta.get('proximo_intento')) + '</p>'
    body += '<p>' + esc(meta.get('error') or 'Sin error registrado') + '</p><p><strong>' + esc(DOCUMENTS) + '</strong></p>'
    body += '<p>' + str(len(data['resultados'])) + ' coincidencias; ' + str(data['pendientes']) + ' detalles pendientes. Resultados parciales: cero coincidencias no demuestra ausencia. Confirma estado y cierre en Mercado Público antes de ofertar.</p><p>' + esc(data['cobertura']) + '</p>'
    body += '<div class="table-wrap"><table><thead><tr>' + ''.join('<th>' + x + '</th>' for x in ['Vencimiento', 'ID', 'Institución / región', 'Título / descripción', 'Ítems y cantidades', 'Presupuesto', 'Cierre UTC', 'Coincidencia', 'Enlace']) + '</tr></thead><tbody>'
    for r in data['resultados']:
        body += '<tr' + (' class="urgent"' if r['proxima_a_vencer'] else '') + '>'
        values = ['⚠ VENCE EN 24 HORAS' if r['proxima_a_vencer'] else 'Más de 24 horas', r['id'], str(r['organismo']) + ' / ' + str(r['region']), str(r['titulo']) + ' / ' + str(r['descripcion']), json.dumps(r['items'], ensure_ascii=False), r['presupuesto'], r['fecha_cierre'], ', '.join(r['donde_coincide'])]
        body += ''.join('<td>' + esc(v) + '</td>' for v in values)
        link = r['enlace_directo'] or r['enlace']
        body += '<td><a href="' + esc(link) + '">' + ('Mercado Público' if r['enlace_directo'] else 'API oficial (requiere ticket)') + '</a></td></tr>'
    return (body + '</tbody></table></div></main></body></html>').encode()
