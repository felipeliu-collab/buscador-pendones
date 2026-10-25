import io
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from app import PIN_TERMS, normalize
from excel import export_xlsx
from sync import Store, iso, now, opportunities


class PinTests(unittest.TestCase):
    def test_words_not_substrings(self):
        for text in ('pin', 'PINES', 'Pin metálico', 'pines de solapa', 'pín'):
            with self.subTest(text=text):
                self.assertTrue(PIN_TERMS.search(normalize(text)))
        for text in ('pintura', 'pincel', 'pinzas', 'alpines', 'PIN123', 'pins'):
            with self.subTest(text=text):
                self.assertFalse(PIN_TERMS.search(normalize(text)))

    def test_title_description_or_item_and_excel(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'cache.sqlite3')
            for code, title, description, item in [
                ('TITULO', 'Pines institucionales', 'Ver productos', 'Material'),
                ('DESCRIPCION', 'Material institucional', 'Se requiere pin metálico', 'Material'),
                ('ITEM', 'Material institucional', 'Ver productos', 'Pines de solapa'),
                ('OTRA', 'Pintura', 'Pinceles y pinzas', 'Papel'),
            ]:
                row = {'codigo': code, 'nombre': title, 'descripcion': description, 'estado': {'codigo': 'publicada'}, 'fechas': {'fecha_cierre': '2099-01-01T00:00:00Z'}, 'productos_solicitados': [{'nombre': 'Producto', 'descripcion': item, 'cantidad': 2}]}
                store.ingest([row], iso(now()), bootstrap=True)
                store.save_detail(code, row)
            data = opportunities(store, PIN_TERMS, normalize)
            found = {r['id']: r for r in data['resultados']}
            self.assertEqual(set(found), {'TITULO', 'DESCRIPCION', 'ITEM'})
            self.assertEqual(found['ITEM']['donde_coincide'], ['Ítems'])
            self.assertEqual(found['DESCRIPCION']['donde_coincide'], ['Descripción'])
            data['busqueda'] = 'pin o pines'
            with ZipFile(io.BytesIO(export_xlsx(data))) as book:
                sheet = book.read('xl/worksheets/sheet1.xml').decode()
                self.assertIn('Pines de solapa', sheet)
                self.assertNotIn('Pinceles y pinzas', sheet)
                self.assertIn('pin o pines', book.read('xl/worksheets/sheet3.xml').decode())
