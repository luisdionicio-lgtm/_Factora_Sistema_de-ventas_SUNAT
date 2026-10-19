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
import { customerForm } from "./catalog.js";
function pos() {
  $("#main").innerHTML =
    heading(
      "PUNTO DE VENTA",
      "Una venta, todo conectado",
      "Selecciona productos y registra tu operación.",
    ) +
    `<div class="pos-layout"><section><div class="search-box pos-search"><span>⌕</span><input id="product-search" placeholder="Encuentra un producto por nombre o SKU…" aria-label="Buscar producto para vender"></div><div class="category-tabs"><button data-cat="" class="selected">Todos</button>${[...new Set(state.products.map((p) => p.category))].map((c) => `<button data-cat="${esc(c)}">${esc(c)}</button>`).join("")}</div><div class="product-grid" id="catalog"></div></section><section class="panel cart"><div class="panel-heading"><h2>Detalle de venta</h2><button class="text-link" id="clear-cart">Limpiar</button></div><div class="cart-fields"><div class="segmented"><button id="boleta" class="${state.kind === "boleta" ? "selected" : ""}">Boleta</button><button id="factura" class="${state.kind === "factura" ? "selected" : ""}">Factura</button></div><label>Cliente <button class="text-link" id="quick-customer" type="button">+ Nuevo</button><select id="sale-customer"><option value="">Consumidor final</option>${state.customers.map((c) => `<option value="${c.id}" ${+state.customer === c.id ? "selected" : ""}>${esc(c.name)} · ${esc(c.doc_type)}</option>`).join("")}</select></label></div><div id="cart-lines"></div><div class="cart-bottom"><label>Medio de pago<select id="payment">${["Efectivo", "Yape", "Plin", "Tarjeta", "Transferencia"].map((p) => `<option ${state.payment === p ? "selected" : ""}>${p}</option>`).join("")}</select></label><div id="totals"></div><button class="btn primary wide" id="checkout">Registrar venta <span>→</span></button><p class="hint centered">Registra la operación y emite tu documento<br>desde Emisión electrónica.</p></div></section></div>`;
  const draw = () => {
    const q = $("#product-search").value.toLowerCase();
    const list = state.products.filter(
      (p) =>
        (p.name + " " + p.sku).toLowerCase().includes(q) &&
        (!state.category || p.category === state.category),
    );
    $("#catalog").innerHTML = list.length
      ? list
          .map(
            (p) =>
              `<button class="catalog-card" data-add="${p.id}" ${p.stock === 0 ? "disabled" : ""}><div class="catalog-top"><span class="catalog-symbol">${p.category === "Audio" ? "♫" : "▣"}</span>${pill(p.stock + " und.", p.stock <= p.minimum ? "amber" : "gray")}</div><small>${esc(p.category)}</small><b>${esc(p.name)}</b><span class="catalog-bottom"><strong>${cash(p.price)}</strong><span class="add-circle">+</span></span></button>`,
          )
          .join("")
      : empty(
          "No encontramos productos",
          "Agrega productos al inventario o cambia la búsqueda.",
        );
    document.querySelectorAll("[data-add]").forEach(
      (b) =>
        (b.onclick = () => {
          const p = state.products.find((p) => p.id === +b.dataset.add),
            line = state.cart.find((x) => x.product_id === p.id);
          if ((line?.quantity || 0) >= p.stock)
            return toast("No hay más unidades disponibles", true);
          if (line) line.quantity++;
          else state.cart.push({ product_id: p.id, quantity: 1 });
          drawCart();
        }),
    );
  };
  $("#product-search").oninput = draw;
  document.querySelectorAll("[data-cat]").forEach(
    (b) =>
      (b.onclick = () => {
        state.category = b.dataset.cat;
        document
          .querySelectorAll("[data-cat]")
          .forEach((x) => x.classList.toggle("selected", x === b));
        draw();
      }),
  );
  ["boleta", "factura"].forEach(
    (k) =>
      ($("#" + k).onclick = () => {
        state.kind = k;
        ["boleta", "factura"].forEach((x) =>
          $("#" + x).classList.toggle("selected", x === k),
        );
      }),
  );
  $("#sale-customer").onchange = (e) => (state.customer = e.target.value);
  $("#payment").onchange = (e) => (state.payment = e.target.value);
  $("#quick-customer").onclick = () =>
    customerForm(null, (r) => (state.customer = r.id));
  $("#clear-cart").onclick = () => {
    state.cart = [];
    state.requestKey = crypto.randomUUID();
    drawCart();
  };
  $("#checkout").onclick = checkout;
  draw();
  drawCart();
}
function drawCart() {
  let total = 0;
  $("#cart-lines").innerHTML = state.cart.length
    ? state.cart
        .map((line) => {
          const p = state.products.find((x) => x.id === line.product_id);
          if (!p) return "";
          total += p.price * line.quantity;
          return `<div class="cart-line"><div><b>${esc(p.name)}</b><small>${cash(p.price)} / unidad</small></div><button class="remove" data-remove="${p.id}" aria-label="Quitar ${esc(p.name)}">×</button><div class="quantity"><button data-minus="${p.id}" aria-label="Reducir cantidad">−</button><span>${line.quantity}</span><button data-plus="${p.id}" aria-label="Aumentar cantidad">+</button></div><strong>${cash(p.price * line.quantity)}</strong></div>`;
        })
        .join("")
    : '<div class="cart-empty"><span>▤</span><p>Agrega productos<br>para comenzar la venta.</p></div>';
  const base = Math.round(total / 1.18);
  $("#totals").innerHTML =
    `<div class="total-row"><span>Base gravada</span><span>${cash(base)}</span></div><div class="total-row"><span>IGV (18 %)</span><span>${cash(total - base)}</span></div><div class="total-row grand"><span>Total</span><strong>${cash(total)}</strong></div>`;
  $("#checkout").disabled = !state.cart.length;
  document.querySelectorAll("[data-remove]").forEach(
    (b) =>
      (b.onclick = () => {
        state.cart = state.cart.filter(
          (l) => l.product_id !== +b.dataset.remove,
        );
        drawCart();
      }),
  );
  document.querySelectorAll("[data-minus]").forEach(
    (b) =>
      (b.onclick = () => {
        const l = state.cart.find((l) => l.product_id === +b.dataset.minus);
        l.quantity--;
        state.cart = state.cart.filter((l) => l.quantity > 0);
        drawCart();
      }),
  );
  document.querySelectorAll("[data-plus]").forEach(
    (b) =>
      (b.onclick = () => {
        const l = state.cart.find((l) => l.product_id === +b.dataset.plus),
          p = state.products.find((p) => p.id === l.product_id);
        if (l.quantity >= p.stock)
          return toast("Stock disponible alcanzado", true);
        l.quantity++;
        drawCart();
      }),
  );
}
async function checkout() {
  const b = $("#checkout");
  b.disabled = true;
  try {
    const result = await api("/sales", "POST", {
      kind: state.kind,
      customer_id: state.customer ? Number(state.customer) : null,
      payment: state.payment,
      items: state.cart,
      request_key: state.requestKey,
    });
    state.cart = [];
    state.requestKey = crypto.randomUUID();
    toast("Venta registrada. Inventario actualizado.");
    await render();
    modal(
      "Venta registrada",
      `<div class="success-check">✓</div><p class="centered">Tu operación se guardó correctamente.</p><a class="btn primary wide" href="/receipt/${result.id}" target="_blank" rel="noopener">Abrir comprobante / Guardar PDF ↗</a><a class="btn ghost wide" href="#fiscal" id="go-fiscal">Preparar boleta o guía →</a><p class="hint centered">El PDF de gestión es interno. El documento electrónico se emite en el siguiente paso.</p>`,
      async () => {},
      "Continuar vendiendo",
    );
    $("#go-fiscal").onclick = () => $("#modal").close();
  } catch (err) {
    toast(err.message, true);
    b.disabled = false;
  }
}

export { pos };
