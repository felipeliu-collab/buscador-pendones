import tempfile
import unittest
from pathlib import Path

from app import TERMS, normalize
from avisos import AlertCenter
from sync import Store, iso, now, opportunities


def result(code):
    return {'id': code, 'titulo': 'PRUEBA: material institucional', 'donde_coincide': ['Ítems']}


class AlertTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'db.sqlite3')
        self.center = AlertCenter(self.store)

    def tearDown(self):
        self.temp.cleanup()

    def test_first_observation_is_silent_and_later_addition_is_an_event(self):
        self.assertEqual(self.center.observe([result('CONOCIDA')]), 0)
        self.assertEqual(self.center.history(), [])
        self.assertEqual(self.center.observe([result('CONOCIDA'), result('NUEVA')]), 1)
        self.assertEqual([e['id'] for e in self.center.history()], ['NUEVA'])
        self.assertEqual(self.center.history()[0]['donde_coincide'], ['Ítems'])

    def test_no_duplicate_after_restarts_or_title_changes(self):
        self.center.observe([])
        self.center.observe([result('NUEVA')])
        self.center.mark_shown(['NUEVA'])
        reopened = AlertCenter(Store(self.store.path))
        changed = {**result('NUEVA'), 'titulo': 'Otro título del mismo proceso'}
        self.assertEqual(reopened.observe([changed]), 0)
        self.assertEqual(len(reopened.history()), 1)
        self.assertEqual(reopened.history(pending_only=True), [])

    def test_muting_persists_and_keeps_history(self):
        self.center.observe([])
        self.center.set_enabled(False)
        self.center.observe([result('NUEVA')])
        reopened = AlertCenter(Store(self.store.path))
        self.assertFalse(reopened.enabled())
        self.assertEqual(len(reopened.history()), 1)
        reopened.set_enabled(True)
        self.assertTrue(self.center.enabled())

    def test_alert_for_pendon_only_in_a_newly_downloaded_item(self):
        self.center.observe(opportunities(self.store, TERMS, normalize)['resultados'])
        row = {'codigo': 'PRUEBA-ITEM', 'nombre': 'Material informativo', 'descripcion': 'Ver productos',
               'estado': {'codigo': 'publicada'}, 'fechas': {'fecha_cierre': '2099-01-01T12:00:00Z'}}
        self.store.ingest([row], iso(now()), bootstrap=True)
        self.center.observe(opportunities(self.store, TERMS, normalize)['resultados'])
        self.assertEqual(self.center.history(), [])
        self.store.save_detail('PRUEBA-ITEM', {**row, 'productos_solicitados': [{'nombre': 'Impresión', 'descripcion': 'Pendón de mesa', 'cantidad': 1}]})
        self.center.observe(opportunities(self.store, TERMS, normalize)['resultados'])
        self.assertEqual(self.center.history()[0]['id'], 'PRUEBA-ITEM')
        self.assertEqual(self.center.history()[0]['donde_coincide'], ['Ítems'])

    def test_expired_and_nonmatching_purchases_do_not_generate_alerts(self):
        self.center.observe([])
        for code, deadline, text in [('EXPIRADA', '2020-01-01T00:00:00Z', 'Pendón'), ('OTRA', '2099-01-01T00:00:00Z', 'Papel')]:
            doc = {'codigo': code, 'nombre': text, 'estado': {'codigo': 'publicada'}, 'fechas': {'fecha_cierre': deadline}, 'productos_solicitados': []}
            self.store.ingest([doc], iso(now()), bootstrap=True)
            self.store.save_detail(code, doc)
        self.center.observe(opportunities(self.store, TERMS, normalize)['resultados'])
        self.assertEqual(self.center.history(), [])

    def test_quota_failure_does_not_fabricate_an_alert(self):
        self.center.observe([])
        self.store.set_meta(estado='pendiente', http_status='429', error='Cuota agotada')
        self.center.observe(opportunities(self.store, TERMS, normalize)['resultados'])
        self.assertEqual(self.center.history(), [])


if __name__ == '__main__':
    unittest.main()
