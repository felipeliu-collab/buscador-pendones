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
    for (const result of data.resultados) {
      const row = document.createElement('tr');
      for (const key of ['id', 'organismo', 'cantidad', 'presupuesto', 'fecha_cierre']) {
        const td = document.createElement('td');
        td.textContent = result[key] ?? 'No informado';
        row.append(td);
      }
      const linkCell = document.createElement('td');
      if (result.enlace) {
        const link = document.createElement('a');
        link.href = result.enlace; link.textContent = 'Ver en fuente oficial';
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
    table.hidden = data.resultados.length === 0;
  } catch (error) { status.textContent = `No se completó la búsqueda: ${error.message}`; }
  finally { button.disabled = false; output.setAttribute('aria-busy', 'false'); }
});
