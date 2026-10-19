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
} from "./core.js";
function saleTable(list) {
  return `<div class="table-wrap"><table><thead><tr><th>Comprobante</th><th>Cliente</th><th>Fecha</th><th>Importe</th><th>Estado</th><th></th></tr></thead><tbody>${list.map((s) => `<tr><td><b>${esc(s.number)}</b><small>${s.kind === "boleta" ? "Boleta" : "Factura"} · prueba</small></td><td>${esc(JSON.parse(s.customer_snapshot).name)}</td><td class="muted">${date(s.created_at)}</td><td class="amount">${cash(s.total)}</td><td>${pill(s.status === "anulado" ? "Anulado" : "Registrado", s.status === "anulado" ? "gray" : "green")}</td><td><a class="text-link" href="/receipt/${s.id}" target="_blank" rel="noopener">Ver ↗</a>${admin() && s.status !== "anulado" ? ` <button class="text-link danger" data-cancel="${s.id}" aria-label="Anular ${esc(s.number)}">Anular</button>` : ""}</td></tr>`).join("")}</tbody></table></div>`;
}
function bindCancels() {
  document.querySelectorAll("[data-cancel]").forEach(
    (b) =>
      (b.onclick = () =>
        confirmAction(
          "Anular venta interna",
          "Se devolverán las unidades al inventario. Esta acción queda registrada y no es una baja fiscal de SUNAT.",
          async () => {
            await api(`/sales/${b.dataset.cancel}/cancel`, "POST", {});
            toast("Venta anulada y stock devuelto");
            await render();
          },
        )),
  );
}
function chart(trend) {
  const map = Object.fromEntries(trend.map((x) => [x.day, x.total]));
  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setUTCDate(d.getUTCDate() - (6 - i));
    const key = new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/Lima",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(d);
    return {
      label: d.toLocaleDateString("es-PE", {
        weekday: "short",
        timeZone: "America/Lima",
      }),
      value: map[key] || 0,
    };
  });
  const max = Math.max(...days.map((d) => d.value), 100);
  return `<div class="bar-chart">${days.map((d) => `<div class="bar-col"><span class="bar-value">${cash(d.value)}</span><div class="bar-track"><div class="bar-fill height-${Math.max(0, Math.round((d.value / max) * 20))}" title="${cash(d.value)}"></div></div><small>${d.label}</small></div>`).join("")}</div>`;
}

export { saleTable, bindCancels, chart };
