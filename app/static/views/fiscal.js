import { $, esc, state, api, heading, field, modal, toast, render, cash, date, navigate } from '../core.js';

const accepted = d => d.status.toLowerCase() === 'aceptado';
const rejected = d => ['rechazado','error','por_verificar'].includes(d.status.toLowerCase());
const summary = d => { try { return JSON.parse(d.response || '{}'); } catch { return {}; } };

export async function fiscal() {
  if (state.me.user.role !== 'admin') {
    $('#main').innerHTML = heading('Emisión electrónica','Acceso del administrador','Solicita al administrador de tu negocio la emisión de los documentos.');
    return;
  }
  $('#main').innerHTML = heading('Emisión electrónica','Preparando tu espacio','Consultando la conexión con el proveedor…') + '<div class="fiscal-skeleton" aria-label="Cargando emisor"><div></div><div></div><div></div></div>';
  const p = await api('/fiscal/profile');
  if (state.page !== 'fiscal') return;
  const c = p.company;
  const [series, docs] = p.linked ? await Promise.all([api('/fiscal/series'),api('/fiscal/documents')]) : [[],[]];
  if (state.page !== 'fiscal') return;
  const sales = state.sales.filter(s => s.status === 'registrado');
  const isBeta = c.entorno !== 'produccion';
  $('#main').innerHTML = heading('COMPROBANTES Y TRASLADOS', 'Emisión electrónica', 'De la venta al documento. Todo en un mismo lugar.', '<button class="btn ghost" id="reload-fiscal">↻ Actualizar</button>') +
    `<section class="emitter-strip"><div class="emitter-identity"><span class="emitter-monogram">${esc(c.razon_social?.slice(0,1) || 'F')}</span><div><span class="eyebrow">TU EMISOR</span><h2>${esc(c.razon_social)}</h2><p>RUC ${esc(c.ruc)} <span>·</span> Kodevo / SUNAT</p></div></div><div class="emitter-state"><span class="connection-dot"></span><div><b>Proveedor conectado</b><small>${c.tiene_certificado ? 'Certificado disponible' : 'Certificado pendiente'}</small></div><span class="environment-tag ${isBeta?'test':''}">${esc(c.entorno || 'Sin confirmar')}</span></div></section>
    ${isBeta ? '<div class="environment-notice"><span class="notice-symbol">i</span><p><b>Estás en el entorno de pruebas.</b> Puedes validar el flujo con el proveedor. Los documentos beta no tienen validez tributaria.</p></div>' : '<div class="environment-notice"><span class="notice-symbol">i</span><p><b>Entorno de producción.</b> Revisa cliente, importes y traslado antes de emitir.</p></div>'}
    <div class="fiscal-metrics"><div><span>Documentos emitidos</span><strong>${docs.filter(d=>d.remote_id).length}</strong><small>Desde Factora</small></div><div><span>Aceptados</span><strong>${docs.filter(accepted).length}<i class="metric-dot ok"></i></strong><small>Estado del proveedor</small></div><div><span>En seguimiento</span><strong>${docs.filter(d=>!accepted(d)&&!rejected(d)).length}<i class="metric-dot wait"></i></strong><small>Pendientes de confirmación</small></div><div><span>Por revisar</span><strong>${docs.filter(rejected).length}<i class="metric-dot review"></i></strong><small>Requieren tu atención</small></div></div>
    ${!p.linked ? `<section class="connect-panel"><span class="step-number">01</span><div><h2>Conecta tu negocio con el emisor</h2><p>Vincularemos este espacio con ${esc(c.razon_social)} e importaremos su razón social, RUC y dirección. Tus ventas e inventario se conservan.</p></div><button class="btn primary" id="connect-fiscal">Vincular negocio →</button></section>` : `<div class="issue-layout"><section class="panel issue-panel"><div class="section-label"><span class="step-number">01</span><div><h2>Prepara tu documento</h2><p>Selecciona una venta registrada para empezar.</p></div></div>${sales.length ? `<label>Venta de origen<select id="fiscal-sale">${sales.map(s => `<option value="${s.id}">${esc(s.number)} · ${esc(JSON.parse(s.customer_snapshot).name)}</option>`).join('')}</select></label><div id="sale-preview" class="sale-preview"></div><div class="document-actions"><button class="document-choice" id="issue-boleta"><span class="document-glyph">B</span><span><b>Boleta electrónica</b><small>Emite el comprobante de tu venta</small></span><span class="choice-arrow">↗</span></button><button class="document-choice" id="issue-guia"><span class="document-glyph">G</span><span><b>Guía de remisión</b><small>Prepara el traslado de tus productos</small></span><span class="choice-arrow">↗</span></button></div>` : '<div class="fiscal-empty"><span class="document-glyph">+</span><h3>Primero, registra una venta</h3><p>Tu inventario y los datos del cliente se usarán para preparar el documento.</p><a class="btn primary" href="#pos">Crear mi primera venta →</a></div>'}</section><aside class="issue-guide"><span class="eyebrow">ANTES DE EMITIR</span><h2>Cada dato, en su lugar.</h2><ol><li><b>Revisa la venta</b><p>Productos, cantidades y cliente se toman de la operación registrada.</p></li><li><b>Completa el documento</b><p>Elige la serie. Para guías, añade ruta, peso y datos del transporte.</p></li><li><b>Consulta el resultado</b><p>Revisa la respuesta del proveedor y descarga tus archivos.</p></li></ol><div class="guide-note">La guía utiliza el stock de la venta. No vuelve a descontar productos.</div></aside></div>`}
    <section class="panel fiscal-history"><div class="panel-heading"><div><h2>Documentos electrónicos</h2><p>El estado y los archivos de cada emisión.</p></div><span class="count">${docs.length} registros</span></div><div class="fiscal-toolbar"><div class="history-tabs" role="group" aria-label="Tipo de documento"><button class="selected" data-kind="">Todos</button><button data-kind="boleta">Boletas</button><button data-kind="guia">Guías</button></div><input id="fiscal-search" type="search" placeholder="Buscar venta, número o estado…" aria-label="Buscar documento"></div><div id="fiscal-rows"></div></section>`;
  $('#reload-fiscal').onclick=()=>render();
  if (!p.linked) $('#connect-fiscal').onclick = () => modal('Vincular emisor', `<p>Vincular ${esc(c.razon_social)} (${esc(c.ruc)}) e importar sus datos comerciales a este negocio.</p>`, async () => {
    await api('/fiscal/connect','POST',{}); state.me = await api('/me'); await render();
  }, 'Vincular negocio');
  let filter='';
  function drawDocuments() {
    const q=$('#fiscal-search').value.toLowerCase();
    const list=docs.filter(d=>(!filter || d.kind===filter) && (JSON.stringify([d.sale_id,summary(d).numero_completo,d.status])).toLowerCase().includes(q));
    $('#fiscal-rows').innerHTML = list.length ? `<div class="table-wrap"><table><thead><tr><th>Documento</th><th>Fecha de emisión</th><th>Venta de origen</th><th>Estado</th><th>Archivos</th></tr></thead><tbody>${list.map(d=> {
      const remote=summary(d), sale=sales.find(s=>s.id===d.sale_id);
      return `<tr><td><div class="document-cell"><span class="document-glyph small">${d.kind==='boleta'?'B':'G'}</span><div><b>${esc(remote.numero_completo || (d.kind==='boleta'?'Boleta':'Guía'))}</b><small>${d.remote_id?'ID '+esc(d.remote_id):'Pendiente de verificación'}</small></div></div></td><td>${date(d.created_at)}</td><td>${esc(sale?.number || d.sale_id)}</td><td><span class="fiscal-status ${accepted(d)?'ok':rejected(d)?'review':'wait'}">${esc(d.status.replaceAll('_',' ').toLowerCase())}</span>${remote.sunat?.descripcion?`<small class="sunat-message">${esc(remote.sunat.descripcion)}</small>`:''}</td><td><div class="file-actions">${d.remote_id ? `<button class="text-link" data-refresh="${d.id}">Consultar</button><a href="/api/fiscal/documents/${d.id}/pdf">PDF</a><a href="/api/fiscal/documents/${d.id}/xml">XML</a>${d.kind==='boleta'?`<a href="/api/fiscal/documents/${d.id}/cdr">CDR</a><a href="/api/fiscal/documents/${d.id}/ticket">Ticket</a>`:''}` : `<button class="text-link" data-reconcile="${d.id}">Verificar ID</button>`}</div></td></tr>`;
    }).join('')}</tbody></table></div>` : `<div class="fiscal-empty"><span class="empty-document">▤</span><h3>${docs.length?'No encontramos coincidencias':'Tus documentos aparecerán aquí'}</h3><p>${docs.length?'Prueba con otra búsqueda o tipo de documento.':'Prepara tu primera boleta o guía. Aquí podrás seguir su estado y descargar los archivos.'}</p></div>`;
    document.querySelectorAll('[data-refresh]').forEach(b=>b.onclick=async()=>{
      b.disabled=true; b.textContent='Consultando…';
      try { await api(`/fiscal/documents/${b.dataset.refresh}/refresh`,'POST',{}); toast('Estado actualizado'); await render(); }
      catch(e) {toast(e.message,true); b.disabled=false; b.textContent='Consultar';}
    });
    document.querySelectorAll('[data-reconcile]').forEach(b=>b.onclick=()=>modal('Verificar emisión pendiente','<p>Si el proveedor creó el documento, ingresa su ID. Verificaremos la serie y referencia de venta sin emitir otro documento.</p>'+field('ID del proveedor','remote_id','','number','required min="1" step="1"'),async d=>{
      await api(`/fiscal/documents/${b.dataset.reconcile}/reconcile`,'POST',{remote_id:Number(d.remote_id)}); await render();
    },'Verificar y vincular'));
  }
  $('#fiscal-search').oninput=drawDocuments;
  document.querySelectorAll('[data-kind]').forEach(b=>b.onclick=()=>{filter=b.dataset.kind; document.querySelectorAll('[data-kind]').forEach(x=>x.classList.toggle('selected',x===b)); drawDocuments();});
  drawDocuments();
  if (!p.linked || !sales.length) return;
  function previewSale() {
    const sale=sales.find(s=>s.id===Number($('#fiscal-sale').value));
    const customer=JSON.parse(sale.customer_snapshot);
    $('#sale-preview').innerHTML=`<div><small>Cliente</small><b>${esc(customer.name)}</b><span>${esc(customer.document || 'Sin documento')}</span></div><div><small>Total de venta</small><strong>${cash(sale.total)}</strong><span>IGV incluido</span></div>`;
    for (const kind of ['boleta','guia']) {
      const button=$('#issue-'+kind),exists=docs.some(d=>d.sale_id===sale.id && d.kind===kind);
      button.disabled=exists || (kind==='boleta' && sale.kind!=='boleta');
      button.querySelector('small').textContent=exists?'Ya existe una solicitud para esta venta':kind==='guia'?'Prepara el traslado de tus productos':sale.kind!=='boleta'?'La venta es de tipo factura':'Emite el comprobante de tu venta';
    }
  }
  $('#fiscal-sale').onchange=previewSale; previewSale();
  const seriesField = kind => `<label>Serie<select name="serie" required>${series.filter(x=>x.activo && x.tipo===kind).map(x=>`<option value="${esc(x.serie)}">${esc(x.serie)} · siguiente ${esc(x.siguiente_numero)}</option>`).join('')}</select></label>`;
  function open(kind) {
    const sid = Number($('#fiscal-sale').value);
    const sale = sales.find(s=>s.id===sid);
    if (kind === 'boleta' && sale.kind !== 'boleta') { toast('Selecciona una venta de tipo boleta.',true); return; }
    let html = `<p>Venta ${esc(sale.number)} · ${cash(sale.total)}. Entorno <strong>${esc(c.entorno)}</strong>. El proveedor asigna el número electrónico.</p>` + seriesField(kind==='boleta'?'boleta':'guia_remision');
    if (kind === 'guia') html += `<p>Guía remitente por venta (motivo 01). El destinatario se toma de la venta y debe tener DNI o RUC.</p><div class="form-grid">${field('Fecha de traslado','fecha_traslado',new Intl.DateTimeFormat('en-CA',{timeZone:'America/Lima'}).format(new Date()),'date','required')}${field('Peso total (kg)','peso_total','','number','required min="0.001" step="0.001"')}${field('Ubigeo de partida','partida_ubigeo','','text','required pattern="[0-9]{6}"')}${field('Dirección de partida','partida_direccion',c.direccion || '','text','required')}${field('Ubigeo de llegada','llegada_ubigeo','','text','required pattern="[0-9]{6}"')}${field('Dirección de llegada','llegada_direccion','','text','required')}</div><label>Modalidad<select name="mod_traslado" id="transport-mode"><option value="01">Transporte público</option><option value="02">Transporte privado</option></select></label><div id="transport-fields"></div>`;
    modal(kind==='boleta'?'Emitir boleta electrónica':'Emitir guía de remisión',html,async d=> {
      await api(`/fiscal/issue/${sid}/${kind}`,'POST',d); toast('Solicitud registrada. Consulta el estado informado.'); await render();
    },'Emitir en '+c.entorno);
    if (kind === 'guia') {
      const update = () => $('#transport-fields').innerHTML = '<div class="form-grid">' + ($('#transport-mode').value==='01' ?
        field('RUC del transportista','transportista_ruc','','text','required pattern="[0-9]{11}"')+field('Razón social del transportista','transportista_nombre','','text','required')+field('Registro MTC','nro_mtc','','text','required') :
        field('Placa','placa','','text','required maxlength="10"')+field('DNI del conductor','conductor_dni','','text','required pattern="[0-9]{8}"')+field('Nombres del conductor','conductor_nombres','','text','required')+field('Apellidos del conductor','conductor_apellidos','','text','required')+field('Licencia del conductor','licencia','','text','required')) + '</div>';
      $('#transport-mode').onchange=update; update();
    }
  }
  $('#issue-boleta').onclick=()=>open('boleta');
  $('#issue-guia').onclick=()=>open('guia');
}
