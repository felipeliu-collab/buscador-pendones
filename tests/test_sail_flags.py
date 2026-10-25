import io
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from app import SAIL_FLAG_TERMS, normalize
from excel import export_xlsx
from sync import Store, iso, now, opportunities


class SailFlagTests(unittest.TestCase):
    def test_names_and_variants(self):
        for text in ('bandera vela', 'BANDERAS VELAS', 'banderas tipo vela', 'bandera publicitaria tipo vela', 'bandera-vela', 'banderas con forma de vela'):
            with self.subTest(text=text):
                self.assertTrue(SAIL_FLAG_TERMS.search(normalize(text)))
        for text in ('velas de cera', 'banderas nacionales', 'banderazo', 'banderas tipo pluma'):
            with self.subTest(text=text):
                self.assertFalse(SAIL_FLAG_TERMS.search(normalize(text)))

    def test_independent_fields_items_and_export_without_cross_item_phrases(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'cache.sqlite3')
            variants = [
                ('TITULO', 'Banderas vela', 'Ver productos', [{'nombre': 'Material'}]),
                ('DESCRIPCION', 'Material institucional', 'Se requieren banderas tipo vela', []),
                ('ITEM', 'Material institucional', 'Ver productos', [{'nombre': 'Banderas', 'descripcion': 'tipo vela', 'cantidad': 2}]),
                ('CERA', 'Velas de cera', 'Material', []),
                ('CAMPOS-SEPARADOS', 'Banderas', 'vela', []),
                ('ITEMS-SEPARADOS', 'Material', 'Ver productos', [{'nombre': 'Banderas'}, {'nombre': 'Velas de cera'}]),
            ]
            for code, title, description, items in variants:
                doc = {'codigo': code, 'nombre': title, 'descripcion': description, 'estado': {'codigo': 'publicada'}, 'fechas': {'fecha_cierre': '2099-01-01T00:00:00Z'}, 'productos_solicitados': items}
                store.ingest([doc], iso(now()), bootstrap=True)
                store.save_detail(code, doc)
            data = opportunities(store, SAIL_FLAG_TERMS, normalize)
            results = {r['id']: r for r in data['resultados']}
            self.assertEqual(set(results), {'TITULO', 'DESCRIPCION', 'ITEM'})
            self.assertEqual(results['ITEM']['donde_coincide'], ['Ítems'])
            self.assertEqual(results['DESCRIPCION']['donde_coincide'], ['Descripción'])
            with ZipFile(io.BytesIO(export_xlsx(data))) as book:
                self.assertIn('Banderas vela', book.read('xl/worksheets/sheet1.xml').decode())
                self.assertNotIn('Velas de cera', book.read('xl/worksheets/sheet1.xml').decode())
