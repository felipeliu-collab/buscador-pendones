const form = document.querySelector('#search');
const resultStatus = document.querySelector('#status');
const table = document.querySelector('#results');
const coverage = document.querySelector('#coverage');
const output = document.querySelector('#output');
form.addEventListener('submit', async event => {
  event.preventDefault();
  const button = document.querySelector('#submit');
  button.disabled = true;
  output.setAttribute('aria-busy', 'true');
  table.hidden = true;
  table.querySelector('tbody').replaceChildren();
  coverage.textContent = '';
  resultStatus.textContent = 'Consultando y buscando en los datos…';
  try {
    const payload = {fuente: document.querySelector('#source').value};
    const file = document.querySelector('#file').files[0];
    if (file) {
      if (file.size > 10 * 1024 * 1024) throw new Error('El archivo supera 10 MiB.');
      payload.contenido = await file.text();
    }
    const response = await fetch(new URL('api/buscar', document.baseURI), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'La consulta falló.');
    resultStatus.textContent = `${data.resultados.length} coincidencias en ${data.registros_leidos} registros. Excluidos por modalidad ausente o distinta de Compra Ágil: ${data.excluidos_por_modalidad}. Coincidencias omitidas por falta de ID: ${data.coincidencias_sin_id}. Consulta: ${new Date(data.consultado_en).toLocaleString('es-CL')}.`;
    coverage.textContent = `${data.cobertura} Fuente: ${data.fuente}`;
    render(data.resultados);
  } catch (error) { resultStatus.textContent = `No se completó la búsqueda: ${error.message}`; }
  finally { button.disabled = false; output.setAttribute('aria-busy', 'false'); }
});

function render(results) {
  table.querySelector('tbody').replaceChildren();
    for (const result of results) {
      const row = document.createElement('tr');
      for (const key of ['id', 'organismo', 'cantidad', 'presupuesto', 'fecha_cierre']) {
        const td = document.createElement('td');
        td.textContent = result[key] ?? 'No informado';
        row.append(td);
      }
      const linkCell = document.createElement('td');
      if (result.enlace) {
        const link = document.createElement('a');
        link.href = result.enlace; link.textContent = result.enlace_requiere_ticket ? 'Detalle API (requiere ticket)' : 'Ver en fuente oficial';
        link.target = '_blank'; link.rel = 'noopener noreferrer'; linkCell.append(link);
      } else linkCell.textContent = 'No informado';
      row.append(linkCell);
      const itemsCell = document.createElement('td');
      const info = document.createElement('p');
      info.textContent = `${result.coincidencias.join(', ')}. ${result.items_disponibles ? 'Hay ítems; completitud no verificada.' : 'Sin ítems: búsqueda parcial.'}`;
      if (result.donde_coincide) info.textContent += ' Encontrado en: ' + result.donde_coincide.join(', ') + '.';
      itemsCell.append(info);
      if (result.titulo) {
        const title = document.createElement('p'); title.textContent = 'Título: ' + result.titulo; itemsCell.append(title);
      }
      if (result.descripcion) {
        const description = document.createElement('p'); description.textContent = 'Descripción: ' + result.descripcion; itemsCell.append(description);
      }
      if (result.items_disponibles) {
        const details = document.createElement('details');
        const summary = document.createElement('summary'); summary.textContent = 'Ver ítems de la fuente';
        const pre = document.createElement('pre'); pre.textContent = JSON.stringify(result.items, null, 2);
        if (result.items_coincidentes && result.items_coincidentes.length) {
          const excerpt = document.createElement('p');
          excerpt.textContent = 'Ítems coincidentes: ' + JSON.stringify(result.items_coincidentes);
          itemsCell.append(excerpt);
        }
        details.append(summary, pre); itemsCell.append(details);
      }
      row.append(itemsCell); table.querySelector('tbody').append(row);
    }
    table.hidden = results.length === 0;
}

let manualMode = false;
let loading = false;
form.addEventListener('submit', () => { manualMode = true; });
async function fetchJSON(path) {
  const response = await fetch(new URL(path, document.baseURI), {signal: AbortSignal.timeout(15000), cache: 'no-store'});
  if (!(response.headers.get('content-type') || '').includes('application/json')) {
    throw new Error(`HTTP ${response.status}: el sitio no devuelve la API JSON del servidor Python. Un alojamiento estático como GitHub Pages no ejecuta la aplicación.`);
  }
  const data = await response.json();
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${data.error || 'consulta fallida'}`);
  return data;
}
function showTime(value) {
  return value ? new Date(value).toLocaleString('es-CL', {timeZone: 'America/Santiago'}) + ' (Chile)' : 'Ninguna registrada';
}
function setText(id, value) { document.getElementById(id).textContent = value; }
async function loadAutomatic() {
  if (loading) return;
  loading = true;
  const autoStatus = document.querySelector('#automatic-status');
  try {
    const state = await fetchJSON('api/estado');
    const sync = state.sincronizacion;
    setText('server-state', state.servidor === 'activo' ? 'Activo · respuesta recibida' : 'No confirmado');
    setText('ticket-state', state.ticket_configurado ? 'Configurado en el proceso (valor oculto)' : 'Ausente en el proceso');
    setText('connection-state', `${sync.conexion || 'Todavía sin respuesta de la API'}${sync.http_status ? ' · HTTP ' + sync.http_status : ''}`);
    setText('last-connection', showTime(sync.ultima_conexion_exitosa));
    setText('last-sync', showTime(sync.ultima_sincronizacion));
    setText('sync-progress', `${sync.estado || 'iniciando'} · trabajador ${state.trabajador_activo ? 'activo' : 'detenido'} · fase ${sync.fase || 'sin iniciar'} · páginas ${sync.paginas_leidas || 0}/${sync.paginas_totales || '?'} · registros listados ${sync.registros_listados || 0} · detalles guardados ${state.detalles_guardados} · pendientes ${state.detalles_pendientes}`);
    setText('next-sync', sync.estado === 'sincronizando' ? 'Al terminar este ciclo se programará el siguiente' : showTime(sync.reintentar_desde || sync.proximo_intento));
    setText('connection-error', sync.error_conexion || sync.error || 'Ninguno registrado');
    const message = `Estado: ${sync.estado || 'iniciando'}. Última sincronización completada: ${showTime(sync.ultima_sincronizacion)}. ${sync.error || ''}`;
    autoStatus.textContent = message;
    autoStatus.dataset.state = sync.error ? 'error' : sync.estado === 'actualizado' ? 'ok' : 'pending';
    const data = await fetchJSON('api/oportunidades');
    if (!manualMode) {
      resultStatus.textContent = `${data.resultados.length} coincidencias en la caché actual. ${data.coincidencias_en_items} con coincidencias en ítems; ${data.coincidencias_items_sin_titulo} de ellas sin mención en el título. ${data.pendientes} detalles pendientes; ${data.sin_items} compras abiertas sin ítems; ${data.fecha_no_interpretable} omitidas por fecha ambigua. ${sync.ultima_sincronizacion ? '' : 'Aún no se ha completado la carga inicial.'} Los resultados son parciales durante la carga y pueden cambiar entre ciclos.`;
      coverage.textContent = data.cobertura;
      render(data.resultados);
    }
  } catch (error) {
    const message = error.name === 'TimeoutError' ? 'El servidor no respondió en 15 segundos.' : error.message;
    autoStatus.textContent = `No se pudo actualizar el estado o los resultados: ${message}`;
    autoStatus.dataset.state = 'error';
    setText('server-state', 'No se pudo completar la consulta; los indicadores previos pueden estar desactualizados');
    if (!manualMode) {
      const retainedRows = table.querySelectorAll('tbody tr').length;
      table.hidden = retainedRows === 0;
      resultStatus.textContent = autoStatus.textContent + (retainedRows ? ` Se conservan ${retainedRows} coincidencias de la última respuesta del servidor; pueden estar desactualizadas.` : ' No hay resultados confirmados disponibles en esta página.');
    }
  } finally { loading = false; }
}
document.querySelector('#refresh').addEventListener('click', () => { manualMode = false; loadAutomatic(); });
loadAutomatic();
// Refresh the cached view; the server, not browser tabs, schedules API traffic.
setInterval(loadAutomatic, 15000);
