"""Diagnóstico desde consola. No requiere navegador ni muestra el ticket."""
import argparse
import json
import os
import urllib.request
from pathlib import Path

from app import ROOT, TERMS, normalize
from sync import API, SourceError, Store, opportunities, safe_error


def diagnose(store, port=8000, live=False):
    report = {'ticket_presente_codex': bool(os.environ.get('CHILECOMPRA_TICKET')), 'servidor': {}, 'api_oficial': {'probada_en_este_comando': False}}
    for path in ('/api/health', '/api/estado', '/api/oportunidades', '/monitor', '/'):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}', timeout=15) as response:
                body = response.read()
                entry = {'http': response.status, 'tipo': response.headers.get('Content-Type'), 'politica_frames': response.headers.get('Content-Security-Policy')}
                if path == '/api/estado':
                    entry['estado'] = json.loads(body)
                elif path == '/api/oportunidades':
                    data = json.loads(body)
                    entry['coincidencias'] = len(data['resultados'])
                    entry['pendientes'] = data['pendientes']
                report['servidor'][path] = entry
        except Exception as exc:
            report['servidor'][path] = {'error_exacto': f'{type(exc).__name__}: {safe_error(exc)}'}
    data = opportunities(store, TERMS, normalize)
    samples = sorted(data['resultados'], key=lambda r: (not (r['coincidencia_en_items'] and not r['coincidencia_en_titulo']), r['id']))[:3]
    report['cache_local'] = {
        'coincidencias': len(data['resultados']), 'detalles_pendientes': data['pendientes'],
        'ultima_sincronizacion_completa': store.metadata().get('ultima_sincronizacion'),
        'ejemplos_reales_de_cache': [{'id': r['id'], 'titulo': r['titulo'], 'en_titulo': r['coincidencia_en_titulo'], 'en_items': r['coincidencia_en_items']} for r in samples],
        'aviso': 'Datos parciales de la caché; las compras pueden cambiar entre consultas.',
    }
    if live:
        client = API(store)
        try:
            page = client.get(params={'estado': 'publicada', 'tamano_pagina': 10, 'numero_pagina': 1})
            report['api_oficial'] = {'probada_en_este_comando': True, 'http': 200, 'success': 'OK', 'paginacion': page.get('paginacion')}
            verified = []
            for sample in samples[:2]:
                detail = client.get(code=sample['id'])
                products = detail.get('productos_solicitados') or []
                hits = [p for p in products if TERMS.search(normalize(str(p.get('nombre') or '') + ' ' + str(p.get('descripcion') or '')))]
                verified.append({
                    'id': detail.get('codigo'), 'titulo': detail.get('nombre'),
                    'estado': detail.get('estado', {}).get('codigo'),
                    'coincidencia_titulo': bool(TERMS.search(normalize(str(detail.get('nombre') or '')))),
                    'items_coincidentes': [{'nombre': p.get('nombre'), 'descripcion': p.get('descripcion'), 'cantidad': p.get('cantidad')} for p in hits[:2]],
                    'http_detalle': 200,
                })
            report['api_oficial']['detalles_verificados_en_vivo'] = verified
        except SourceError as exc:
            report['api_oficial'].update(probada_en_este_comando=True, error_exacto=safe_error(exc))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--data-dir', default=str(ROOT / 'data'))
    parser.add_argument('--live', action='store_true', help='Consultar listado y hasta dos detalles oficiales con el ticket del entorno.')
    args = parser.parse_args()
    report = diagnose(Store(Path(args.data_dir) / 'compras.sqlite3'), args.port, args.live)
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    ticket = os.environ.get('CHILECOMPRA_TICKET')
    if ticket:
        encoded = encoded.replace(ticket, '[TICKET OCULTO]')
    print(encoded)
    raise SystemExit(1 if any('error_exacto' in r for r in report['servidor'].values()) or 'error_exacto' in report['api_oficial'] else 0)
