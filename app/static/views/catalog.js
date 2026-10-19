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
function productForm(p) {
  modal(
    p ? "Editar producto" : "Nuevo producto",
    `<div class="form-grid">${field("Nombre del producto", "name", p?.name || "", "text", 'required maxlength="160"')}${field("Código SKU", "sku", p?.sku || "", "text", 'required maxlength="40"')}${field("Categoría", "category", p?.category || "General", "text", 'required maxlength="60"')}${field("Precio de venta (incluye IGV)", "price", p ? (p.price / 100).toFixed(2) : "", "number", 'required min="0" max="1000000" step="0.01"')}${field("Costo unitario", "cost", p ? (p.cost / 100).toFixed(2) : "0", "number", 'required min="0" max="1000000" step="0.01"')}${!p ? field("Stock inicial", "stock", "0", "number", 'required min="0" max="1000000" step="1"') : ""}${field("Alerta de stock mínimo", "minimum", p?.minimum ?? 5, "number", 'required min="0" max="1000000" step="1"')}</div><p class="hint">Productos gravados con IGV 18 %. Cantidades enteras. Los ajustes de stock se registran por separado.</p>`,
    async (d) => {
      d.minimum = Number(d.minimum);
      if (!p) d.stock = Number(d.stock);
      await api("/products" + (p ? "/" + p.id : ""), p ? "PUT" : "POST", d);
      toast("Producto guardado");
      await render();
    },
  );
}
function products() {
  const cats = [...new Set(state.products.map((p) => p.category))];
  $("#main").innerHTML =
    heading(
      "CATÁLOGO Y EXISTENCIAS",
      "Todo tu inventario",
      "Productos organizados. Stock siempre al día.",
      `${admin() ? '<a class="btn ghost" href="/api/export/products">↓ Exportar</a><button class="btn primary" id="add-product">+ Nuevo producto</button>' : ""}`,
    ) +
    `<section class="panel"><div class="toolbar"><div class="search-box"><span>⌕</span><input id="search" placeholder="Buscar por nombre o SKU…" aria-label="Buscar productos"></div><select id="category" aria-label="Categoría"><option value="">Todas las categorías</option>${cats.map((c) => `<option>${esc(c)}</option>`).join("")}</select><label class="check"><input type="checkbox" id="low-stock"> Stock bajo</label><span class="count">${state.products.length} productos</span></div><div id="product-table"></div></section>`;
  const draw = () => {
    const q = $("#search").value.toLowerCase();
    const list = state.products.filter(
      (p) =>
        (p.name + " " + p.sku).toLowerCase().includes(q) &&
        (!$("#category").value || p.category === $("#category").value) &&
        (!$("#low-stock").checked || p.stock <= p.minimum),
    );
    $("#product-table").innerHTML = list.length
      ? `<div class="table-wrap"><table><thead><tr><th>Producto</th><th>Categoría</th><th>Precio</th><th>Stock</th><th>Estado</th>${admin() ? "<th>Acciones</th>" : ""}</tr></thead><tbody>${list.map((p) => `<tr><td><div class="product-cell"><span class="product-symbol">▣</span><div><b>${esc(p.name)}</b><small>${esc(p.sku)}</small></div></div></td><td>${esc(p.category)}</td><td class="amount">${cash(p.price)}</td><td><b>${p.stock}</b> <span class="muted">und.</span></td><td>${pill(p.stock === 0 ? "Agotado" : p.stock <= p.minimum ? "Stock bajo" : "Disponible", p.stock <= p.minimum ? "amber" : "green")}</td>${admin() ? `<td><button class="table-btn" data-edit="${p.id}">Editar</button><button class="table-btn" data-stock="${p.id}">± Stock</button>${p.stock === 0 ? `<button class="table-btn danger" data-archive="${p.id}">Archivar</button>` : ""}</td>` : ""}</tr>`).join("")}</tbody></table></div>`
      : empty(
          "No hay productos para mostrar",
          "Agrega tu primer producto o cambia los filtros.",
        );
    document
      .querySelectorAll("[data-edit]")
      .forEach(
        (b) =>
          (b.onclick = () =>
            productForm(state.products.find((p) => p.id === +b.dataset.edit))),
      );
    document.querySelectorAll("[data-stock]").forEach(
      (b) =>
        (b.onclick = () => {
          const p = state.products.find((p) => p.id === +b.dataset.stock);
          modal(
            "Movimiento de stock",
            `<div class="callout">${esc(p.name)} · Stock actual: <b>${p.stock}</b></div>${field("Cantidad (+ entrada / − salida)", "delta", "", "number", 'required step="1" min="-1000000" max="1000000"')}${field("Motivo del movimiento", "reason", "", "text", 'required maxlength="250"')}`,
            async (d) => {
              await api(`/products/${p.id}/stock`, "POST", {
                ...d,
                delta: Number(d.delta),
              });
              toast("Stock actualizado");
              await render();
            },
          );
        }),
    );
    document.querySelectorAll("[data-archive]").forEach(
      (b) =>
        (b.onclick = () =>
          confirmAction(
            "Archivar producto",
            "Se ocultará del catálogo. Su historial de ventas y movimientos se conservará.",
            async () => {
              await api("/products/" + b.dataset.archive, "DELETE", {});
              await render();
              toast("Producto archivado");
            },
          )),
    );
  };
  $("#search").oninput = draw;
  $("#category").onchange = draw;
  $("#low-stock").onchange = draw;
  if ($("#add-product")) $("#add-product").onclick = () => productForm();
  draw();
}
function customerForm(c, after) {
  modal(
    c ? "Editar cliente" : "Nuevo cliente",
    `<div class="form-grid">${field("Nombre o razón social", "name", c?.name || "", "text", 'required maxlength="160"')}<label>Tipo de documento<select name="doc_type">${["DNI", "RUC", "OTRO"].map((t) => `<option ${c?.doc_type === t ? "selected" : ""}>${t}</option>`).join("")}</select></label>${field("Número de documento", "document", c?.document || "", "text", 'required maxlength="30"')}${field("Correo electrónico", "email", c?.email || "", "email", 'maxlength="160"')}${field("Dirección", "address", c?.address || "", "text", 'maxlength="250"')}</div>`,
    async (d) => {
      const result = await api(
        "/customers" + (c ? "/" + c.id : ""),
        c ? "PUT" : "POST",
        d,
      );
      if (after) after(result);
      toast("Cliente guardado");
      await render();
    },
  );
}
function customers() {
  $("#main").innerHTML =
    heading(
      "RELACIONES QUE CRECEN",
      "Tus clientes",
      "La información que necesitas para cada venta.",
      '<button class="btn primary" id="add-customer">+ Nuevo cliente</button>',
    ) +
    `<section class="panel"><div class="toolbar"><div class="search-box"><span>⌕</span><input id="search" placeholder="Buscar nombre o documento…" aria-label="Buscar clientes"></div><span class="count">${state.customers.length} clientes</span></div><div id="customer-table"></div></section>`;
  const draw = () => {
    const q = $("#search").value.toLowerCase();
    const list = state.customers.filter((c) =>
      (c.name + " " + c.document).toLowerCase().includes(q),
    );
    $("#customer-table").innerHTML = list.length
      ? `<div class="table-wrap"><table><thead><tr><th>Cliente</th><th>Documento</th><th>Correo</th><th>Dirección</th><th></th></tr></thead><tbody>${list.map((c) => `<tr><td><b>${esc(c.name)}</b></td><td>${pill(c.doc_type, "gray")} ${esc(c.document)}</td><td>${esc(c.email || "—")}</td><td>${esc(c.address || "—")}</td><td><button class="table-btn" data-edit="${c.id}">Editar</button></td></tr>`).join("")}</tbody></table></div>`
      : empty(
          "Tu cartera de clientes comienza aquí",
          "Registra personas y empresas para agilizar tus ventas.",
        );
    document
      .querySelectorAll("[data-edit]")
      .forEach(
        (b) =>
          (b.onclick = () =>
            customerForm(
              state.customers.find((c) => c.id === +b.dataset.edit),
            )),
      );
  };
  $("#search").oninput = draw;
  $("#add-customer").onclick = () => customerForm();
  draw();
}

export { products, customers, customerForm };
