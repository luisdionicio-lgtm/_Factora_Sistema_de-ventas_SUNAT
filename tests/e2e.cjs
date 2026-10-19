const { chromium } = require("playwright");
const { spawn } = require("child_process");
const path = require("path"),
  fs = require("fs"),
  os = require("os");
const root = path.resolve(__dirname, "..");
const output = path.join(root, "test-results");
fs.mkdirSync(output, { recursive: true });
const db = path.join(os.tmpdir(), "factora-e2e-" + Date.now() + ".db");
const server = spawn(process.env.PYTHON_BIN || "python", ["run.py"], {
  cwd: root,
  env: { ...process.env, PORT: "8001", DATABASE_PATH: db },
  stdio: "inherit",
});
process.on("exit", () => server.kill());
(async () => {
  await new Promise((r) => setTimeout(r, 1000));
  const browser = await chromium.launch({
    ...(process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {}),
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
    headless: true,
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1050 },
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://localhost:8001");
  await page.waitForSelector("#auth-form");
  await page.screenshot({
    path: path.join(output, "login.png"),
    fullPage: true,
  });
  await page.click("#auth-switch");
  await page.fill("[name=name]", "Luis Dionicio");
  await page.fill("[name=company]", "Norte Studio");
  await page.fill("[name=email]", "qa-" + Date.now() + "@example.com");
  await page.fill("[name=password]", "Prueba-segura-2026");
  await page.click("#auth-form button");
  await page.waitForSelector("#demo");
  await page.click("#demo");
  await page.click("#modal button[type=submit]");
  await page.waitForSelector(".stock-row");
  await page.click("[data-page=pos]");
  await page.waitForSelector("[data-add]");
  await page.locator("[data-add]").first().click();
  await page.click("#checkout");
  await page.waitForSelector(".success-check");
  let href = await page.locator("#modal a[href^='/receipt/']").getAttribute("href");
  await page.click("#modal button[type=submit]");
  await page.click("[data-page=dashboard]");
  await page.waitForSelector("tbody tr");
  await page.waitForTimeout(5100);
  await page.screenshot({
    path: path.join(output, "dashboard.png"),
    fullPage: true,
  });
  await page.click("[data-page=products]");
  await page.waitForSelector("[data-edit]");
  await page.click("#add-product");
  await page.fill("[name=name]", "Producto de control");
  await page.fill("[name=sku]", "QA-001");
  await page.fill("[name=price]", "25.50");
  await page.fill("[name=stock]", "12");
  await page.click("#modal button[type=submit]");
  await page.waitForSelector("#product-table");
  await page.waitForTimeout(300);
  await page.screenshot({
    path: path.join(output, "inventory.png"),
    fullPage: true,
  });
  await page.click("[data-page=customers]");
  await page.waitForSelector("#add-customer");
  await page.click("#add-customer");
  await page.fill("[name=name]", "Cliente de ejemplo");
  await page.fill("[name=document]", "12345678");
  await page.click("#modal button[type=submit]");
  await page.waitForSelector("#customer-table tbody tr");
  await page.click("[data-page=pos]");
  await page.waitForSelector("[data-add]");
  await page.locator("[data-add]").nth(1).click();
  await page.screenshot({ path: path.join(output, "pos.png"), fullPage: true });
  const receipt = await context.newPage();
  await receipt.goto("http://localhost:8001" + href);
  await receipt.screenshot({
    path: path.join(output, "receipt.png"),
    fullPage: true,
  });
  await receipt.pdf({
    path: path.join(output, "receipt-qa.pdf"),
    printBackground: true,
    preferCSSPageSize: true,
  });
  await receipt.goto("http://localhost:8001" + href + "?format=ticket");
  await receipt.screenshot({
    path: path.join(output, "ticket.png"),
    fullPage: true,
  });
  await receipt.pdf({
    path: path.join(output, "ticket-qa.pdf"),
    printBackground: true,
    preferCSSPageSize: true,
  });
  for (const view of ["reports", "settings", "sales"]) {
    await page.click("[data-page=" + view + "]");
    await page.waitForSelector(".page-heading");
    await page.waitForTimeout(250);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => {
    location.hash = "dashboard";
  });
  await page.waitForSelector(".stats");
  await page.waitForTimeout(5100);
  await page.screenshot({
    path: path.join(output, "mobile.png"),
    fullPage: true,
  });
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > innerWidth,
  );
  if (overflow) throw new Error("Mobile overflow");
  await page.click("#menu");
  await page.click("[data-page=pos]");
  await page.waitForSelector("#checkout");
  await page.screenshot({
    path: path.join(output, "mobile-pos.png"),
    fullPage: true,
  });
  console.log(
    JSON.stringify({
      errors,
      mobileOverflow: overflow,
      flow: "register → seed → sale → receipt → product → customer → views → mobile",
    }),
  );
  // Test fiscal forms with an isolated browser mock; never emit in the provider account.
  await page.route('**/api/fiscal/**', async route => {
    const url = new URL(route.request().url());
    let body;
    if (url.pathname.endsWith('/profile')) body = {linked:true, company:{ruc:'20100000001',razon_social:'Emisor QA',entorno:'beta',tiene_certificado:true,direccion:'Origen QA'}};
    else if (url.pathname.endsWith('/series')) body = [{tipo:'boleta',serie:'B001',activo:true,siguiente_numero:'B001-1'},{tipo:'guia_remision',serie:'T001',activo:true,siguiente_numero:'T001-1'}];
    else if (url.pathname.endsWith('/documents')) body = [];
    else throw new Error('Unexpected fiscal mutation in UI test: '+url.pathname);
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });
  await page.evaluate(() => { location.hash = 'fiscal'; });
  await page.waitForSelector('#issue-boleta');
  if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error('Fiscal mobile overflow');
  await page.click('#issue-guia');
  await page.waitForSelector('[name=transportista_ruc]');
  await page.selectOption('#transport-mode','02');
  await page.waitForSelector('[name=conductor_dni]');
  await page.screenshot({path:path.join(output,'fiscal-mobile.png'),fullPage:false});
  await page.click('#cancel-modal');
  await page.setViewportSize({width:1440,height:1050});
  await page.evaluate(() => window.scrollTo(0,0));
  await page.screenshot({path:path.join(output,'fiscal-overview.png'),fullPage:true});
  await page.click('#issue-boleta');
  await page.waitForSelector('[name=serie]');
  if (!(await page.locator('#modal').innerText()).includes('beta')) throw new Error('Missing beta environment');
  await page.screenshot({path:path.join(output,'fiscal-desktop.png'),fullPage:false});
  console.log(JSON.stringify({fiscalForms:'boleta, public/private guide',fiscalErrors:errors}));
  await browser.close();
  server.kill();
  if (errors.length) process.exit(1);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
