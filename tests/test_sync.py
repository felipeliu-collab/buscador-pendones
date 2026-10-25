"""Fixtures sintéticas: no son oportunidades reales ni llamadas a ChileCompra."""
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from app import TERMS, normalize
from sync import API, BASE, SourceError, Store, Synchronizer, closing_time, connection_status, iso, now, opportunities


def listing(code, state='publicada'):
    return {'codigo': code, 'nombre': 'Materiales institucionales', 'estado': {'codigo': state},
            'fechas': {'fecha_cierre': iso(now() + timedelta(days=1))}}


def detail(code):
    return {**listing(code), 'productos_solicitados': [
        {'nombre': 'Impresión', 'descripcion': 'Mini pendón roller', 'cantidad': 3, 'unidad_medida': 'EA'}],
        'institucion': {'organismo_comprador': 'ORGANISMO SINTÉTICO'},
        'presupuesto': {'monto_disponible': 12000, 'moneda': 'CLP'}}


class FakeAPI:
    def __init__(self, pages, details):
        self.pages, self.details, self.calls = pages, details, []

    def get(self, code=None, params=None):
        self.calls.append((code, params))
        if code:
            value = self.details[code]
            if isinstance(value, Exception):
                raise value
            return value
        page = params['numero_pagina']
        return {'items': self.pages[page - 1], 'paginacion': {'numero_pagina': page, 'total_paginas': len(self.pages)}}


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'compras.db')

    def tearDown(self):
        self.temp.cleanup()

    def test_bootstrap_paginates_nationwide_and_fetches_every_detail(self):
        api = FakeAPI([[listing('PRUEBA-A')], [listing('PRUEBA-B')]],
                      {'PRUEBA-A': detail('PRUEBA-A'), 'PRUEBA-B': detail('PRUEBA-B')})
        Synchronizer(self.store, api).run()
        self.assertEqual(self.store.metadata()['estado'], 'actualizado')
        for code, params in api.calls:
            if params:
                self.assertNotIn('q', params)
                self.assertNotIn('region', params)
                self.assertEqual(params['estado'], 'publicada')
                self.assertEqual(params['tamano_pagina'], 50)
        found = opportunities(self.store, TERMS, normalize)
        self.assertEqual(len(found['resultados']), 2)
        self.assertEqual(found['resultados'][0]['cantidad'], '3 EA')
        self.assertEqual(found['resultados'][0]['presupuesto'], '12000 CLP')
        self.assertEqual(found['pendientes'], 0)

    def test_product_description_match_is_returned_without_a_title_match(self):
        doc = detail('PRUEBA-SOLO-ITEM')
        doc['nombre'] = 'Servicio de impresión institucional'
        doc['descripcion'] = 'Según especificaciones de productos'
        doc['productos_solicitados'] = [
            {'nombre': 'Tela de batik', 'descripcion': 'Pendón roller 80 x 200', 'cantidad': 1},
            {'nombre': 'Papel', 'descripcion': 'Hojas blancas', 'cantidad': 500},
        ]
        api = FakeAPI([[listing('PRUEBA-SOLO-ITEM')]], {'PRUEBA-SOLO-ITEM': doc})
        Synchronizer(self.store, api).run()
        found = opportunities(self.store, TERMS, normalize)
        self.assertEqual(len(found['resultados']), 1)
        result = found['resultados'][0]
        self.assertFalse(result['coincidencia_en_titulo'])
        self.assertTrue(result['coincidencia_en_items'])
        self.assertEqual(result['cantidad'], '1')
        self.assertEqual(result['items_coincidentes'], [doc['productos_solicitados'][0]])
        self.assertEqual(found['coincidencias_items_sin_titulo'], 1)
        self.assertEqual(found['coincidencias_en_items'], 1)
        self.assertIn(('PRUEBA-SOLO-ITEM', None), api.calls)

    def test_pending_details_do_not_prioritize_titles_and_survive_restart(self):
        hidden = listing('Z-SIN-PALABRA')
        titled = {**listing('A-CON-PALABRA'), 'nombre': 'Pendones'}
        self.store.ingest([hidden, titled], iso(now()), bootstrap=True)
        reopened = Store(self.store.path)
        self.assertEqual([code for code, _ in reopened.pending()], ['Z-SIN-PALABRA', 'A-CON-PALABRA'])
        reopened.save_detail('Z-SIN-PALABRA', detail('Z-SIN-PALABRA'))
        hidden['nombre'] = 'Actualización sin palabras clave'
        reopened.ingest([hidden], iso(now()))
        self.assertEqual([code for code, _ in reopened.pending()], ['A-CON-PALABRA', 'Z-SIN-PALABRA'])

    def test_resume_reads_hidden_item_before_listing_and_exports_it(self):
        import io
        from zipfile import ZipFile
        from excel import export_xlsx
        self.store.ingest([listing('PRUEBA-RETOMAR')], iso(now()), bootstrap=True)
        doc = detail('PRUEBA-RETOMAR')
        doc['nombre'] = 'Material de difusión'
        doc['descripcion'] = 'Ver productos solicitados'
        doc['productos_solicitados'] = [{'nombre': 'Impresión', 'descripcion': 'Pendón de mesa', 'cantidad': 2}]
        api = FakeAPI([[]], {'PRUEBA-RETOMAR': doc})
        Synchronizer(self.store, api).run()
        self.assertEqual(api.calls[0], ('PRUEBA-RETOMAR', None))
        self.assertIsNotNone(api.calls[1][1])
        found = opportunities(self.store, TERMS, normalize)
        self.assertEqual(found['coincidencias_items_sin_titulo'], 1)
        self.assertEqual(found['resultados'][0]['id'], 'PRUEBA-RETOMAR')
        with ZipFile(io.BytesIO(export_xlsx(found))) as book:
            sheet = book.read('xl/worksheets/sheet1.xml').decode()
            self.assertIn('PRUEBA-RETOMAR', sheet)
            self.assertIn('Pendón de mesa', sheet)

    def test_failure_resuming_items_does_not_advance_cursor_or_spend_on_listing(self):
        cursor = iso(now())
        self.store.ingest([listing('PRUEBA-LIMITE')], cursor, bootstrap=True)
        api = FakeAPI([[]], {'PRUEBA-LIMITE': SourceError('Cuota agotada en prueba')})
        Synchronizer(self.store, api).run()
        self.assertEqual(api.calls, [('PRUEBA-LIMITE', None)])
        self.assertEqual(self.store.metadata()['cursor'], cursor)
        self.assertEqual(len(self.store.pending()), 1)
        self.assertEqual(self.store.metadata()['estado'], 'pendiente')

    def test_incremental_does_not_filter_states_and_removes_closed_purchase(self):
        Synchronizer(self.store, FakeAPI([[listing('PRUEBA')]], {'PRUEBA': detail('PRUEBA')})).run()
        api = FakeAPI([[listing('PRUEBA', 'cancelada')]], {})
        Synchronizer(self.store, api).run()
        params = api.calls[0][1]
        self.assertIn('cambio_desde', params)
        self.assertIn('cambio_hasta', params)
        self.assertNotIn('estado', params)
        self.assertNotIn('publicado_desde', params)
        self.assertEqual(opportunities(self.store, TERMS, normalize)['resultados'], [])

    def test_detail_failure_is_queued_and_retry_does_not_lose_record(self):
        api = FakeAPI([[listing('PRUEBA')]], {'PRUEBA': SourceError('Fallo sintético')})
        Synchronizer(self.store, api).run()
        self.assertEqual(self.store.metadata()['estado'], 'pendiente')
        self.assertNotIn('ultima_sincronizacion', self.store.metadata())
        self.assertEqual(len(self.store.pending()), 1)
        Synchronizer(self.store, FakeAPI([[]], {'PRUEBA': detail('PRUEBA')})).run()
        self.assertEqual(len(opportunities(self.store, TERMS, normalize)['resultados']), 1)

    def test_bad_pagination_does_not_advance_cursor(self):
        api = FakeAPI([[]], {})
        with patch.object(api, 'get', return_value={'items': [], 'paginacion': {'total_paginas': 1, 'numero_pagina': 9}}):
            Synchronizer(self.store, api).run()
        self.assertNotIn('cursor', self.store.metadata())
        self.assertEqual(self.store.metadata()['estado'], 'pendiente')

    def test_expired_naive_dates_and_missing_items_are_explicit(self):
        docs = [detail('EXPIRED'), detail('NAIVE'), detail('NOITEMS')]
        docs[0]['fechas']['fecha_cierre'] = iso(now() - timedelta(seconds=1))
        docs[1]['fechas']['fecha_cierre'] = '2030-01-01T12:00:00'
        docs[2]['productos_solicitados'] = []
        docs[2]['nombre'] = 'Pendones'
        self.store.ingest(docs, iso(now()), bootstrap=True)
        for doc in docs:
            self.store.save_detail(doc['codigo'], doc)
        data = opportunities(self.store, TERMS, normalize)
        self.assertEqual([r['id'] for r in data['resultados']], ['NOITEMS'])
        self.assertEqual(data['fecha_no_interpretable'], 1)
        self.assertEqual(data['sin_items'], 1)
        self.assertFalse(data['resultados'][0]['items_disponibles'])

    def test_missing_ticket_does_not_call_network(self):
        with patch.dict('os.environ', {}, clear=True), patch('sync.urllib.request.build_opener') as opener:
            Synchronizer(self.store).run()
            opener.assert_not_called()
        self.assertIn('Falta CHILECOMPRA_TICKET', self.store.metadata()['error'])

    def test_auth_header_official_path_and_429_pause(self):
        import urllib.error
        from email.message import Message
        headers = Message()
        headers['Retry-After'] = '90000'
        error = urllib.error.HTTPError(BASE, 429, 'Too many requests', headers, None)
        with patch.dict('os.environ', {'CHILECOMPRA_TICKET': 'SYNTHETIC_TEST_ONLY'}), patch('sync.urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect = error
            with self.assertRaises(SourceError):
                API(self.store).get(params={'estado': 'publicada'})
            request = opener.return_value.open.call_args.args[0]
            self.assertTrue(request.full_url.startswith(BASE + '?'))
            self.assertEqual(request.get_header('Ticket'), 'SYNTHETIC_TEST_ONLY')
            self.assertNotIn('SYNTHETIC_TEST_ONLY', request.full_url)
        self.assertIn('reintentar_desde', self.store.metadata())
        fake = FakeAPI([[]], {})
        Synchronizer(self.store, fake).run()
        self.assertEqual(fake.calls, [])

    def test_transport_error_is_exact_but_credential_is_redacted(self):
        import urllib.error
        secret = 'SYNTHETIC_TEST_SECRET'
        with patch.dict('os.environ', {'CHILECOMPRA_TICKET': secret}), patch('sync.urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect = urllib.error.URLError('Tunnel connection failed: 403 Forbidden ' + secret)
            with self.assertRaises(SourceError) as caught:
                API(self.store).get()
            self.assertIn('Tunnel connection failed: 403 Forbidden', str(caught.exception))
            self.assertNotIn(secret, str(caught.exception))
            state = connection_status(self.store)
            self.assertTrue(state['ticket_configurado'])
            self.assertNotIn(secret, json.dumps(state))
            self.assertEqual(state['sincronizacion']['conexion'], 'error_red_o_respuesta')

    def test_initial_error_cleared_and_progress_persisted(self):
        self.store.set_meta(error='Falta CHILECOMPRA_TICKET. El monitoreo no está activo.')
        Synchronizer(self.store, FakeAPI([[listing('PRUEBA')]], {'PRUEBA': detail('PRUEBA')})).run()
        meta = self.store.metadata()
        self.assertEqual(meta['error'], '')
        self.assertEqual(meta['paginas_leidas'], '1')
        self.assertEqual(meta['registros_listados'], '1')
        self.assertEqual(meta['detalles_procesados_ciclo'], '1')
        self.assertEqual(connection_status(self.store)['detalles_guardados'], 1)

    def test_closing_uses_matching_explicit_call_date_not_guessed_timezone(self):
        raw = '2030-01-01 16:00'
        doc = {'fechas': {'fecha_cierre': raw}, 'convocatoria': {'estado_convocatoria': 1}}
        listed = {'fechas': {'fecha_cierre_primer_llamado': '2030-01-01T16:00:00Z'}, 'convocatoria': {'estado_convocatoria': 1}}
        self.assertEqual(iso(closing_time(doc, listed)), '2030-01-01T16:00:00+00:00')
        listed['convocatoria']['estado_convocatoria'] = 2
        self.assertIsNone(closing_time(doc, listed))
        listed['convocatoria']['estado_convocatoria'] = 1
        listed['fechas']['fecha_cierre_primer_llamado'] = '2030-01-01T20:00:00Z'
        self.assertIsNone(closing_time(doc, listed))


if __name__ == '__main__':
    unittest.main()
