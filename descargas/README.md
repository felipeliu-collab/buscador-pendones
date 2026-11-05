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

### Base recibida el 27 de octubre de 2026 (actualización parcial)

`base_compra_agil_ACTUALIZACION_PARCIAL_2026-10-27.xlsx`: exportación nueva tras recibir 200 páginas de cambios mediante la API Compra Ágil v2 (10.000 registros listados). Contiene 14.496 registros acumulados, 38 coincidencias de pendón/pendones en los campos disponibles y 2.787 líneas de ítems almacenadas. No es una lista de 14.496 oportunidades vigentes: incluye registros anteriores y estados distintos de publicada. Faltan más de 13.000 detalles por actualizar. Las coincidencias tampoco acreditan vigencia; verificar estado y fecha. La hoja `LEER cobertura` incluye el cursor real y los pendientes. El ticket no se exporta. Es una instantánea del avance, no una sincronización completada.

### Archivo para revisar oportunidades vigentes

`pendones_SOLO_VIGENTES_VERIFICADAS_2026-10-27.xlsx` se prepara con una nueva consulta individual de cada compra incluida: exige estado oficial `publicada`, fecha de cierre futura con zona interpretable y coincidencia pendón/pendones en título, descripción o ítems. Revisa la fecha de verificación de cada fila y la hoja de cobertura. Es parcial por los ítems todavía no descargados. **La base acumulada `base_compra_agil_ACTUALIZACION_PARCIAL_2026-10-27.xlsx` contiene también cerradas y NO debe usarse como una lista de oportunidades vigentes.**

### Menores a $100.000 — listado nuevo del 1 de noviembre de 2026

Usar `compras_MENORES_100000_LISTADO_NUEVO_2026-11-01.xlsx` para esta revisión, en lugar de la selección anterior de 11 candidatas almacenadas. Se consultaron de nuevo las 130 páginas que informó la API oficial con `estado=publicada`, `tamano_pagina=50`, `ordenar_por=FechaPublicacion` y un límite de publicación fijo al inicio. Se recibieron 6.473 IDs únicos y se exportaron 273 que cumplieron estado publicada, presupuesto total oficial en CLP estrictamente menor a 100.000 y cierre futuro interpretable. Se eliminaron duplicados y se ordenó por cierre. No se reutilizaron las filas ni los ítems de octubre. Los campos corresponden al listado; no se descargaron detalles ni adjuntos. La hoja de cobertura registra horarios, páginas, exclusiones y límites por cambios durante la paginación. Confirmar vigencia antes de ofertar.

### Pendones — consulta nueva del 2 de noviembre de 2026

`pendones_VIGENTES_PARCIAL_2026-11-02.xlsx`: listado nuevo de 121 páginas con 5.931 códigos únicos. Se identificaron 19 candidatas por texto del listado o ítems almacenados; solo se alcanzó a verificar el detalle de 4 antes de HTTP 429. El Excel incluye únicamente esas 4 compras confirmadas como publicadas, con cierre futuro y pendón/pendones en título, descripción o ítems. No incluye las 15 candidatas sin verificar. La cobertura de ítems es incompleta y no se revisaron adjuntos. Incluye tiempos de consulta, límites y error de cuota en la hoja de cobertura. No reutiliza como vigentes las oportunidades de la planilla de octubre.

### Menores a $100.000 — consulta nueva del 4 de noviembre de 2026 (hora de Chile)

`compras_MENORES_100000_LISTADO_NUEVO_2026-11-04.xlsx`: nueva consulta completa de las 200 páginas informadas por la API, con 10.000 registros únicos recibidos y 340 compras exportadas que cumplen estado publicada, presupuesto total oficial estrictamente menor a $100.000 CLP y cierre futuro interpretable. Se incorporó el listado nuevo a la base local sin adelantar el cursor de cambios de todos los estados. La planilla se ordena por cierre y agrega cierre en hora de Chile continental. Se basa en los campos del listado; no se consultaron detalles ni adjuntos. La cobertura depende de los resultados y límites de la API; el estado puede cambiar después. No se reutilizó la planilla del 2 de noviembre. El nombre usa la fecha de Chile, mientras los horarios UTC de consulta son del 5 de noviembre.

### Segundo llamado sin límite de presupuesto — 4 de noviembre de 2026

`SEGUNDO_LLAMADO_ACTUAL_SIN_LIMITE_2026-11-04.xlsx` contiene 189 IDs únicos con llamado actual explícito 2, estado publicada y cierre futuro; no filtra presupuesto ni producto. Parte del listado nuevo de 200 páginas recibido minutos antes y consulta nuevamente los cambios de todos los estados desde cinco minutos antes del inicio de ese listado; la API no reportó registros cambiados en ese intervalo. La cobertura sigue dependiendo de los límites de la fuente y la paginación, no acredita exhaustividad nacional. Los ítems no se incluyen. Reemplaza para esta solicitud al archivo anterior de solo 3 compras bajo $100.000: aquel tenía un límite que el usuario no deseaba.
