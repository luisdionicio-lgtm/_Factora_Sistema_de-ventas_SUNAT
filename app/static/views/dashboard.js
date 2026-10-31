import {
  $,
  esc,
  cash,
  date,
  icons,
  state,
  admin,
  toast,
  api,
  field,
  empty,
  pill,
  modal,
  confirmAction,
  shell,
  navigate,
  heading,
  render,
} from "../core.js";
import { saleTable, bindCancels, chart } from "../components.js";
async function dashboard() {
  const d = await api("/dashboard");
  if (state.page !== "dashboard") return;
  const s = d.stats;
  $("#main").innerHTML =
    heading(
      "TU NEGOCIO DE UN VISTAZO",
      `Hola, ${esc(state.me.user.name.split(" ")[0])} <span class="greeting-dot">✦</span>`,
      "Esto es lo que está pasando en tu negocio.",
      `<button class="btn primary" id="new-sale">+ Nueva venta</button>`,
    ) +
    `<section class="command-banner"><div><span class="eyebrow">TU CENTRO DE OPERACIONES</span><h2>Vende. Emite. Sigue avanzando.</h2><p>Del inventario al documento electrónico, con cada operación en su lugar.</p><a href="#fiscal" class="btn primary">Preparar boleta o guía ↗</a></div><div class="command-art" aria-hidden="true"><span class="art-page"><i>F</i><b>Una operación.<br>Todo conectado.</b><em>VENTA / DOCUMENTO / ENTREGA</em></span><span class="art-stamp">F</span></div></section><div class="stats"><article class="stat featured"><div><span>Ventas de hoy</span><span>↗</span></div><strong>${cash(s.today)}</strong><small>Operaciones registradas · hora de Perú</small></article><article class="stat"><div><span>Ventas acumuladas</span><span class="stat-icon">◷</span></div><strong>${cash(s.total)}</strong><small>${s.count} operaciones activas</small></article><article class="stat"><div><span>Productos activos</span><span class="stat-icon">▣</span></div><strong>${s.products}<span> productos</span></strong><small>En tu catálogo de inventario</small></article><article class="stat"><div><span>Stock por reponer</span><span class="stat-icon amber-text">!</span></div><strong>${s.low}<span> alertas</span></strong><small>En el mínimo o por debajo</small></article></div><div class="dashboard-grid"><section class="panel"><div class="panel-heading"><div><h2>Movimiento de ventas</h2><p>Tus últimos 7 días</p></div><span class="pill gray">Esta semana</span></div>${chart(d.trend)}</section><section class="panel stock-panel"><div class="panel-heading"><div><h2>Atención al inventario</h2><p>Repón a tiempo, vende sin pausas.</p></div><span class="alert-circle">!</span></div>${
      state.products
        .filter((p) => p.stock <= p.minimum)
        .slice(0, 4)
        .map(
          (p) =>
            `<div class="stock-row"><span class="product-symbol">▣</span><div><b>${esc(p.name)}</b><small>${esc(p.sku)}</small></div><span class="pill amber">${p.stock} und.</span></div>`,
        )
        .join("") ||
      '<div class="mini-empty">Todo en orden.<br>No tienes alertas de stock.</div>'
    }<button class="text-link full-link" id="view-stock">Ir al inventario <span>→</span></button></section></div><section class="panel recent"><div class="panel-heading"><div><h2>Últimas operaciones</h2><p>El detalle de tus ventas más recientes.</p></div><button class="text-link" id="view-sales">Ver todas →</button></div>${state.sales.length ? saleTable(state.sales.slice(0, 5)) : empty("Tu próxima venta empieza aquí", "Agrega productos y registra tu primera operación.", admin() ? '<button class="btn ghost" id="demo">Cargar productos de ejemplo</button>' : "")}</section><div class="info-line"><span>i</span> Los comprobantes de gestión se registran aquí. Emite boletas y guías, consulta estados y descarga archivos en Emisión electrónica.</div>`;
  $("#new-sale").onclick = () => navigate("pos");
  $("#view-stock").onclick = () => navigate("products");
  $("#view-sales").onclick = () => navigate("sales");
  if ($("#demo"))
    $("#demo").onclick = () =>
      confirmAction(
        "Cargar productos de ejemplo",
        "Se agregarán 8 productos ficticios con stock inicial. No se crearán ventas.",
        async () => {
          await api("/demo", "POST", {});
          toast("Catálogo de ejemplo cargado");
          await render();
        },
      );
  bindCancels();
}

export { dashboard };
