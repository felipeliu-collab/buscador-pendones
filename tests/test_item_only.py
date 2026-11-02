import tempfile
import unittest
from pathlib import Path
from app import ITEM_PENDON_TERMS, normalize
from sync import Store, item_only_opportunities, iso, now


class ItemOnlyTests(unittest.TestCase):
    def test_requires_product_excludes_title_and_unverified_or_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'cache.sqlite3')
            cases = [('HIDDEN', 'Material institucional', 'Detalle', 'Pendón roller', 'publicada'),
                     ('BOTH', 'Pendones', '', 'Pendón', 'publicada'),
                     ('DESCRIPTION', 'Material', 'Pendón', 'Papel', 'publicada'),
                     ('CLOSED', 'Material', '', 'Pendón', 'cerrada'),
                     ('PENDING', 'Material', '', 'Pendón', 'publicada'),
                     ('EXPIRED', 'Material', '', 'Pendón', 'publicada')]
            for code, title, description, product, state in cases:
                doc = {'codigo': code, 'nombre': title, 'descripcion': description,
                       'estado': {'codigo': state}, 'fechas': {'fecha_cierre': '2000-01-01T00:00:00Z' if code == 'EXPIRED' else '2099-01-01T00:00:00Z'},
                       'productos_solicitados': [{'nombre': product, 'cantidad': 2}]}
                store.ingest([doc], iso(now()), bootstrap=True)
                if code != 'PENDING':store.save_detail(code, doc)
            data = item_only_opportunities(store, ITEM_PENDON_TERMS, normalize)
            self.assertEqual([r['id'] for r in data['resultados']], ['HIDDEN'])
            self.assertEqual(data['resultados'][0]['donde_coincide'], ['Ítems'])
            self.assertEqual(data['coincidencias_items_sin_titulo'], 1)
            self.assertEqual(data['pendientes'], 1)
