import io
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from excel import export_xlsx


class ExcelTests(unittest.TestCase):
    def test_workbook_contains_results_items_and_partial_status_without_formulas(self):
        data = {
            'resultados': [{'id': 'PRUEBA-XLSX', 'titulo': '=HYPERLINK("https://example.com")',
                'organismo': 'Organismo & prueba', 'presupuesto': '100 CLP',
                'items': [{'nombre': 'Impresión', 'descripcion': 'Pendón\x00 <roller>', 'cantidad': 2}],
                'items_coincidentes': [{'nombre': 'Impresión', 'descripcion': 'Pendón\x00 <roller>', 'cantidad': 2}],
                'coincidencia_en_items': True, 'coincidencias': ['pendon']}],
            'pendientes': 10, 'sincronizacion': {'estado': 'pendiente', 'ticket': 'NO_EXPORTAR'},
            'fuente': 'https://api2.mercadopublico.cl/v2/compra-agil',
        }
        blob = export_xlsx(data)
        with ZipFile(io.BytesIO(blob)) as archive:
            self.assertIsNone(archive.testzip())
            for name in archive.namelist():
                ET.fromstring(archive.read(name))
            book = archive.read('xl/workbook.xml').decode()
            self.assertIn('name="Compras"', book)
            self.assertIn('name="Items"', book)
            self.assertIn('name="Estado"', book)
            purchases = archive.read('xl/worksheets/sheet1.xml').decode()
            self.assertIn('PRUEBA-XLSX', purchases)
            self.assertIn('=HYPERLINK', purchases)
            self.assertNotIn('<f>', purchases)
            self.assertIn('t="inlineStr"', purchases)
            self.assertIn('Pendón &lt;roller&gt;', archive.read('xl/worksheets/sheet2.xml').decode())
            status = archive.read('xl/worksheets/sheet3.xml').decode()
            self.assertIn('PARCIAL', status)
            self.assertNotIn('NO_EXPORTAR', ''.join(archive.read(n).decode() for n in archive.namelist()))

    def test_empty_export_keeps_headers_and_discloses_zero_results(self):
        with ZipFile(io.BytesIO(export_xlsx({'resultados': []}))) as archive:
            self.assertIn('Título', archive.read('xl/worksheets/sheet1.xml').decode())
            self.assertIn('PARCIAL', archive.read('xl/worksheets/sheet3.xml').decode())


if __name__ == '__main__':
    unittest.main()
