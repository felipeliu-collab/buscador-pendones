"""Exportación XLSX sin paquetes externos ni fórmulas provenientes de datos."""
import io
import json
from datetime import datetime, timezone
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


def column(number):
    result = ''
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def clean(value):
    if value is None:
        return 'No informado'
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    # XML 1.0 and Excel cell limits. Use inline strings even for '=' prefixed text.
    return ''.join(c for c in str(value) if c in '\t\n\r' or 0x20 <= ord(c) <= 0xD7FF or 0xE000 <= ord(c) <= 0xFFFD or 0x10000 <= ord(c) <= 0x10FFFF)[:32767]


def worksheet(rows):
    xml = [f'<worksheet xmlns="{NS}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><sheetData>']
    for row_index, row in enumerate(rows, 1):
        xml.append(f'<row r="{row_index}">')
        for col, value in enumerate(row, 1):
            style = ' s="1"' if 'VENCE EN 24 HORAS' in row else ''
            xml.append(f'<c r="{column(col)}{row_index}"{style} t="inlineStr"><is><t xml:space="preserve">{escape(clean(value))}</t></is></c>')
        xml.append('</row>')
    xml.append('</sheetData>')
    if rows:
        xml.append(f'<autoFilter ref="A1:{column(len(rows[0]))}{len(rows)}"/>')
    xml.append('</worksheet>')
    return ''.join(xml)


def export_xlsx(data):
    purchases = [['ID', 'Título', 'Organismo', 'Ítems', 'Cantidad de ítems coincidentes', 'Presupuesto informado', 'Fecha de cierre', 'Enlace API (requiere ticket)', 'Coincidencia en título', 'Coincidencia en ítems', 'Términos encontrados', 'Descripción de la compra', 'Encontrado en']]
    items = [['ID compra', 'Nombre del ítem', 'Descripción del ítem', 'Cantidad', 'Unidad de medida', 'Coincidente']]
    for result in data['resultados']:
        item_lines = []
        for item in result.get('items') or []:
            if isinstance(item, dict):
                parts = [str(item[k]) for k in ('nombre', 'descripcion') if item.get(k) is not None and item[k] != '']
                if item.get('cantidad') is not None:
                    parts.append('Cantidad: ' + str(item['cantidad']) + (' ' + str(item['unidad_medida']) if item.get('unidad_medida') else ''))
                item_lines.append(' | '.join(parts) or 'Ítem sin datos informados')
        purchases.append([result.get('id'), result.get('titulo'), result.get('organismo'), '\n'.join(item_lines) or 'No informado', result.get('cantidad'), result.get('presupuesto'), result.get('fecha_cierre'), result.get('enlace'), 'Sí' if result.get('coincidencia_en_titulo') else 'No', 'Sí' if result.get('coincidencia_en_items') else 'No', ', '.join(result.get('coincidencias', [])), result.get('descripcion'), ', '.join(result.get('donde_coincide') or []) or 'No informado'])
        for item in result.get('items') or []:
            if isinstance(item, dict):
                items.append([result.get('id'), item.get('nombre'), item.get('descripcion'), item.get('cantidad'), item.get('unidad_medida'), 'Sí' if item in result.get('items_coincidentes', []) else 'No'])
    meta = data.get('sincronizacion', {})
    complete = meta.get('estado') == 'actualizado' and data.get('pendientes', 0) == 0 and bool(meta.get('ultima_sincronizacion'))
    status = [
        ['Dato', 'Valor'], ['Exportado en UTC', datetime.now(timezone.utc).isoformat()],
        ['Fuente', data.get('fuente')], ['Cobertura', data.get('cobertura')],
        ['Búsqueda', data.get('busqueda', 'Pendón, pendones, roller o mini pendón en título, descripción o ítems')],
        ['Alcance de la exportación', 'Solo coincidencias de la caché automática al descargar. No incluye la importación manual.'],
        ['Carga', 'Ciclo completado según el estado guardado; cobertura sujeta a la fuente.' if complete else 'PARCIAL: carga incompleta o no actualizada. No representa todas las oportunidades.'],
        ['Estado de sincronización', meta.get('estado', 'Sin iniciar')],
        ['Última sincronización completa', meta.get('ultima_sincronizacion')],
        ['Detalles pendientes', data.get('pendientes', 0)],
        ['Compras exportadas', len(data['resultados'])],
        ['Fechas ambiguas omitidas', data.get('fecha_no_interpretable', 0)],
        ['Compras abiertas sin ítems', data.get('sin_items', 0)],
        ['Enlaces', 'Los enlaces API requieren autenticación. No contienen el ticket y no son enlaces directos para ofertar.'],
        ['Celdas extensas', 'Excel limita las celdas a 32.767 caracteres; los textos mayores se recortan.'],
    ]
    return workbook([('Compras', purchases), ('Items', items), ('Estado', status)])


def workbook(sheets):
    buffer = io.BytesIO()
    with ZipFile(buffer, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' + ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, len(sheets) + 1)) + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>')
        archive.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr('xl/workbook.xml', f'<workbook xmlns="{NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + ''.join(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>' for i, (name, _) in enumerate(sheets, 1)) + '</sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + ''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets) + 1)) + '<Relationship Id="styles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        archive.writestr('xl/styles.xml', f'<styleSheet xmlns="{NS}"><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFFE699"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="0" fillId="2" borderId="0" xfId="0" applyFill="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
        for i, (_, rows) in enumerate(sheets, 1):
            archive.writestr(f'xl/worksheets/sheet{i}.xml', worksheet(rows))
    return buffer.getvalue()
