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
function sales() {
  $("#main").innerHTML =
    heading(
      "HISTORIAL COMERCIAL",
      "Tus comprobantes",
      "Consulta y descarga los documentos de cada operación.",
      admin()
        ? '<a class="btn ghost" href="/api/export/sales">↓ Exportar CSV</a>'
        : "",
    ) +
    `<div class="callout notice">Documentos internos de gestión. Consulta estados y descarga archivos del proveedor en Emisión electrónica.</div><section class="panel"><div class="toolbar"><div class="search-box"><span>⌕</span><input id="search" placeholder="Buscar número o cliente…" aria-label="Buscar comprobantes"></div><select id="status" aria-label="Estado"><option value="">Todos los estados</option><option value="registrado">Registrados</option><option value="anulado">Anulados</option></select><span class="count">Últimos ${state.sales.length} registros</span></div><div id="sales-table"></div></section>`;
  const draw = () => {
    const q = $("#search").value.toLowerCase(),
      filter = $("#status").value;
    const list = state.sales.filter(
      (s) =>
        (s.number + " " + JSON.parse(s.customer_snapshot).name)
          .toLowerCase()
          .includes(q) &&
        (!filter || s.status === filter),
    );
    $("#sales-table").innerHTML = list.length
      ? saleTable(list)
      : empty(
          "Aún no hay comprobantes",
          "Tus ventas registradas aparecerán en este espacio.",
        );
    bindCancels();
  };
  $("#search").oninput = draw;
  $("#status").onchange = draw;
  draw();
}
async function reports() {
  const [d, m] = await Promise.all([api("/dashboard"), api("/movements")]);
  if (state.page !== "reports") return;
  $("#main").innerHTML =
    heading(
      "DATOS PARA DECIDIR",
      "Conoce tu operación",
      "Ventas acumuladas y trazabilidad del inventario.",
      admin()
        ? '<a class="btn ghost" href="/api/export/sales">↓ Descargar ventas</a>'
        : "",
    ) +
    `<div class="stats three"><article class="stat featured"><span>Ventas acumuladas</span><strong>${cash(d.stats.total)}</strong><small>Excluye operaciones anuladas</small></article><article class="stat"><span>Ticket promedio</span><strong>${cash(d.stats.count ? Math.round(d.stats.total / d.stats.count) : 0)}</strong><small>${d.stats.count} ventas registradas</small></article><article class="stat"><span>Valor del inventario</span><strong>${cash(d.stats.value)}</strong><small>Valorizado al costo actual</small></article></div><div class="dashboard-grid"><section class="panel"><div class="panel-heading"><h2>Ventas de la semana</h2></div>${chart(d.trend)}</section><section class="panel"><div class="panel-heading"><h2>Productos más vendidos</h2></div>${d.top.map((p, i) => `<div class="stock-row"><span class="rank">0${i + 1}</span><div><b>${esc(p.name)}</b><small>${p.quantity} unidades vendidas</small></div><strong>${cash(p.total)}</strong></div>`).join("") || empty("Todavía sin ventas", "Aquí verás tus productos destacados.")}</section></div><section class="panel"><div class="panel-heading"><div><h2>Kardex · Movimientos de stock</h2><p>Últimos ${m.length} movimientos. Fecha y hora de Perú.</p></div></div>${m.length ? `<div class="table-wrap"><table><thead><tr><th>Fecha</th><th>Producto</th><th>Movimiento</th><th>Saldo</th><th>Motivo</th><th>Usuario</th></tr></thead><tbody>${m.map((x) => `<tr><td>${date(x.created_at)}</td><td><b>${esc(x.name)}</b><small>${esc(x.sku)}</small></td><td>${pill((x.delta > 0 ? "+" : "") + x.delta, x.delta > 0 ? "green" : "amber")}</td><td>${x.balance}</td><td>${esc(x.reason)}</td><td>${esc(x.operator)}</td></tr>`).join("")}</tbody></table></div>` : empty("Sin movimientos", "El historial comenzará al registrar tus productos.")}</section>`;
}
async function settings() {
  const c = state.me.company;
  let users = [],
    audit = [];
  if (admin())
    [users, audit] = await Promise.all([api("/users"), api("/audit")]);
  if (state.page !== "settings") return;
  $("#main").innerHTML =
    heading(
      "A TU MEDIDA",
      "Configuración",
      "Los datos de tu negocio y la seguridad de tu cuenta.",
    ) +
    `<div class="settings-grid"><section class="panel padded"><h2>Datos del negocio</h2><p class="muted">Se conservarán en cada nuevo comprobante.</p><form id="company-form"><div class="form-grid">${field("Razón social o nombre", "name", c.name, "text", 'required maxlength="160"')}${field("RUC", "ruc", c.ruc, "text", 'pattern="[0-9]{11}" maxlength="11"')}${field("Dirección", "address", c.address, "text", 'maxlength="250"')}${field("Correo de contacto", "email", c.email, "email", 'maxlength="160"')}${field("Teléfono", "phone", c.phone, "tel", 'maxlength="30"')}</div>${admin() ? '<button class="btn primary">Guardar cambios</button>' : "<p>Solo el administrador puede modificar estos datos.</p>"}</form></section><section class="panel padded fiscal-card"><span class="eyebrow">FACTURACIÓN ELECTRÓNICA</span><h2>Conexión con SUNAT</h2><p>La integración con Kodevo está disponible en Emisión electrónica. Allí puedes vincular el emisor, emitir boletas y guías desde una venta, consultar estados y descargar archivos.</p><p>El entorno beta produce documentos de prueba. El entorno se configura con el proveedor.</p><a class="btn ghost" href="#fiscal">Abrir emisión electrónica</a></section><section class="panel padded"><h2>Seguridad de tu cuenta</h2><form id="password-form">${field("Contraseña actual", "current_password", "", "password", 'required autocomplete="current-password"')}${field("Nueva contraseña", "new_password", "", "password", 'required minlength="12" maxlength="200" autocomplete="new-password"')}<button class="btn ghost">Actualizar contraseña</button></form></section>${admin() ? `<section class="panel padded"><div class="panel-heading compact"><h2>Equipo de trabajo</h2><button class="btn ghost" id="add-user">+ Usuario</button></div>${users.map((u) => `<div class="user-row"><span class="avatar">${esc(u.name.slice(0, 1))}</span><div><b>${esc(u.name)}</b><small>${esc(u.email)} · ${u.role === "admin" ? "Administrador" : "Vendedor"}</small></div>${u.email !== state.me.user.email ? `<button class="text-link" data-toggle="${u.id}">${u.active ? "Desactivar" : "Activar"}</button>` : pill("Tú", "green")}</div>`).join("")}</section>` : ""}</div>${admin() ? `<section class="panel recent"><div class="panel-heading"><div><h2>Registro de actividad</h2><p>Últimos 500 eventos de tu negocio.</p></div></div><div class="table-wrap"><table><thead><tr><th>Fecha</th><th>Usuario</th><th>Acción</th><th>Detalle</th></tr></thead><tbody>${audit.map((a) => `<tr><td>${date(a.created_at)}</td><td>${esc(a.name)}</td><td>${esc(a.action)}</td><td>${esc(a.detail)}</td></tr>`).join("")}</tbody></table></div></section>` : ""}`;
  $("#company-form").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api("/company", "PUT", Object.fromEntries(new FormData(e.target)));
      state.me = await api("/me");
      toast("Datos del negocio actualizados");
      shell();
      render();
    } catch (err) {
      toast(err.message, true);
    }
  };
  if (!admin())
    $("#company-form")
      .querySelectorAll("input")
      .forEach((i) => (i.disabled = true));
  $("#password-form").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api("/password", "PUT", Object.fromEntries(new FormData(e.target)));
      e.target.reset();
      toast("Contraseña actualizada");
    } catch (err) {
      toast(err.message, true);
    }
  };
  if ($("#add-user"))
    $("#add-user").onclick = () =>
      modal(
        "Nuevo miembro del equipo",
        `${field("Nombre", "name", "", "text", 'required maxlength="160"')}${field("Correo", "email", "", "email", 'required maxlength="160"')}${field("Contraseña inicial", "password", "", "password", 'required minlength="12" maxlength="200" autocomplete="new-password"')}<label>Rol<select name="role"><option value="seller">Vendedor</option><option value="admin">Administrador</option></select></label><p class="hint">El vendedor registra clientes y ventas. El administrador también gestiona inventario, equipo y anulaciones.</p>`,
        async (d) => {
          await api("/users", "POST", d);
          toast("Usuario creado");
          await render();
        },
      );
  document.querySelectorAll("[data-toggle]").forEach(
    (b) =>
      (b.onclick = () =>
        confirmAction(
          "Cambiar acceso",
          "Se actualizará el acceso de este usuario y se cerrarán sus sesiones.",
          async () => {
            await api("/users/" + b.dataset.toggle + "/toggle", "POST", {});
            await render();
          },
        )),
  );
}

export { sales, reports, settings };
