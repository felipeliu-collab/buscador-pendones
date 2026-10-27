import io
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
from app import normalize
from difusion import diffusion_data, diffusion_excel, diffusion_page
from sync import Store, Synchronizer, iso, now


class DiffusionTests(unittest.TestCase):
    def test_fields_closed_pending_order_urgency_and_excel(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'cache.sqlite3')
            current = now()
            cases = [('TITLE', 'DIFUSIÓN', '', [], 48),
                     ('DESC', 'Servicios', 'difusion institucional', [], 20),
                     ('ITEM', 'Servicios', '', [{'nombre': 'Material de difusión', 'cantidad': 5}], 2),
                     ('CLOSED', 'Difusión', '', [], -1),
                     ('UNRELATED', 'Difusiones', '', [], 2),
                     ('CANCELLED', 'Difusión', '', [], 2),
                     ('PENDING', 'Difusión', '', [], 2)]
            for code, title, description, items, hours in cases:
                doc = {'codigo': code, 'nombre': title, 'descripcion': description,
                       'institucion': {'organismo_comprador': 'Institución de prueba', 'nombre_region': 'Región de prueba'},
                       'estado': {'codigo': 'cancelada' if code == 'CANCELLED' else 'publicada'},
                       'fechas': {'fecha_cierre': iso(current + timedelta(hours=hours))},
                       'productos_solicitados': items}
                store.ingest([doc], iso(current), bootstrap=True)
                if code != 'PENDING':
                    store.save_detail(code, doc)
            data = diffusion_data(store, normalize)
            self.assertEqual([r['id'] for r in data['resultados']], ['ITEM', 'DESC', 'TITLE'])
            self.assertEqual(data['resultados'][0]['donde_coincide'], ['Ítems'])
            self.assertEqual(data['resultados'][1]['donde_coincide'], ['Descripción'])
            self.assertTrue(data['resultados'][0]['proxima_a_vencer'])
            self.assertFalse(data['resultados'][2]['proxima_a_vencer'])
            self.assertEqual(data['resultados'][0]['region'], 'Región de prueba')
            self.assertIsNone(data['resultados'][0]['enlace_directo'])
            page = diffusion_page(data).decode()
            self.assertIn('NO REVISADOS', page)
            self.assertIn('action="/difusion/actualizar"', page)
            self.assertIn('action="/difusion/horaria"', page)
            self.assertIn('class="urgent"', page)
            with ZipFile(io.BytesIO(diffusion_excel(data))) as book:
                xml = book.read('xl/worksheets/sheet1.xml').decode()
                self.assertIn('VENCE EN 24 HORAS', xml)
                self.assertIn('s="1"', xml)
                self.assertNotIn('CLOSED', xml)
                self.assertIn('styles.xml', book.namelist()[book.namelist().index('xl/styles.xml')])

    def test_manual_request_respects_backoff(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'cache.sqlite3')
            store.set_meta(reintentar_desde=iso(now() + timedelta(hours=24)))
            worker = Synchronizer(store)
            worker.request_update()
            self.assertTrue(worker.wakeup.is_set())
            with patch.object(worker.api, 'get') as get:
                worker.run()
                get.assert_not_called()
            self.assertEqual(store.metadata()['estado'], 'pausado_por_cuota')
            self.assertEqual(store.metadata()['proximo_intento'], store.metadata()['reintentar_desde'])
            self.assertIn('actualizacion_solicitada', store.metadata())
