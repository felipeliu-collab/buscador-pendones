# Buscador de Pendones

Web en español que integra la **API oficial Compra Ágil v2 de ChileCompra** para buscar pendón, pendones, roller y mini pendón en nombres, descripciones y productos solicitados. Consulta sin filtro regional y muestra compras con estado `publicada` y cierre futuro con zona horaria explícita.

**Listado y detalle autenticados verificados contra la API real el 25 de octubre de 2026 (HTTP 200, `success: OK`). La carga nacional completa y la ejecución horaria continua aún deben completarse y verificarse.** No se incluyen oportunidades ficticias ni datos reales de prueba en el repositorio.

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
- Solo muestra compras cuyo detalle figure `publicada` y cuyo cierre con zona horaria sea futuro. La API real entrega a veces el cierre del detalle sin zona; se usa el campo con zona explícita del llamado correspondiente del listado solo si coinciden exactamente el llamado y los valores de fecha/hora. Si no hay tal coincidencia, se excluye y contabiliza la fecha ambigua. No se asigna una zona supuesta.
- La página refresca el estado y la caché cada 15 segundos; abrir varias pestañas no multiplica las consultas a ChileCompra. **Actualizar vista** no fuerza descargas a la API.
- Las consultas son secuenciales. Hay un presupuesto local conservador de 9.000 solicitudes/día UTC por base de datos, no una afirmación de la cuota concedida. HTTP 429 pausa al menos 24 horas y respeta un `Retry-After` numérico mayor. No cambia tickets ni IP para eludir límites.

Un listado sin palabras clave + detalles puede consumir muchas solicitudes. Antes de prometer una carga inicial completa y actualización horaria se debe medir cuántas compras existen y la cuota real. La página general publica 10.000 solicitudes diarias; la guía v2 describe cuotas por tipo de ticket. Hay que confirmar la cuota y condiciones aplicables con ChileCompra si no bastan. No se garantiza que el presupuesto local coincida con el reinicio de cuota del servidor.

## Campos y enlaces

ID: `codigo`; organismo: `institucion.organismo_comprador`; presupuesto: `presupuesto.monto_disponible` o `presupuesto_estimado` con `moneda`; cierre: `fechas.fecha_cierre`; cantidades: `productos_solicitados[].cantidad` y `unidad_medida`.

El enlace apunta al **recurso de detalle de la API oficial documentado**, que requiere ticket. No se ha verificado un enlace de ficha web pública para cada compra: no se inventa uno. Abrir el enlace desde un navegador sin encabezado de autenticación puede devolver un error de acceso.

## Conexión, diagnóstico y operación

La página muestra servidor, presencia del ticket (sin valor), conexión API y último HTTP, fecha de última conexión exitosa, última sincronización completa, progreso por páginas y detalles, próximo intento y error de diagnóstico. Un error de conexión no se representa como cero oportunidades. Los datos son parciales hasta completar la carga.

`GET /api/estado` informa estado del proceso y del trabajador, contadores y errores de transporte con el ticket redactado. No imprime headers ni respuestas remotas que puedan repetir credenciales. La página no se queda indefinidamente en «Comprobando»: una consulta tarda como máximo 15 segundos antes de mostrar un fallo. Si el alojamiento devuelve HTML en vez de la API JSON, indica que falta el backend. El servidor también incorpora un resumen al HTML para que exista información si JavaScript falla.

**No basta abrir `static/index.html` o publicar los archivos en GitHub Pages.** Hay que acceder a la web servida por `python app.py` o desplegar el backend en un servicio que ejecute Python permanentemente. El secreto configurado en Codex no se transfiere a un alojamiento distinto: debe configurarse allí mediante su gestor seguro. Si no hay proceso escuchando, primero inicia el servidor. Guardar archivos en GitHub no inicia un servicio.

Revisión real del 25 de octubre de 2026: al comenzar no había servidor en el puerto 8000 (`<urlopen error [Errno 111] Connection refused>`). Se inició, se reconoció el ticket existente y se verificaron listado y detalle con HTTP 200 y productos reales. Se conservó la base de datos. El aviso antiguo de ausencia de ticket se limpia al comenzar un nuevo ciclo. No se publica la credencial ni el contenido de las compras como fixtures.

Una prueba inicial de conexión usó una página demasiado pequeña y la API devolvió HTTP 400: `tamano_pagina debe estar entre 10 y 50`. La prueba se corrigió a 10 y respondió HTTP 200. El sincronizador ya utiliza 50. Esta diferencia con el máximo documentado no se ocultó desactivando validaciones.

Pendiente para prometer cobertura exhaustiva y actualización continua: terminar todos los detalles y revisar fechas ambiguas; medir volumen/cuota y dos ciclos reales; desplegar en un servicio permanente con disco persistente; añadir reconciliación completa periódica y comprobar paginación ante cambios concurrentes. Si un ciclo tarda más de una hora, el siguiente se inicia una hora después de terminar. La sesión temporal de Codex no garantiza disponibilidad 24/7.

Si la fuente omite productos o adjuntos, no es posible encontrar términos contenidos solo en ellos. Las fechas y estados pueden cambiar entre ciclos. No hay una ficha web pública verificada: el enlace actual dirige al recurso de detalle de la API y exige ticket.

## Probar

```bash
cd /workspace/buscador-pendones
python -m unittest discover -s tests -v
node --check static/app.js
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:8000/api/estado
curl --fail http://127.0.0.1:8000/api/oportunidades
```

Los tests usan fixtures **sintéticas**, no resultados de compras reales. Cubren búsquedas en ítems, paginación nacional sin `q`, sincronización incremental, cancelaciones, detalles pendientes, fechas, falta de ticket y pausa por cuota. No acreditan que la API real ya esté operativa con este entorno.

## Importación opcional

La importación anterior sigue disponible como alternativa manual. No es necesaria para el modo automático. En esta modalidad, se indica una URL oficial de procedencia y se aporta un CSV/JSON, o se descarga una URL directa de datos públicos. La procedencia del archivo es declarada, no certificada.

El JSON debe ser una lista o un objeto con array `compras` o `records`. CSV: UTF-8 con encabezados y separador coma, punto y coma o tabulador. Cada registro debe incluir `id` y `tipo: Compra Ágil`. Campos opcionales: `organismo`, `cantidad`, `presupuesto`, `fecha_cierre`, `enlace`, `items`. Las descripciones e ítems anidados se buscan recursivamente. Este es el contrato del importador, no un esquema oficial atribuido a ChileCompra. No acredita vigencia. Máximo 10 MiB, incluyendo la solicitud JSON que transporta el archivo.

### Internet Explorer y vista sin JavaScript

La interfaz moderna requiere un navegador con módulos JavaScript, `fetch` y `AbortSignal.timeout`. Internet Explorer no los soporta. Para esos navegadores existe **`/monitor`**, una página generada completamente por Python, sin JavaScript, con conexión, ticket oculto, errores, progreso, fecha de sincronización y resultados reales de la misma caché. Se actualiza cada 30 segundos mediante HTML. La portada enlaza esta vista y el script ES5 `legacy.js` dirige allí a navegadores sin módulos. También funciona con JavaScript desactivado mediante el enlace.

Se comprobó la vista sin JavaScript con Chromium y se verificó el redireccionamiento compatible; no se dispuso de Internet Explorer para una prueba nativa. Ambas vistas necesitan el servidor Python: un alojamiento estático no ejecuta `/monitor` ni el sincronizador.

## Vista previa bloqueada y diagnóstico por consola

El servidor original enviaba `Content-Security-Policy: … frame-ancestors 'none'`, que impide cualquier iframe. Ahora permite `'self'`; un alojamiento que deba incrustarlo desde otro origen HTTPS puede autorizar ese origen exacto mediante `--frame-origin`. No se habilitan todos los dominios ni se quitan las verificaciones TLS. Una política del visor externo aún puede bloquear la aplicación y no se controla desde este repositorio.

La UI de configuración del entorno de Codex no ofrece en este flujo un mecanismo de publicación web soportado. Los HTTP 200 internos no prueban que exista una dirección pública accesible desde tu navegador. No confundir un archivo HTML visible al lado del chat con la página que entrega el servidor Python. Cambiar a `0.0.0.0` por sí solo tampoco crea un dominio público ni configura HTTPS.

La portada ahora genera **todos los estados y las filas de resultados en el servidor**, además de actualizarlos con JavaScript cuando está disponible. Si el navegador bloquea las consultas de actualización, conserva los resultados ya recibidos y avisa que pueden estar desactualizados. Abrir directamente el archivo `static/index.html` sigue sin ejecutar Python y no puede consultar ChileCompra.

Ejecuta desde una terminal de Codex, sin navegador:

```bash
cd /workspace/buscador-pendones
python diagnostico.py --live
```

Comprueba las rutas locales, la política de frames, el trabajador, el secreto presente (nunca su valor), contadores, listado autenticado y hasta dos detalles reales. Informa el error exacto redactando la credencial; devuelve un código distinto de cero si el servidor o la conexión oficial fallan. No inicia servidores ni altera el cursor de sincronización. Las consultas oficiales cuentan para la cuota. No publica archivos con datos reales ni imprime headers de autenticación.

### Usarlo desde el navegador de tu equipo

Instala Python 3.12+ y Git. En una terminal de **tu equipo**, ejecuta:

```bash
git clone https://github.com/felipeliu-collab/buscador-pendones.git
cd buscador-pendones
python app.py --ask-ticket --open-browser
```

Si ya tienes el repositorio, actualízalo con `git pull` dentro de su carpeta en lugar de clonarlo otra vez. El programa pide tu ticket de ChileCompra con entrada oculta, lo conserva solo en memoria y abre automáticamente la vista compatible en el navegador **de tu equipo**. No lo escribas en el comando, en GitHub ni en el chat. Mantén la terminal abierta mientras utilices el buscador. Tu PC debe tener acceso directo autorizado a `api2.mercadopublico.cl`; la configuración secreta de Codex no se transfiere automáticamente al PC.

Si necesitas un sitio accesible permanentemente desde cualquier equipo, el siguiente paso es desplegar Python con almacenamiento persistente, HTTPS y la credencial segura en el hosting elegido. El repositorio preparado no equivale a un despliegue ya publicado. No se ha creado un túnel público ni una URL de vista previa desde esta sesión.

### Si PowerShell no permite pegar el ticket

Actualiza el repositorio con `git pull` y ejecuta `python app.py --ticket-window --open-browser`. Se abre una ventana nativa con campo oculto, botón **Pegar ticket** y botón **Iniciar buscador**. Usa Tcl/Tk, incluido normalmente en el instalador tradicional de Python para Windows. La ventana confirma que se pegó texto sin revelar el ticket; no lo guarda en disco. Cerrar la ventana cancela el inicio. Esta interfaz gráfica no se verificó en Windows desde Codex; las 22 pruebas existentes del servidor y sincronizador siguen pasando.

### Error `No time zone found with key America/Santiago` en Windows

La página usa UTC con una etiqueta explícita si Windows no dispone de la base de zonas IANA; no debería quedar en blanco. Para mostrar la hora chilena, se puede instalar opcionalmente la base oficial para Python con `python -m pip install tzdata` y reiniciar el buscador. Se verifican ambas páginas mediante una prueba que simula la ausencia de esos datos.
