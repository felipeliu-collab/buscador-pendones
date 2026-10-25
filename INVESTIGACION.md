# Investigación: acceso automático a Compras Ágiles

Revisión documental: 25 de octubre de 2026. Fuentes oficiales consultadas por HTTPS sin desactivar TLS ni eludir controles.

## Hallazgo

ChileCompra publica una API específica **Compra Ágil v2**, presentada en mayo de 2026. La página oficial de API enlaza su guía de uso y ejemplos. Esto permite reemplazar el flujo manual de importación con un cliente autenticado.

| Fuente oficial | Evidencia consultada |
| --- | --- |
| [Página de API](https://www.chilecompra.cl/api/) | En el acceso por `https://api.mercadopublico.cl/` se obtuvo la página oficial de ChileCompra con sección COMPRA ÁGIL, enlaces a PDF, botón de ticket y políticas de uso. HTTP 200. |
| [Guía de uso](https://www.chilecompra.cl/wp-content/uploads/2026/05/Documentacion_API_Compra_Agil-2-1.pdf) | Descargada con HTTP 200 y leída. Base URL, autenticación, listado, detalle, cuotas y referencias de campos. |
| [Ejemplos](https://www.chilecompra.cl/wp-content/uploads/2026/05/Documentacion_API_Compra_Agil-3-1.pdf) | Descargados con HTTP 200 y leídos. |
| [Presentación oficial de la nueva API](https://www.chilecompra.cl/2026/05/chilecompra-presenta-nueva-api-compra-agil-en-feria-de-estado-abierto-2026/) | Consultada, HTTP 200. |
| [Portal de Datos Abiertos](https://datos-abiertos.chilecompra.cl/) | HTTP 200, aplicación JavaScript. No se verificó allí un feed alternativo de oportunidades vigentes con todos sus productos. |

## Endpoints efectivamente documentados

```text
GET https://api2.mercadopublico.cl/v2/compra-agil
GET https://api2.mercadopublico.cl/v2/compra-agil/{codigo}
```

Header obligatorio: `ticket`. No confundir con las URLs v1 para licitaciones y órdenes de compra ni trasladar su autenticación por query string a v2.

La guía documenta `estado=publicada`, `tamano_pagina` (máximo 50), `numero_pagina`, `payload.items`, `payload.paginacion.total_paginas`, `cambio_desde`, `cambio_hasta` y `ttl_cambio_ms`. Una revisión de la última hora puede usar `ttl_cambio_ms=3600000`, pero para no perder períodos de caída es mejor un cursor persistente con rangos absolutos y solapamiento.

El filtro `q` está descrito como búsqueda en **nombre/descripción**. No se afirma que abarque productos. El detalle documenta `productos_solicitados[]` con `nombre`, `descripcion`, `cantidad`, `unidad_medida`. Por ello el cliente enumera compras y consulta sus detalles antes de filtrar localmente. Omite el filtro regional para solicitar cobertura nacional.

Para vigencia se necesita estado `publicada` y `fechas.fecha_cierre` futura. Se deben procesar también los cambios de compras que pasan a canceladas/cerradas y los llamados posteriores. Un feed limitado exclusivamente a publicaciones nuevas no basta.

## Solicitud de credencial

La guía indica: entrar en la página de API, pulsar **Pide tu ticket**, aceptar términos, iniciar sesión con ClaveÚnica, completar datos reales y seleccionar **Solicitar ticket**. Se recibe por correo. El botón de la página consultada enlaza a [Iniciar sesión](https://api.mercadopublico.cl/modules/IniciarSesion.aspx). No se inició sesión ni se solicitó un ticket en nombre del usuario.

Se verificaron nombres de variables del entorno y metadatos de configuración: no había un ticket configurado. Se guardó el requisito `CHILECOMPRA_TICKET`, sin valor, para el destino `api2.mercadopublico.cl`. Nunca se reutilizó el ticket de ejemplo presente en documentación.

## Prueba de acceso y límites de las conclusiones

La consulta de lectura sin credencial al listado documentado devolvió un bloqueo del túnel del proxy: `403 Forbidden`. No es una respuesta del servicio que pruebe un problema de autenticación. Se añadió el nuevo dominio al borrador sin retirar los dominios previos. La actualización del borrador no confirma aplicación de reglas en la máquina actual.

No se obtuvieron registros reales. Por tanto, están **pendientes**: prueba autenticada del ticket, esquema real, interpretación de zonas horarias, completitud y paginación de la carga inicial, cobertura de productos, volumen, cuota, enlaces de ficha pública y ejecución horaria continua. Los tests locales solo validan el comportamiento del cliente frente al esquema documentado.

## Condiciones y cuota

La página general exige mecanismos documentados, datos reales al solicitar ticket, atribución a Dirección ChileCompra y cumplimiento de límites; publica 10.000 solicitudes/día y recomienda horario nocturno para descargas masivas. La guía v2 describe cuotas según tipo de ticket y errores 429. Esta diferencia debe aclararse con soporte si el volumen requerido excede el acceso concedido; no se asume una cuota ilimitada.

Para soporte, la página de API indica el formulario de sugerencias del sitio. Se debe consultar allí sobre permisos v2, cuota, paginación bajo cambios concurrentes y completitud de productos si las pruebas reales muestran límites. No se enviaron mensajes ni formularios al organismo.


## Actualización: prueba autenticada real

El 25 de octubre de 2026, después de la configuración del secreto por el usuario, se verificó su presencia sin mostrar el valor. Internet funcionó (sitio de ChileCompra, HTTP 200). Listado autenticado de Compra Ágil v2 y un detalle devolvieron HTTP 200, `success: OK`, paginación y `productos_solicitados` reales. Esto reemplaza el bloqueo de red anterior como diagnóstico del estado actual.

La prueba inicial con `tamano_pagina=1` recibió HTTP 400 con `tamano_pagina debe estar entre 10 y 50`. Con 10 funcionó; el sincronizador usa 50. El listado indicó aproximadamente 7.000 compras publicadas, un total dinámico que no es una promesa de cobertura ni un conteo de coincidencias.

Se constató que el detalle puede entregar fechas como `2026-10-26 16:00`, sin zona horaria, mientras el listado entrega campos de cierre de llamado con sufijo Z. El adaptador usa el cierre explícito del llamado correspondiente solo cuando coincide con el cierre no cualificado del detalle; si difiere o falta, no adivina la zona y omite la compra con un contador visible.

No se verificó aún una carga nacional completa, dos ciclos horarios ni la restauración del proceso en un despliegue permanente. Los documentos anteriores describen el estado observado en sus fechas; los errores pasados de proxy no significan un bloqueo persistente después de aplicar configuración.

La carga real completó el recorrido inicial de páginas y comenzó la consulta de detalles. Se verificaron coincidencias reales servidas por la aplicación, sin convertirlas en fixtures ni subirlas al repositorio. El conteo de coincidencias y pendientes es dinámico y visible en la aplicación; no se declara carga nacional completa mientras existan detalles pendientes. La vista sin JavaScript `/monitor` permite consultar el estado sin depender de las funciones modernas que Internet Explorer no implementa.

## Vista previa y comprobación desde consola

Se verificó directamente desde Codex que `/`, `/monitor`, `/api/health`, `/api/estado` y `/api/oportunidades` respondían HTTP 200. El servidor original incluía `frame-ancestors 'none'`, que prohíbe incrustación. La política se cambió a `'self'` y se agregó configuración de orígenes HTTPS exactos para un despliegue autorizado. Esto no prueba ni garantiza que la interfaz de vista previa de Codex publique el puerto o permita la incrustación.

Se añadió `diagnostico.py --live`, sin navegador. La prueba real verificó listado y detalles oficiales con HTTP 200 y coincidencias en un título y en ítems de una compra cuyo título no contenía los términos. No se guardan sus respuestas como fixtures. La carga de detalles seguía incompleta; no se declara sincronización nacional terminada. Se preservó la base SQLite y el ticket nunca se imprimió ni subió a GitHub.
