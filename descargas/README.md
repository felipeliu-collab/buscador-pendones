# Base parcial en Excel

[Descargar Excel](https://github.com/felipeliu-collab/buscador-pendones/raw/refs/heads/main/descargas/base_compras_agiles_PARCIAL_2026-10-25.xlsx)

Archivo preparado el 25 de octubre de 2026 con datos públicos previamente descargados de la API oficial Compra Ágil v2 de la Dirección ChileCompra. Contiene 6.965 filas del listado disponible, 2.608 filas de ítems descargados y 37 coincidencias de los términos del buscador. No contiene el ticket de acceso.

**Es un archivo estático y parcial, no una base nacional completa ni una lista de oportunidades vigentes actualizada.** Quedaron 6.047 detalles sin consultar debido a la cuota de la API. Puede haber compras omitidas, cerradas o modificadas desde la consulta. El término roller también puede referirse a cortinas. Comprueba estado, cierre y requisitos en Mercado Público antes de ofertar. La hoja «LEER - Cobertura» contiene los límites y las fechas de los datos.

## Excel para revisar título, descripción e ítems

[Descargar Excel de revisión](https://github.com/felipeliu-collab/buscador-pendones/raw/refs/heads/main/descargas/pendones_revision_titulo_descripcion_items_2026-10-25.xlsx)

Incluye las 37 coincidencias disponibles al exportar, sus ítems y las columnas **Descripción de la compra** y **Encontrado en** (título, descripción o ítems). La hoja **Estado** advierte que la base es parcial: quedaron 6.047 detalles pendientes. No se hicieron nuevas consultas a la API. No es una base completa ni garantiza vigencia posterior a la consulta.

## Compras Ágiles menores a $100.000 CLP

[Descargar Excel de compras menores a $100.000](https://github.com/felipeliu-collab/buscador-pendones/raw/refs/heads/main/descargas/compras_menores_100000_PARCIAL_2026-10-25.xlsx)

Exportación estática del 25 de octubre de 2026 con 252 resultados de la caché oficial disponible, de cualquier producto o servicio. El presupuesto total informado es estrictamente menor a $100.000 CLP; las de exactamente ese monto quedan fuera. Entre esos resultados, 210 tienen detalles pendientes: el filtro se pudo aplicar con el monto y el cierre del listado. No contiene el ticket ni se realizaron nuevas consultas. La hoja Estado explica que la base es parcial y que deben confirmarse vigencia, presupuesto y requisitos en Mercado Público antes de ofertar.

## Segundo llamado, presupuesto menor a $500.000 CLP

[Descargar Excel de segundo llamado bajo $500.000](https://github.com/felipeliu-collab/buscador-pendones/raw/refs/heads/main/descargas/compras_agiles_segundo_llamado_menos_500000_PARCIAL_2026-10-25.xlsx)

Exportación estática y parcial del 25 de octubre de 2026 con 180 resultados del listado oficial guardado. Se exige estado publicado, cierre futuro interpretable, presupuesto total informado estrictamente menor a $500.000 CLP y `convocatoria.estado_convocatoria=2` explícito. Tener una fecha de segundo llamado no basta para incluirse. Hay 145 resultados con detalles pendientes. No se hicieron nuevas consultas a la API ni se incluyó el ticket. Confirma vigencia y requisitos en Mercado Público antes de ofertar.
