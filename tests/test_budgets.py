import io
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from presupuestos import amount_clp, budget_opportunities, export, page
from sync import Store, iso, now


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'base.sqlite3')

    def tearDown(self):
        self.temp.cleanup()

    def put(self, code, amount, currency='CLP', state='publicada', deadline='2099-01-01T12:00:00Z'):
        row = {'codigo': code, 'nombre': 'PRUEBA: útiles de oficina', 'estado': {'codigo': state},
               'fechas': {'fecha_cierre': deadline}, 'montos': {'monto_disponible': amount, 'moneda': currency}}
        self.store.ingest([row], iso(now()), bootstrap=True)
        return row

    def test_strict_total_budget_without_keyword_or_item_requirement(self):
        self.put('BAJO', '99999.99')
        self.put('IGUAL', 100000)
        self.put('ALTO', 100001)
        data = budget_opportunities(self.store)
        self.assertEqual([r['id'] for r in data['resultados']], ['BAJO'])
        self.assertEqual(data['resultados'][0]['presupuesto_clp'], '99999.99')
        self.assertTrue(data['resultados'][0]['detalle_pendiente'])
        self.assertEqual(len(self.store.pending()), 3)

    def test_foreign_currency_needs_explicit_official_clp_amount(self):
        self.assertIsNone(amount_clp({'montos': {'monto_disponible': 50, 'moneda': 'USD'}}))
        self.assertEqual(amount_clp({'montos': {'monto_disponible': 50, 'moneda': 'USD', 'monto_disponible_clp': 45000}}), Decimal('45000'))
        self.assertIsNone(amount_clp({'montos': {'monto_disponible': 50000}}))

    def test_invalid_and_unknown_amounts_are_not_invented(self):
        for value in (None, 'NaN', 'Infinity', '-1', True, '99.999,00', 'sin presupuesto'):
            with self.subTest(value=value):
                self.assertIsNone(amount_clp({'montos': {'monto_disponible': value, 'moneda': 'CLP'}}))
        self.assertEqual(amount_clp({'presupuesto': {'presupuesto_estimado': 50000, 'moneda': 'CLP'}}), Decimal('50000'))

    def test_expired_closed_and_ambiguous_dates_are_excluded(self):
        self.put('VENCIDA', 40000, deadline='2020-01-01T00:00:00Z')
        self.put('CANCELADA', 40000, state='cancelada')
        self.put('AMBIGUA', 40000, deadline='2099-01-01 12:00')
        self.put('SIN-MONTO', None)
        data = budget_opportunities(self.store)
        self.assertEqual(data['resultados'], [])
        self.assertEqual(data['fechas_ambiguas'], 1)
        self.assertEqual(data['sin_monto_clp'], 1)

    def test_stale_detail_does_not_override_changed_listing_budget(self):
        row = self.put('CAMBIO', 40000)
        self.store.save_detail('CAMBIO', row)
        changed = {**row, 'montos': {'monto_disponible': 200000, 'moneda': 'CLP'}}
        self.store.ingest([changed], iso(now()))
        self.assertEqual(budget_opportunities(self.store)['resultados'], [])

    def test_page_and_excel_disclose_partial_data_and_use_safe_text(self):
        row = self.put('ARCHIVO', 60000)
        row['nombre'] = '<script>alert(1)</script>'
        self.store.ingest([row], iso(now()))
        data = budget_opportunities(self.store)
        html = page(data).decode()
        self.assertIn('ARCHIVO', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertIn('Pendiente de descargar', html)
        with ZipFile(io.BytesIO(export(data))) as book:
            for name in book.namelist():
                ET.fromstring(book.read(name))
            self.assertIn('ARCHIVO', book.read('xl/worksheets/sheet1.xml').decode())
            self.assertIn('Caché parcial', book.read('xl/worksheets/sheet2.xml').decode())
