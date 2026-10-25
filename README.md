# Buscador de Pendones

Web en español que integra la **API oficial Compra Ágil v2 de ChileCompra** para buscar pendón, pendones, roller y mini pendón en nombres, descripciones y productos solicitados. Consulta sin filtro regional y muestra compras con estado `publicada` y cierre futuro con zona horaria explícita.

**Conector implementado y probado con fixtures; integración real pendiente de ticket y acceso de red a `api2.mercadopublico.cl`. No hay oportunidades reales precargadas ni se ha validado todavía la cobertura nacional en producción.**

## Fuente oficial verificada documentalmente

- [Página oficial de la API y solicitud de ticket](https://www.chilecompra.cl/api/).
- [Guía oficial Compra Ágil v2, mayo de 2026](https://www.chilecompra.cl/wp-content/uploads/2026/05/Documentacion_API_Compra_Agil-2-1.pdf): autenticación, endpoints, campos, filtros y paginación.
- [Ejemplos oficiales](https://www.chilecompra.cl/wp-content/uploads/2026/05/Documentacion_API_Compra_Agil-3-1.pdf).
- [Investigación y limitaciones](INVESTIGACION.md).

Se descargaron y leyeron los documentos oficiales durante esta implementación. No se extrajeron endpoints privados de la aplicación web ni se usó la API de licitaciones como sustituto.

## Obtener el ticket

1. Visita [ChileCompra API](https://www.chilecompra.cl/api/) y pulsa **Pide tu ticket**.
2. Acepta los términos e inicia sesión con **ClaveÚnica**, según la guía oficial.
3. Completa los datos reales y selecciona **Solicitar ticket**. La guía indica que llega automáticamente por correo; revisa spam.
4. Configura el secreto **CHILECOMPRA_TICKET** en los ajustes seguros del entorno, destinado a `api2.mercadopublico.cl`. No lo subas a GitHub, pegues en el chat ni guardes en archivos del repositorio. El servidor lo envía en el encabezado `ticket`, nunca al navegador.
5. Permite el dominio `api2.mercadopublico.cl` en la política de salida y aplica la configuración. El dominio anterior `api.mercadopublico.cl` no sustituye a la API v2.

El borrador del entorno incluye este requisito de secreto y el dominio. Guardar el borrador no inyecta automáticamente la clave ni aplica las reglas al proceso actual.

## Ejecutar

Python 3.12+, sin paquetes externos. Desde un checkout local o el entorno:

```bash
cd /workspace/buscador-pendones
python app.py --host 127.0.0.1 --port 8000
```

La web carga la caché automática sin CSV/JSON manuales. Si falta la clave, muestra **Falta CHILECOMPRA_TICKET** y no fabrica una búsqueda exitosa. Tras configurar o cambiar variables del proceso, reinicia el servidor. El ticket no tiene un campo en la página web.

La base SQLite se crea en `data/compras.sqlite3` (ignorada por Git). Puede cambiarse con `--data-dir`. Necesita almacenamiento persistente. No borres la base para resolver un fallo: conserva cursor y detalles pendientes. No guarda el ticket ni cotizaciones de proveedores.

El servidor de desarrollo escucha solo en loopback. En tu equipo abre el puerto 8000 del servidor local; en una plataforma remota usa su mecanismo autorizado. Para funcionamiento permanente se necesita un despliegue que mantenga el proceso activo, almacenamiento persistente y configuración de producción con HTTPS y control de acceso. Una sesión temporal de Codex no garantiza ejecución 24/7.

## Cómo funciona la revisión automática

- Al arrancar se programa un primer ciclo. Sin clave se detiene el ciclo con un aviso.
- Carga inicial: lista `estado=publicada` sin `q` ni `region`, hasta completar todas las páginas, de hasta 50 registros. Usa un límite superior de publicación fijo para esa carga.
- Obtiene el detalle de **cada compra abierta**, aunque su título no mencione pendones. Busca en `nombre`, `descripcion` y `productos_solicitados[].nombre/descripcion`.
- El parámetro `q` oficial solo está documentado para nombre/descripción; por eso no se usa como prefiltro que pudiera omitir coincidencias exclusivas de los productos.
- Guarda la caché y los detalles pendientes. Las cantidades corresponden a líneas coincidentes, sin sumar unidades distintas; presupuesto y moneda vienen del detalle.
- Después de cada ciclo espera 3.600 segundos. Consulta los cambios desde el cursor persistido con cinco minutos de solapamiento y límite superior fijo. Incluye **todos los estados**, para retirar oportunidades cerradas o canceladas. Si un ciclo tarda, el período entre inicios será mayor a una hora.
- No adelanta el cursor si falla la paginación. Si falla un detalle, queda pendiente para el próximo ciclo y no se muestra su versión anterior como actual.
- Solo muestra compras cuyo detalle figure `publicada` y cuyo cierre con zona horaria sea futuro. Fechas sin zona o no interpretables se excluyen y contabilizan; no se asume una zona no documentada.
- La página refresca la caché cada minuto; abrir varias pestañas no multiplica las consultas a ChileCompra. **Actualizar vista** no fuerza descargas a la API.
- Las consultas son secuenciales. Hay un presupuesto local conservador de 9.000 solicitudes/día UTC por base de datos, no una afirmación de la cuota concedida. HTTP 429 pausa al menos 24 horas y respeta un `Retry-After` numérico mayor. No cambia tickets ni IP para eludir límites.

Un listado sin palabras clave + detalles puede consumir muchas solicitudes. Antes de prometer una carga inicial completa y actualización horaria se debe medir cuántas compras existen y la cuota real. La página general publica 10.000 solicitudes diarias; la guía v2 describe cuotas por tipo de ticket. Hay que confirmar la cuota y condiciones aplicables con ChileCompra si no bastan. No se garantiza que el presupuesto local coincida con el reinicio de cuota del servidor.

## Campos y enlaces

ID: `codigo`; organismo: `institucion.organismo_comprador`; presupuesto: `presupuesto.monto_disponible` o `presupuesto_estimado` con `moneda`; cierre: `fechas.fecha_cierre`; cantidades: `productos_solicitados[].cantidad` y `unidad_medida`.

El enlace apunta al **recurso de detalle de la API oficial documentado**, que requiere ticket. No se ha verificado un enlace de ficha web pública para cada compra: no se inventa uno. Abrir el enlace desde un navegador sin encabezado de autenticación puede devolver un error de acceso.

## Qué falta para funcionar con datos reales

1. Ingresar el ticket oficial y confirmar sus permisos para Compra Ágil v2.
2. Aplicar el acceso de red a `api2.mercadopublico.cl`. La consulta sin ticket desde el entorno obtuvo `Tunnel connection failed: 403 Forbidden` (proxy), no un 401 de la API; eso no prueba que el endpoint esté caído o el ticket sea inválido.
3. Probar listado y detalle autenticados, confirmar el esquema y las zonas horarias, recorrer todas las páginas y medir cuotas/latencia.
4. Completar la carga inicial y comparar compras e ítems con Mercado Público, especialmente una coincidencia presente solo en productos.
5. Desplegar en un servicio continuo con disco persistente; observar al menos dos ciclos reales. Incorporar una reconciliación completa periódica y verificar el comportamiento de la paginación ante cambios concurrentes antes de afirmar cobertura exhaustiva. El cursor incremental por sí solo no demuestra completitud frente a omisiones de la fuente.

Si la API no entrega todos los productos, la búsqueda no puede encontrar palabras solo en los productos omitidos; debe indicarse y solicitarse soporte oficial. Tampoco lee PDFs, imágenes ni adjuntos. Entre ciclos, los estados pueden cambiar. Cero resultados en una sincronización pendiente no significa ausencia de oportunidades en Chile.

## Probar

```bash
cd /workspace/buscador-pendones
python -m unittest discover -s tests -v
node --check static/app.js
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:8000/api/oportunidades
```

Los tests usan fixtures **sintéticas**, no resultados de compras reales. Cubren búsquedas en ítems, paginación nacional sin `q`, sincronización incremental, cancelaciones, detalles pendientes, fechas, falta de ticket y pausa por cuota. No acreditan que la API real ya esté operativa con este entorno.

## Importación opcional

La importación anterior sigue disponible como alternativa manual. No es necesaria para el modo automático. En esta modalidad, se indica una URL oficial de procedencia y se aporta un CSV/JSON, o se descarga una URL directa de datos públicos. La procedencia del archivo es declarada, no certificada.

El JSON debe ser una lista o un objeto con array `compras` o `records`. CSV: UTF-8 con encabezados y separador coma, punto y coma o tabulador. Cada registro debe incluir `id` y `tipo: Compra Ágil`. Campos opcionales: `organismo`, `cantidad`, `presupuesto`, `fecha_cierre`, `enlace`, `items`. Las descripciones e ítems anidados se buscan recursivamente. Este es el contrato del importador, no un esquema oficial atribuido a ChileCompra. No acredita vigencia. Máximo 10 MiB, incluyendo la solicitud JSON que transporta el archivo.
