"""Datos sintéticos de prueba: no representan compras reales."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from app import Handler, download, official_url, search
from sync import Store
from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError
from avisos import AlertCenter

SOURCE = 'https://datos-abiertos.chilecompra.cl/'


class SearchTests(unittest.TestCase):
    def test_browser_disconnect_does_not_raise_but_other_errors_remain_visible(self):
        handler = Handler.__new__(Handler)
        for error in (ConnectionResetError(10054, 'client closed'), ConnectionAbortedError(), BrokenPipeError()):
            with self.subTest(error=type(error).__name__), patch.object(handler, '_send', side_effect=error):
                handler.send(200, {'estado': 'ok'})
                self.assertTrue(handler.close_connection)
        with patch.object(handler, '_send', side_effect=RuntimeError('real server bug')):
            with self.assertRaises(RuntimeError):
                handler.send(200, {})

    def test_nested_items_accents_and_missing_fields(self):
        records = [
            {'id': 'PRUEBA-1', 'tipo': 'Compra Ágil', 'titulo': 'Material institucional',
             'items': [{'descripcion': 'Impresión de mini pendón', 'cantidad': 4}]},
            {'id': 'PRUEBA-2', 'tipo': 'Compra Ágil', 'descripcion': 'PENDONES y roller'},
            {'id': 'PRUEBA-3', 'tipo': 'Licitación', 'descripcion': 'pendón'},
            {'id': 'PRUEBA-4', 'tipo': 'Compra Ágil', 'descripcion': 'papelería'},
            {'id': 'PRUEBA-5', 'descripcion': 'pendón'},
            {'tipo': 'Compra Ágil', 'descripcion': 'pendón'},
        ]
        data = search(json.dumps(records), SOURCE)
        self.assertEqual([r['id'] for r in data['resultados']], ['PRUEBA-1', 'PRUEBA-2'])
        self.assertEqual(data['excluidos_por_modalidad'], 2)
        self.assertEqual(data['coincidencias_sin_id'], 1)
        first = data['resultados'][0]
        self.assertTrue(first['items_disponibles'])
        self.assertIsNone(first['presupuesto'])
        self.assertIsNone(first['cantidad'])  # Do not sum unlike item units.
        self.assertIsNone(first['enlace'])
        self.assertFalse(data['resultados'][1]['items_disponibles'])

    def test_csv_and_untrusted_links(self):
        content = 'id;tipo;descripcion;cantidad;presupuesto;enlace\nPRUEBA;Compra Ágil;ROLLER;2;50000;https://example.com\n'
        row = search(content, SOURCE)['resultados'][0]
        self.assertEqual(row['cantidad'], '2')
        self.assertEqual(row['presupuesto'], '50000')
        self.assertIsNone(row['enlace'])

    def test_word_boundaries_and_empty_results(self):
        data = search(json.dumps([{'id': 'PRUEBA', 'tipo': 'Compra Ágil', 'descripcion': 'controladores y pendonista'}]), SOURCE)
        self.assertEqual(data['resultados'], [])

    def test_reject_unofficial_sources_and_bad_formats(self):
        for url in ['http://www.mercadopublico.cl/', 'https://www.mercadopublico.cl.ejemplo.com/', 'https://user:pass@www.mercadopublico.cl/', 'https://127.0.0.1/', 'https://www.mercadopublico.cl:8080/']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                official_url(url)
        for content in ['', '{"unexpected": []}', '[1]']:
            with self.subTest(content=content), self.assertRaises(ValueError):
                search(content, SOURCE)

    def test_download_rejects_private_resolution(self):
        with patch('app.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]):
            with self.assertRaises(ValueError):
                download(SOURCE)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_store = Handler.store
        cls.previous_alerts = Handler.alerts
        cls.temp = tempfile.TemporaryDirectory()
        Handler.store = Store(Path(cls.temp.name) / 'test.sqlite3')
        Handler.alerts = AlertCenter(Handler.store)
        Handler.store.set_meta(estado='pendiente', error='DIAGNÓSTICO SINTÉTICO', conexion='error_red_o_respuesta')
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        Handler.store = cls.previous_store
        Handler.alerts = cls.previous_alerts
        cls.temp.cleanup()

    def test_page_assets_and_health(self):
        for path in ['/', '/app.js', '/app.js?v=3', '/legacy.js', '/monitor', '/style.css', '/api/health', '/api/estado']:
            with urllib.request.urlopen(self.base + path) as response:
                self.assertEqual(response.status, 200)
                self.assertTrue(response.read())

    def test_diagnostics_and_server_rendered_fallback(self):
        with urllib.request.urlopen(self.base + '/api/estado') as response:
            state = json.load(response)
        self.assertEqual(state['servidor'], 'activo')
        self.assertIsInstance(state['ticket_configurado'], bool)
        self.assertEqual(state['sincronizacion']['error'], 'DIAGNÓSTICO SINTÉTICO')
        with urllib.request.urlopen(self.base + '/') as response:
            page = response.read().decode()
        self.assertIn('Servidor activo', page)
        self.assertIn('DIAGNÓSTICO SINTÉTICO', page)
        self.assertNotIn('<!--SERVER_STATUS-->', page)
        self.assertNotIn('Sin comprobar', page)
        self.assertIn('Activo · respuesta generada por el servidor', page)

    def test_frame_policy_allows_same_origin_only_by_default(self):
        with urllib.request.urlopen(self.base + '/') as response:
            policy = response.headers['Content-Security-Policy']
        self.assertIn("frame-ancestors 'self'", policy)
        self.assertNotIn("frame-ancestors 'none'", policy)

    def test_home_renders_actual_cache_without_javascript_and_escapes_content(self):
        previous = Handler.store
        try:
            with tempfile.TemporaryDirectory() as directory:
                Handler.store = Store(Path(directory) / 'cache.sqlite3')
                row = {'codigo': 'PRUEBA-SSR', 'nombre': '<img src=x onerror=alert(1)>',
                       'estado': {'codigo': 'publicada'}, 'fechas': {'fecha_cierre': '2099-01-01T12:00:00Z'},
                       'productos_solicitados': [{'nombre': 'pendón', 'cantidad': 2}]}
                Handler.store.ingest([row], '2026-01-01T00:00:00Z', bootstrap=True)
                Handler.store.save_detail('PRUEBA-SSR', row)
                with urllib.request.urlopen(self.base + '/') as response:
                    page = response.read().decode()
                self.assertIn('PRUEBA-SSR', page)
                self.assertIn('1 coincidencias', page)
                self.assertIn('&lt;img src=x onerror=alert(1)&gt;', page)
                self.assertNotIn('<img src=x', page)
                self.assertIn('<table id="results">', page)
        finally:
            Handler.store = previous

    def test_monitor_works_without_javascript(self):
        with urllib.request.urlopen(self.base + '/monitor') as response:
            page = response.read().decode()
        self.assertIn('http-equiv="refresh" content="30"', page)
        self.assertIn('DIAGNÓSTICO SINTÉTICO', page)
        self.assertIn('Última sincronización completa', page)
        self.assertNotIn('<script', page)
        self.assertIn('Descargar Excel', page)
        self.assertIn('./descargar.xlsx', page)

    def test_alert_history_works_without_javascript_and_escapes_titles(self):
        Handler.alerts.observe([])
        Handler.alerts.observe([{'id': 'PRUEBA-AVISO', 'titulo': '<script>alert(1)</script>', 'donde_coincide': ['Ítems']}])
        with urllib.request.urlopen(self.base + '/avisos') as response:
            page = response.read().decode()
        self.assertIn('PRUEBA-AVISO', page)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', page)
        self.assertNotIn('<script>', page)
        self.assertIn('No significa necesariamente una publicación nueva', page)

    def test_excel_download_is_an_attachment_and_makes_no_api_calls(self):
        import io
        from zipfile import ZipFile
        with patch('sync.API.get', side_effect=AssertionError('Download must use cache')):
            with urllib.request.urlopen(self.base + '/descargar.xlsx') as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                self.assertIn('attachment; filename="pendones.xlsx"', response.headers['Content-Disposition'])
                with ZipFile(io.BytesIO(response.read())) as book:
                    self.assertIn('xl/workbook.xml', book.namelist())

    def test_budget_search_routes_do_not_call_api(self):
        import io
        from zipfile import ZipFile
        with patch('sync.API.get', side_effect=AssertionError('Budget search must use cache')):
            with urllib.request.urlopen(self.base + '/menores-100000') as response:
                self.assertIn('Compras Ágiles menores a $100.000', response.read().decode())
            with urllib.request.urlopen(self.base + '/api/menores-100000') as response:
                self.assertIn('sin_monto_clp', json.load(response))
            with urllib.request.urlopen(self.base + '/menores-100000.xlsx') as response:
                self.assertIn('compras_menores_100000.xlsx', response.headers['Content-Disposition'])
                with ZipFile(io.BytesIO(response.read())) as book:
                    self.assertIn('Compras menores a 100000', book.read('xl/workbook.xml').decode())

    def test_missing_windows_timezone_database_does_not_break_pages(self):
        Handler.store.set_meta(ultima_conexion_exitosa='2026-10-25T12:00:00Z', ultima_sincronizacion='2026-10-25T12:00:00Z')
        with patch('app.ZoneInfo', side_effect=ZoneInfoNotFoundError('America/Santiago')):
            for path in ('/', '/monitor'):
                with self.subTest(path=path), urllib.request.urlopen(self.base + path) as response:
                    page = response.read().decode()
                self.assertIn('25/10/2026 12:00:00 UTC', page)
                self.assertIn('zona de Chile no disponible', page)

    def test_search_endpoint_exercises_nested_description(self):
        payload = {'fuente': SOURCE, 'contenido': json.dumps([{'id': 'PRUEBA-HTTP', 'tipo': 'Compra Ágil', 'items': [{'descripcion': 'pendón'}]}])}
        request = urllib.request.Request(self.base + '/api/buscar', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request) as response:
            data = json.load(response)
        self.assertEqual(data['resultados'][0]['id'], 'PRUEBA-HTTP')
        self.assertIsNone(data['resultados'][0]['presupuesto'])

    def test_source_failure_is_not_an_empty_success(self):
        with patch('app.download', side_effect=urllib.error.URLError('blocked')):
            request = urllib.request.Request(self.base + '/api/buscar', data=json.dumps({'fuente': SOURCE}).encode())
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request)
            self.assertEqual(caught.exception.code, 502)
            self.assertIn('No fue posible', json.load(caught.exception)['error'])


if __name__ == '__main__':
    unittest.main()
