const form = document.querySelector('#search');
const status = document.querySelector('#status');
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
  status.textContent = 'Consultando y buscando en los datos…';
  try {
    const payload = {fuente: document.querySelector('#source').value};
    const file = document.querySelector('#file').files[0];
    if (file) {
      if (file.size > 10 * 1024 * 1024) throw new Error('El archivo supera 10 MiB.');
      payload.contenido = await file.text();
    }
    const response = await fetch('/api/buscar', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'La consulta falló.');
    status.textContent = `${data.resultados.length} coincidencias en ${data.registros_leidos} registros. Excluidos por modalidad ausente o distinta de Compra Ágil: ${data.excluidos_por_modalidad}. Coincidencias omitidas por falta de ID: ${data.coincidencias_sin_id}. Consulta: ${new Date(data.consultado_en).toLocaleString('es-CL')}.`;
    coverage.textContent = `${data.cobertura} Fuente: ${data.fuente}`;
    render(data.resultados);
  } catch (error) { status.textContent = `No se completó la búsqueda: ${error.message}`; }
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
      itemsCell.append(info);
      if (result.items_disponibles) {
        const details = document.createElement('details');
        const summary = document.createElement('summary'); summary.textContent = 'Ver ítems de la fuente';
        const pre = document.createElement('pre'); pre.textContent = JSON.stringify(result.items, null, 2);
        details.append(summary, pre); itemsCell.append(details);
      }
      row.append(itemsCell); table.querySelector('tbody').append(row);
    }
    table.hidden = results.length === 0;
}

let manualMode = false;
let loading = false;
form.addEventListener('submit', () => { manualMode = true; });
async function loadAutomatic() {
  if (loading) return;
  loading = true;
  const autoStatus = document.querySelector('#automatic-status');
  try {
    const response = await fetch('/api/oportunidades');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Consulta fallida');
    const sync = data.sincronizacion;
    const last = sync.ultima_sincronizacion ? new Date(sync.ultima_sincronizacion).toLocaleString('es-CL') : 'ninguna completada';
    const message = `Estado: ${sync.estado || 'iniciando'}. Última sincronización completada: ${last}. Detalles pendientes: ${data.pendientes}. ${sync.error || ''}`;
    autoStatus.textContent = message;
    if (!manualMode) {
      status.textContent = `${data.resultados.length} coincidencias vigentes según la fuente. ${message} Compras abiertas sin ítems: ${data.sin_items}. Omitidas por fecha sin zona horaria o no interpretable: ${data.fecha_no_interpretable}. Si la sincronización no está completa o actualizada, los resultados son parciales o pueden estar desactualizados.`;
      coverage.textContent = data.cobertura;
      render(data.resultados);
    }
  } catch (error) {
    autoStatus.textContent = `No se pudo comprobar el monitoreo: ${error.message}`;
    if (!manualMode) { table.hidden = true; status.textContent = autoStatus.textContent; }
  } finally { loading = false; }
}
document.querySelector('#refresh').addEventListener('click', () => { manualMode = false; loadAutomatic(); });
loadAutomatic();
// Refresh the cached view; the server, not browser tabs, schedules API traffic.
setInterval(loadAutomatic, 60000);
