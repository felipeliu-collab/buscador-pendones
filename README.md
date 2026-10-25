# Buscador de Pendones

Web en español para buscar **pendón, pendones, roller y mini pendón** (sin distinguir mayúsculas ni acentos) dentro de registros de Compras Ágiles, incluidas las descripciones y los ítems anidados que contenga el archivo consultado. Muestra ID, organismo, cantidad, presupuesto, cierre y enlace oficial, cuando esos campos están disponibles.

**Estado: herramienta de búsqueda sobre importaciones oficiales; no es todavía un rastreador nacional automático.** No hay resultados precargados. No se ha verificado una fuente oficial que permita enumerar todas las Compras Ágiles y consultar todos sus ítems. No se promete cobertura nacional completa ni oportunidades vigentes. No se usa la API de licitaciones como sustituto de Compras Ágiles.

## Ejecutar

Requiere Python 3.12 o superior. No necesita paquetes, claves, base de datos ni servicios externos para importar archivos.

```bash
cd /workspace/buscador-pendones
python app.py --host 127.0.0.1 --port 8000
```

En tu equipo, abre el navegador en el puerto 8000 del servidor local. En un entorno remoto usa únicamente el mecanismo de acceso autorizado por tu plataforma. La configuración predeterminada escucha solo en loopback. No exponer públicamente este servidor de desarrollo sin autenticación, límites de solicitudes y un servidor de producción.

## Obtener y buscar datos

1. Obtén una exportación mediante mecanismos autorizados de [Datos Abiertos de ChileCompra](https://datos-abiertos.chilecompra.cl/) o [Mercado Público](https://www.mercadopublico.cl/). Respeta sus condiciones y permisos. Estos enlaces son portales de referencia, no endpoints de descarga verificados.
2. En la web, introduce la URL oficial de procedencia y selecciona el CSV o JSON. La procedencia del archivo es declarada por el usuario: la aplicación no certifica su autenticidad.
3. Si dispones de una URL oficial directa a un CSV o JSON público, puedes omitir el archivo. Se hará una única descarga HTTPS, sin navegar páginas, seguir redirecciones, sortear CAPTCHA ni intentar autenticación. No hay sondeo periódico, paginación ni descubrimiento automático de endpoints.
4. Pulsa **Buscar pendones**. Se recorren todos los valores del registro, incluidos ítems anidados; no se aplica filtro regional. El alcance depende del archivo, no acredita que estén representadas todas las regiones.

Dominios admitidos exactamente: `www.mercadopublico.cl`, `api.mercadopublico.cl`, `datos-abiertos.chilecompra.cl`, `www.chilecompra.cl`. No se admiten URLs con credenciales. TLS permanece verificado. Las políticas de red del entorno pueden impedir la descarga. No se almacenan los datos importados en disco.

### Formato de importación

El adaptador admite un array JSON o un objeto con `compras` o `records` como array; CSV UTF-8 con coma, punto y coma o tabulador y encabezados. **Este es el contrato de esta aplicación, no un esquema oficial afirmado de ChileCompra.** Si una exportación tiene otra estructura, debe prepararse un adaptador específico a partir de su documentación y una muestra autorizada; no se atribuyen equivalencias sin verificar.

| Campo | Uso |
| --- | --- |
| `id` | Obligatorio para mostrar una coincidencia; alias `codigo`, `codigo_compra`, `CodigoExterno` |
| `tipo` | Obligatorio: `Compra Ágil` o `Compras Ágiles`; alias `modalidad`, `tipo_compra` |
| `organismo` | Alias `comprador`, `institucion` |
| `cantidad` | Valor total explícito de la fuente; no se suman unidades distintas de los ítems |
| `presupuesto` | Alias `monto_estimado`; se muestra sin inferir moneda ni impuestos |
| `fecha_cierre` | Alias `FechaCierre`; se conserva fecha y zona horaria de la fuente sin inferirlas |
| `enlace` | Alias `url`, `link`; solo HTTPS de dominios oficiales admitidos |
| `items` | Array u objeto con las descripciones y cantidades; alias `productos` |
| Otros campos | También se buscan sus valores textuales, en cualquier profundidad |

Los registros sin modalidad explícita o de otra modalidad se excluyen y contabilizan. Las coincidencias sin ID se contabilizan pero no se muestran como compras identificadas. Los campos ausentes aparecen como **No informado**; jamás se reconstruyen montos, fechas o enlaces a partir del ID. Las filas no se deduplican: un CSV con una fila por ítem puede mostrar el mismo ID varias veces. No hay ordenamiento temporal ni filtro de cierre porque no se asume un formato o zona horaria uniforme.

### Límites de cobertura

- Si la fuente incluye solo títulos o encabezados, **no se pueden encontrar menciones que estén únicamente en ítems omitidos**. La interfaz señala registros sin ítems. La presencia de algunos ítems tampoco acredita que estén todos.
- No se leen adjuntos PDF, imágenes, OCR ni páginas HTML.
- Un error de acceso devuelve un error visible, no una lista vacía que aparente una búsqueda exitosa.
- Cero coincidencias significa cero en los campos importados, no ausencia de compras en Chile.
- Límite de solicitud/descarga: 10 MiB (el JSON que transporta un archivo también cuenta). Divide exportaciones mayores por mecanismos oficiales.
- Para completar el objetivo nacional automático falta identificar y verificar una fuente oficial autorizada con enumeración, paginación y detalle de ítems, sus condiciones, credenciales si corresponden y cobertura. No solicitar claves en chat; usar configuración segura cuando exista un requisito comprobado.

## Probar

```bash
cd /workspace/buscador-pendones
python -m unittest discover -s tests -v
node --check static/app.js
```

Las pruebas usan datos **sintéticos**, identificados como `PRUEBA`, solo en memoria: no son oportunidades reales ni aparecen al abrir la web. Verifican búsquedas en ítems anidados, acentos, modalidad, campos ausentes, CSV, enlaces no oficiales, resolución privada y respuestas HTTP. No certifican acceso a una fuente nacional. El test HTTP inicia y cierra su propio servidor en un puerto libre.

Comprobación del servidor iniciado:

```bash
curl --fail http://127.0.0.1:8000/api/health
```

Debe indicar `estado: ok` y `cobertura_nacional_verificada: false`. Para probar con datos reales, importa una exportación oficial autorizada y compara una compra y sus ítems con la fuente. Esta comparación no fue realizada durante la creación: los portales oficiales devolvieron bloqueo de red 403 desde el entorno.

## Archivos

`app.py`: servidor y adaptador sin dependencias externas. `static/`: interfaz accesible en español y renderizado de texto sin HTML de los datos. `tests/`: pruebas del buscador y HTTP. No se requiere compilación. El servidor no persiste archivos, tokens ni resultados.
