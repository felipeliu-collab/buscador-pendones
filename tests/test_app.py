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

SOURCE = 'https://datos-abiertos.chilecompra.cl/'


class SearchTests(unittest.TestCase):
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
        cls.temp = tempfile.TemporaryDirectory()
        Handler.store = Store(Path(cls.temp.name) / 'test.sqlite3')
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
        cls.temp.cleanup()

    def test_page_assets_and_health(self):
        for path in ['/', '/app.js', '/app.js?v=3', '/style.css', '/api/health', '/api/estado']:
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
