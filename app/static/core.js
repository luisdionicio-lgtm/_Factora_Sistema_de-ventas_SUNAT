import { dashboard } from "./views/dashboard.js";
import { products, customers } from "./views/catalog.js";
import { pos } from "./views/pos.js";
import { sales, reports, settings } from "./views/operations.js";
import { fiscal } from "./views/fiscal.js";
const $ = (s, r = document) => r.querySelector(s);
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const cash = (v) =>
  new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN" }).format(
    (v || 0) / 100,
  );
const date = (v) =>
  new Date(v.replace(" ", "T") + "Z").toLocaleString("es-PE", {
    timeZone: "America/Lima",
    dateStyle: "short",
    timeStyle: "short",
  });
const icon = (content) =>
  `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${content}</svg>`;
const icons = {
  grid: icon(
    '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  ),
  box: icon(
    '<path d="m12 3 9 5-9 5-9-5 9-5Zm-9 5v9l9 5 9-5V8M12 13v9M7.5 5.5l9 5"/>',
  ),
  sale: icon(
    '<path d="M3 3h2l2.5 12h11L21 7H6M9 20h.01M18 20h.01"/><circle cx="9" cy="20" r="1"/><circle cx="18" cy="20" r="1"/>',
  ),
  users: icon(
    '<circle cx="9" cy="8" r="3"/><path d="M3 21v-2a6 6 0 0 1 12 0v2M16 5a3 3 0 0 1 0 6M18 15a5 5 0 0 1 3 4v2"/>',
  ),
  receipt: icon(
    '<path d="M5 3h14v18l-3-2-4 2-4-2-3 2V3ZM8 7h8M8 11h8M8 15h5"/>',
  ),
  chart: icon('<path d="M3 3v18h18M7 16v-5M12 16V7M17 16v-9"/>'),
  settings: icon(
    '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="#102b22"/><circle cx="15" cy="17" r="3" fill="#102b22"/>',
  ),
  arrow: "→",
  plus: "+",
};
let state = {
  me: null,
  page: "dashboard",
  products: [],
  customers: [],
  sales: [],
  cart: [],
  search: "",
  category: "",
  kind: "boleta",
  customer: "",
  payment: "Efectivo",
  requestKey: crypto.randomUUID(),
};
let renderVersion = 0;
const admin = () => state.me?.user.role === "admin";
function toast(msg, error = false) {
  const el = document.createElement("div");
  el.className = "toast" + (error ? " error" : "");
  el.textContent = msg;
  $("#toasts").replaceChildren(el);
  setTimeout(() => el.remove(), 5000);
}
async function api(path, method = "GET", body) {
  const response = await fetch("/api" + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(state.me ? { "X-CSRF-Token": state.me.csrf } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 && state.me) {
      state.me = null;
      auth();
    }
    throw new Error(data.error || "No se pudo completar la solicitud.");
  }
  return data;
}
const field = (label, name, value = "", type = "text", extra = "") =>
  `<label>${label}<input name="${name}" type="${type}" value="${esc(value)}" ${extra}></label>`;
const empty = (title, body, button = "") =>
  `<div class="empty"><span class="empty-icon">▦</span><h3>${title}</h3><p>${body}</p>${button}</div>`;
const pill = (text, type = "") =>
  `<span class="pill ${type}">${esc(text)}</span>`;
function modal(title, html, submit, label = "Guardar") {
  const dialog = $("#modal");
  dialog.innerHTML = `<form id="modal-form"><div class="modal-title"><h2>${title}</h2><button type="button" class="icon-btn" id="close-modal" aria-label="Cerrar">✕</button></div><div class="modal-content">${html}</div><div class="modal-footer"><button type="button" class="btn ghost" id="cancel-modal">Cancelar</button><button class="btn primary" type="submit">${label}</button></div></form>`;
  $("#close-modal").onclick = $("#cancel-modal").onclick = () => dialog.close();
  $("#modal-form").onsubmit = async (e) => {
    e.preventDefault();
    const button = $("button[type=submit]", e.target);
    button.disabled = true;
    try {
      await submit(Object.fromEntries(new FormData(e.target)));
      dialog.close();
    } catch (err) {
      toast(err.message, true);
    } finally {
      button.disabled = false;
    }
  };
  dialog.showModal();
}
function confirmAction(title, body, fn) {
  modal(title, `<p>${esc(body)}</p>`, fn, "Confirmar");
}
function auth(register = false) {
  $("#app").innerHTML =
    `<div class="auth"><section class="auth-story"><a class="brand" href="/"><span class="brand-mark">F</span>factora<span class="brand-dot">.</span></a><div><span class="eyebrow">TU NEGOCIO, EN ORDEN</span><h1>Tu operación,<br>en <em>orden.</em></h1><p>Registra tus ventas, prepara boletas y guía tus entregas. Un espacio para llevar el control de tu negocio.</p><div class="auth-tags"><span>Boletas electrónicas</span><span>Guías de remisión</span><span>Inventario al día</span></div></div><small>Diseñado para negocios que quieren crecer. / Perú</small></section><section class="auth-form"><div class="auth-mobile brand"><span class="brand-mark">F</span>factora.</div><div class="auth-inner"><span class="eyebrow">COMIENZA AQUÍ</span><h2>${register ? "Dale espacio a tu negocio" : "Qué bueno verte de nuevo"}</h2><p>${register ? "Crea tu cuenta y organiza tu primera venta." : "Ingresa para continuar con tu día."}</p><form id="auth-form">${register ? field("Tu nombre", "name", "", "text", 'required autocomplete="name" maxlength="160"') + field("Nombre de tu negocio", "company", "", "text", 'required maxlength="160"') : ""}${field("Correo electrónico", "email", "", "email", 'required autocomplete="username" maxlength="160"')}${field("Contraseña", "password", "", "password", `required ${register ? 'minlength="12"' : ""} maxlength="200" autocomplete="${register ? "new-password" : "current-password"}"`)}${register ? "<small>Mínimo 12 caracteres. No necesitas datos de SUNAT para probar.</small>" : ""}<div id="auth-error" class="form-error" role="alert"></div><button class="btn primary wide">${register ? "Crear mi cuenta" : "Entrar a Factora"} <span>→</span></button></form><p class="auth-switch">${register ? "¿Ya tienes cuenta?" : "¿Tu primera vez aquí?"} <button id="auth-switch">${register ? "Iniciar sesión" : "Crear una cuenta"}</button></p><div class="auth-note">La emisión utiliza el entorno de tu proveedor. Los documentos beta son de prueba.</div></div></section></div>`;
  $("#auth-switch").onclick = () => auth(!register);
  $("#auth-form").onsubmit = async (e) => {
    e.preventDefault();
    const b = $("button", e.target);
    b.disabled = true;
    $("#auth-error").textContent = "";
    try {
      await api(
        register ? "/register" : "/login",
        "POST",
        Object.fromEntries(new FormData(e.target)),
      );
      await boot();
    } catch (err) {
      $("#auth-error").textContent = err.message;
    } finally {
      b.disabled = false;
    }
  };
}
const nav = [
  ["dashboard", "grid", "Resumen"],
  ["pos", "sale", "Nueva venta"],
  ["products", "box", "Inventario"],
  ["customers", "users", "Clientes"],
  ["sales", "receipt", "Comprobantes"],
  ["fiscal", "receipt", "Emisión electrónica"],
  ["reports", "chart", "Reportes"],
  ["settings", "settings", "Configuración"],
];
function shell() {
  const u = state.me.user,
    c = state.me.company;
  $("#app").innerHTML =
    `<div class="layout"><aside class="sidebar"><a class="brand" href="#dashboard"><span class="brand-mark">F</span>factora<span class="brand-dot">.</span></a><div class="workspace"><span class="workspace-icon">${esc(c.name.slice(0, 1).toUpperCase())}</span><div><b>${esc(c.name)}</b><small>Espacio de trabajo</small></div></div><span class="nav-label">PRINCIPAL</span><nav>${nav.map(([id, icon, label]) => `<button data-page="${id}" class="nav-item ${state.page === id ? "active" : ""}"><span>${icons[icon]}</span>${label}${id === "pos" ? "<i>+</i>" : ""}</button>`).join("")}</nav><div class="sidebar-bottom"><div class="mode-card"><b>Tu espacio de trabajo</b><p>Boletas, guías e inventario. Revisa tus documentos desde Emisión electrónica.</p><span class="pill amber">Boletas y guías</span></div><button class="profile" id="logout"><span class="avatar">${esc(u.name.slice(0, 2).toUpperCase())}</span><span><b>${esc(u.name)}</b><small>${u.role === "admin" ? "Administrador" : "Vendedor"}</small></span><span title="Cerrar sesión">↪</span></button></div></aside><div class="main-wrap"><header class="topbar"><button class="icon-btn mobile-menu" id="menu" aria-label="Abrir menú">☰</button><div class="breadcrumb">Mi negocio <span>/</span> <b>${nav.find((n) => n[0] === state.page)?.[2] || "Resumen"}</b></div><div class="top-right"><span class="country">PEN · Perú</span><span class="top-divider"></span><span class="avatar small">${esc(u.name.slice(0, 2).toUpperCase())}</span></div></header><main id="main" tabindex="-1"></main><footer class="app-footer">Factora <span>Gestión simple. Decisiones claras.</span><span>PEN · Hora de Perú</span></footer></div></div>`;
  document
    .querySelectorAll("[data-page]")
    .forEach((b) => (b.onclick = () => navigate(b.dataset.page)));
  $("#menu").onclick = () => $(".sidebar").classList.toggle("open");
  $("#logout").onclick = () =>
    confirmAction("Cerrar sesión", "¿Deseas salir de tu cuenta?", async () => {
      await api("/logout", "POST", {});
      state.me = null;
      state.cart = [];
      auth();
    });
}
function navigate(page) {
  state.page = nav.some((n) => n[0] === page) ? page : "dashboard";
  state.search = "";
  state.category = "";
  history.replaceState(null, "", "#" + state.page);
  shell();
  render();
}
function heading(kicker, title, subtitle, actions = "") {
  return `<div class="page-heading"><div><span class="eyebrow">${kicker}</span><h1>${title}</h1><p>${subtitle}</p></div><div class="heading-actions">${actions}</div></div>`;
}
async function loadData() {
  const [p, c, s] = await Promise.all([
    api("/products"),
    api("/customers"),
    api("/sales"),
  ]);
  state.products = p;
  state.customers = c;
  state.sales = s;
}
async function render() {
  const version = ++renderVersion;
  try {
    await loadData();
    if (version !== renderVersion) return;
    const pages = {
      dashboard: dashboard,
      products: products,
      customers: customers,
      pos: pos,
      sales: sales,
      fiscal: fiscal,
      reports: reports,
      settings: settings,
    };
    await pages[state.page]();
  } catch (err) {
    toast(err.message, true);
    if ($("#main"))
      $("#main").innerHTML = empty(
        "No pudimos cargar la información",
        "Revisa tu conexión y vuelve a intentarlo.",
        '<button class="btn primary" id="retry">Reintentar</button>',
      );
    if ($("#retry")) $("#retry").onclick = render;
  }
}
async function boot() {
  try {
    state.me = await api("/me");
    state.page = location.hash.slice(1) || "dashboard";
    if (!nav.some((n) => n[0] === state.page)) state.page = "dashboard";
    shell();
    await render();
  } catch {
    auth();
  }
}

export {
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
  auth,
  nav,
  shell,
  navigate,
  heading,
  loadData,
  render,
  boot,
};
