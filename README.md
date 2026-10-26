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

### Coincidencias dentro de ítems y carga parcial

La web muestra cuántas coincidencias provienen de ítems y cuántas no mencionan el término en el título. Cada resultado señala dónde se encontró y muestra los ítems coincidentes. La búsqueda incluye `productos_solicitados[].nombre` y `.descripcion` incluso si título y descripción general no contienen los términos; no usa `q` para descartar compras antes de consultar sus productos. Una prueba específica verifica ese recorrido completo.

Los detalles nunca descargados se revisan por orden persistente de descubrimiento, sin favorecer títulos que contengan palabras clave. Al retomar una carga incompleta, se revisan hasta 50 detalles pendientes antes de consultar nuevas páginas de cambios; después se continúa con la cola restante. Los detalles ya existentes que requieren actualización van después de los nunca descargados. Los reinicios conservan la cola y las compras nuevas con títulos coincidentes no saltan por delante de los ítems pendientes más antiguos. El contador de pendientes debe llegar a cero y la sincronización completarse antes de evaluar la búsqueda completa, dentro de los límites de cobertura documentados.

Una desconexión del navegador durante el envío de HTML (`ConnectionResetError`, incluido WinError 10054) se maneja cerrando esa respuesta; no se imprime un traceback por ese cierre ni se detiene el trabajador de ChileCompra. Los otros errores de servidor no se silencian.

## Descargar Excel

El botón **Descargar Excel**, disponible sobre los resultados en ambas vistas y compatible sin JavaScript, descarga `pendones.xlsx`. Incluye **Compras** (ID, título, organismo, cantidades, presupuesto, cierre, enlace y términos), **Items** (productos de las compras exportadas con indicador de coincidencia) y **Estado** (fuente, fecha UTC de exportación, última sincronización, pendientes y advertencia de carga parcial). Se exporta la caché automática disponible al descargar; no incluye búsquedas manuales ni completa registros pendientes. Descargar no consume consultas oficiales, no incluye el ticket y no requiere instalar paquetes. Las celdas se guardan como texto para evitar ejecutar fórmulas procedentes de datos. Los textos mayores a 32.767 caracteres se recortan por el límite de Excel.

La hoja **Compras** también incluye una columna **Ítems** con nombre, descripción, cantidad y unidad de todos los productos disponibles, un producto por línea dentro de la celda. La hoja **Items** conserva el detalle por filas.

## Abrir con doble clic en Windows

Después de actualizar el repositorio con `git pull`, abre la carpeta en el Explorador y haz doble clic en **Crear acceso directo.vbs**. Crea **Buscador de Pendones** en tu escritorio, usando la ubicación de Escritorio configurada en Windows. Si ya existe un acceso con ese nombre, pregunta antes de reemplazarlo. No necesita permisos de administrador, no copia el ticket ni modifica el inicio de Windows.

Luego abre **Buscador de Pendones** desde el escritorio. Si el servidor ya responde como Buscador de Pendones en el puerto 8000, abre su página. Si no responde, inicia el programa y su ventana para pegar el ticket. También puedes abrir directamente **Iniciar buscador.bat** desde la carpeta del proyecto. La ventana de consola permanece abierta durante la ejecución: ciérrala cuando quieras detener el buscador. No se trata de un servicio permanente ni se evita la cuota de la API. Si Windows administra o bloquea scripts VBS, usa el archivo BAT; no es necesario desactivar protecciones del sistema. El lanzador Python se probó con casos de servidor presente y ausente; no se ejecutó la creación nativa del acceso directo de Windows desde Codex.


### Corrección de revisión de compras sin palabras clave en el título

Se eliminó la prioridad anterior basada en el título: con una cuota reducida podía retrasar las oportunidades que contienen «pendón» solo en un producto. Se verificó el recorrido listado → detalle sin término en el título → coincidencia exclusiva en la descripción de un ítem → fila en Excel. Las pruebas también comprueban reanudación antes de nuevas páginas, conservación del cursor ante error y orden de la cola al reiniciar.

Actualizar el programa no descarga de inmediato los detalles que faltan. Si la API responde 429, se mantiene la pausa y la cola se retoma cuando corresponde; no se evade la cuota ni se garantiza cobertura completa con un acceso insuficiente.

## Buscar en título O descripción O ítems

La condición es inclusiva: basta una coincidencia en cualquiera de los tres campos descargados para que una compra publicada con cierre futuro interpretable aparezca en resultados. Cada compra incluye **Encontrado en: Título, Descripción, Ítems** según corresponda, además de la descripción general y los productos. El Excel agrega **Descripción de la compra** y **Encontrado en**. Se comprueban los tres casos por separado, sin requerir que el título contenga la palabra ni asumir coincidencias por rubro.

No se ha verificado ni reproducido la cobertura o el funcionamiento interno de Licilab. Esta implementación usa la API oficial autorizada y los límites ya documentados. Una cola pendiente o una pausa HTTP 429 impiden presentar el conjunto como completo, aunque la condición de búsqueda local sea correcta.

## Avisos en la pantalla del computador

En Windows, el programa abre automáticamente el panel **Avisos en pantalla** al iniciarse (también desde el acceso directo). Permite activar o silenciar avisos, abrir las compras y ver el historial. Cuando se detectan coincidencias no vistas antes, una ventana agrupa los nuevos IDs y títulos; no abre una ventana por cada compra. Minimizar el panel mantiene el programa activo. Cerrar su ventana principal pide confirmación y detiene el servidor y los avisos. El historial está en **Avisos de nuevas coincidencias**, enlazado en ambas vistas.

La primera revisión establece una referencia silenciosa con las coincidencias ya disponibles. Después se avisa de **nuevas detecciones**, incluso si provienen de ítems que acaban de descargarse de compras antiguas. No se afirma que se hayan publicado en ese momento. Cada ID se avisa una sola vez; IDs conocidos, historial y silencio se conservan en la misma base SQLite al reiniciar. Silenciar conserva el historial y los avisos pendientes pueden agruparse al reactivar. Las compras pueden cerrar o cambiar después del aviso: comprueba vigencia y requisitos antes de ofertar.

El detector revisa la caché cada minuto; no hace consultas adicionales a ChileCompra ni envía emails. La sincronización oficial conserva su frecuencia, cola pendiente y pausa por 429. Si faltan datos o hay cuota agotada, la detección será parcial o tardía; no se asegura cobertura completa ni entrega inmediata. El programa y el computador deben permanecer funcionando. Los avisos no llegan desde este chat.

La ventana usa Tcl/Tk, igual que el ingreso gráfico del ticket. Se puede forzar con `--desktop-alerts` o ejecutar sin ella con `--no-desktop-alerts`; en sistemas sin escritorio se conserva el historial web. Se probaron la detección de coincidencias exclusivas de ítems, la referencia inicial, deduplicación entre reinicios, silencio persistente, exclusión de compras cerradas y estado de cuota. No se dispuso de Windows gráfico en Codex para verificar la ventana nativa; esa presentación debe confirmarse en el PC.

## Compras Ágiles menores a $100.000 CLP

El botón **Compras Ágiles menores a $100.000** aparece en ambas vistas y en el panel de Windows. Abre `/menores-100000`, un buscador de cualquier producto o servicio con **presupuesto total informado estrictamente menor a 100.000 pesos chilenos**. No aplica palabras clave de pendones. Las compras de exactamente $100.000 quedan fuera. Dispone de su propio botón Excel, servido por `/menores-100000.xlsx`, y de la consulta local `/api/menores-100000`.

Usa los registros oficiales ya descargados, incluso cuando los ítems estén pendientes, si permiten comprobar monto, estado `publicada` y cierre futuro con zona horaria explícita. Prioriza el detalle actualizado cuando existe; si está pendiente de renovar, utiliza el listado más reciente. No reutiliza un presupuesto antiguo de detalle para una compra modificada. Acepta `monto_disponible_clp` normalizado por la fuente; si falta, requiere moneda CLP y `monto_disponible` o `presupuesto_estimado`. No supone que USD u otra moneda sean pesos ni calcula conversiones, impuestos o precio por unidad. Un cero se muestra únicamente si la fuente lo informa: debe confirmarse antes de ofertar.

Los montos ausentes, negativos, no finitos o no interpretables y las fechas ambiguas se excluyen. La vista se actualiza cada 30 segundos desde la caché, sin nuevas llamadas a ChileCompra. Comparte el estado de sincronización y sus límites de cuota: no acredita cobertura nacional completa ni actualidad si la fuente está pausada. Los avisos de escritorio existentes siguen correspondiendo a coincidencias de pendones; esta vista no agrega avisos de presupuesto automáticamente.

## Botón: segundo llamado bajo $500.000

El botón **Segundo llamado · Menos de $500.000** está en la portada, la vista compatible y el panel de Windows. Abre `/segundo-llamado-500000`; permite descargar `/segundo-llamado-500000.xlsx` y consultar `/api/segundo-llamado-500000`. Exige presupuesto total informado menor a $500.000 CLP, llamado actual explícito 2, estado publicado y cierre futuro interpretable. No basta tener una fecha de segundo llamado programada. Utiliza la misma caché parcial y sus advertencias; no hace solicitudes nuevas a la API ni agrega automáticamente avisos de escritorio para este filtro. El botón pertenece al programa, no a la sección Recientes de ChatGPT/Codex.

## Botón Pin o pines

El botón **Pin o pines** está en la portada, la vista compatible y el panel de Windows. Abre `/pines`, con descarga `/pines.xlsx` (`pin_o_pines.xlsx`) y consulta local `/api/pines`. Busca palabras completas **pin** o **pines**, sin distinguir mayúsculas o tildes, en título O descripción O nombre/descripción de productos solicitados. No incluye por subcadena palabras como pintura, pincel o pinzas. La coincidencia es textual y puede tener distintos significados: revisa el contexto antes de ofertar.

Comparte la caché oficial y sus límites; no consulta nuevamente la API al abrir la vista o descargar y no representa todas las compras mientras falten detalles. El Excel indica el filtro y dónde se encontró cada coincidencia. Los avisos actuales de escritorio siguen correspondiendo a pendones; no se agregan avisos de pines automáticamente.

## Botón Banderas vela

El botón **Banderas vela** está en la portada, la vista compatible y el panel de Windows. Abre `/banderas-vela`, con descarga `/banderas-vela.xlsx` (`banderas_vela.xlsx`) y consulta `/api/banderas-vela`. Busca expresiones como **bandera vela**, **banderas velas**, **banderas tipo vela** y **bandera publicitaria tipo vela**, incluyendo nombres y descripciones de un mismo ítem. La palabra vela aislada no basta; se evitan así coincidencias genéricas de velas de cera. Tampoco se forman frases juntando títulos con descripciones o productos distintos.

Comparte los datos oficiales ya guardados y sus límites de cobertura. No se añaden consultas ni avisos de escritorio por este filtro. El Excel indica dónde se encontró la expresión y si la carga está incompleta.

## Búsqueda de difusión en Windows

Actualiza el repositorio con `git pull` y abre **Iniciar buscador.bat** (o el acceso directo existente). En la ventana protegida pega tu ticket y pulsa **Iniciar buscador**. En el navegador elige **Difusión**. También está disponible en el panel de escritorio.

- **Descargar Excel** exporta ID, institución, región informada, título, descripción, todos los ítems disponibles, cantidades por ítem, presupuesto, cierre, campos coincidentes y enlaces. Las filas que vencen en 24 horas se resaltan en amarillo. No suma unidades incompatibles.
- **Actualizar búsqueda desde ChileCompra** despierta el único trabajador compartido; no crea sincronizaciones simultáneas. Respeta el bloqueo por HTTP 429 y las cuotas. Recargar la página no fuerza llamadas a la API.
- **Activar / Desactivar repetición cada hora** controla el trabajador compartido de todas las búsquedas. Está activada inicialmente; la elección se conserva en SQLite. Un ciclo puede tardar más de una hora si hay muchos detalles. El programa debe permanecer abierto y tener conexión a Internet. La primera sincronización al iniciar se ejecuta incluso si la repetición está desactivada.
- Coincide la palabra completa `difusión` o `difusion`, sin distinguir mayúsculas o tildes, en título **o** descripción general **o** ítems. El ID es único, se excluyen estados distintos de publicada y cierres pasados o ambiguos; orden ascendente por fecha. La vigencia es la de la última respuesta recibida, no una garantía de ausencia de cancelaciones posteriores.
- **Límite pendiente: documentos públicos.** Este adaptador no enumera ni descarga adjuntos. No se ha verificado una API documentada que proporcione todos los documentos públicos de las solicitudes vigentes. La pantalla y el Excel indican **NO REVISADOS**; las coincidencias exclusivas en adjuntos pueden faltar. No se usan adjuntos privados, rutas inventadas ni evasión de restricciones.
- El enlace directo al portal solo se incluye si la fuente lo entrega como URL HTTPS de Mercado Público sin credenciales ni parámetros. En caso contrario se informa que no está disponible y se entrega el recurso API oficial, que requiere ticket. Busca el ID en Mercado Público para ofertar; no se fabrica una URL de oferta.

El ticket se solicita en https://www.chilecompra.cl/api/ mediante **Pide tu ticket**, ClaveÚnica y el formulario oficial. Nunca pegues el ticket al final del comando ni lo compartas en capturas. No se guarda en el Excel.

Pruebas: `python -m unittest discover -s tests -q`. Incluyen coincidencias exclusivas de ítems, exclusión de cerradas/canceladas/detalles pendientes, fechas, orden, resaltado XLSX y respeto del bloqueo de cuota al actualizar manualmente. Las pruebas usan datos sintéticos; la aplicación no los muestra. No se ha probado la ventana nativa en un equipo Windows desde este entorno.
