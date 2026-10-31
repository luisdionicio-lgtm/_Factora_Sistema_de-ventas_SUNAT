# Factora

### Sistema de ventas, inventario y emisión electrónica para Perú

Aplicación web para registrar ventas, controlar existencias y preparar boletas electrónicas y guías de remisión mediante una API externa. Proyecto de portafolio con backend Flask, SQLite e interfaz en JavaScript nativo.

**Estado:** gestión comercial funcional e integración de boletas comprobada en el entorno beta del proveedor. Las guías tienen pruebas automatizadas con respuestas simuladas; falta validar un traslado completo con datos reales. Los documentos beta no tienen validez tributaria. Este repositorio no se presenta como un sistema fiscal certificado ni listo para producción.

## Qué puedes hacer

- Registrar negocios, usuarios administradores y vendedores, y clientes.
- Gestionar productos, precios, stock mínimo y movimientos de inventario.
- Registrar ventas con cálculo de importes en el servidor y control transaccional de stock.
- Consultar un dashboard, kardex y auditoría, y exportar datos a CSV.
- Imprimir documentos internos en A4 o ticket de 80 mm.
- Vincular un emisor del proveedor, consultar series y emitir boletas desde una venta.
- Preparar guías remitente por venta con transporte público o privado.
- Consultar estados electrónicos y descargar los archivos que entregue el proveedor.
- Conciliar una respuesta incierta sin repetir automáticamente la emisión.

## Tecnologías

| Capa | Implementación |
| --- | --- |
| Backend | Python, Flask y Waitress |
| Datos | SQLite, transacciones, claves foráneas y WAL |
| Interfaz | HTML, CSS y módulos JavaScript ES |
| Autenticación | Contraseñas con scrypt y sesiones con tokens almacenados como hash |
| Protección | CSRF, permisos por rol, validación de origen y separación por negocio |
| Pruebas | pytest y Playwright |
| Ejecución | Windows, terminal, VS Code y Docker |

## Inicio rápido

Requiere Python 3.12 o superior. Node.js solo es necesario para las herramientas de desarrollo y las pruebas de navegador.

```bash
git clone https://github.com/luisdionicio-lgtm/_Factora_Sistema_de-ventas_SUNAT.git
cd _Factora_Sistema_de-ventas_SUNAT
python -m venv .venv
```

En Windows:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

En macOS o Linux:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py
```

Abre **http://localhost:8000** y crea tu cuenta. No se incluyen usuarios ni contraseñas predeterminados. También puedes usar `start-windows.bat` o `start.sh`.

La base local se crea automáticamente en `data/factora.db`. Puedes probar inventario, clientes, ventas e impresión sin configurar ninguna API.

### Visual Studio Code

Abre la carpeta y selecciona **Factora · ejecutar aplicación** en Ejecutar y depurar. Con las extensiones Python y Python Debugger instaladas, **F5** utiliza el entorno virtual y abre **http://localhost:8003**. Este puerto permite mantener una instancia normal en 8000.

No ejecutes este proyecto únicamente con Live Server: Flask es necesario para las operaciones de negocio.

## Primer recorrido

1. Crea una cuenta e inicia sesión.
2. Agrega productos al inventario o carga el catálogo ficticio desde Resumen.
3. Registra un cliente. La guía requiere destinatario con DNI o RUC.
4. Abre Nueva venta, añade productos y registra el pago manual.
5. Consulta el documento interno y prueba su impresión A4 o ticket.
6. Si configuraste tus credenciales, abre Emisión electrónica y vincula el emisor al negocio correcto.
7. Selecciona una venta, prepara la boleta o guía y consulta el resultado.

El comprobante interno y el documento electrónico tienen numeraciones independientes. Registrar una venta no equivale a una aceptación fiscal. La guía no vuelve a descontar el stock de la venta.

## Configuración de la API

La integración requiere `FISCAL_COMPANY_ID` con el ID del negocio local autorizado. Por defecto queda bloqueada. Consulta [Seguridad](SECURITY.md) para configurarlo antes de vincular el emisor.

**No se incluyen API Key, API Secret, certificados, claves SOL ni datos de la cuenta utilizada durante el desarrollo.** Cada persona debe utilizar sus propias credenciales de Kodevo. El adaptador está implementado en `app/fiscal.py` y apunta a `https://sunat.kodevo.es/api/v1/`.

Para una ejecución local, configura variables reales del sistema antes de iniciar el servidor. Ejemplo de PowerShell, reemplazando los valores ilustrativos:

```powershell
$env:FISCAL_API_KEY = 'TU_API_KEY'
$env:FISCAL_API_SECRET = 'TU_API_SECRET'
.venv\Scripts\python.exe run.py
```

Alternativamente crea **solo en tu equipo** `data/fiscal-secrets.json`:

```json
{
  "api_key": "TU_API_KEY",
  "api_secret": "TU_API_SECRET"
}
```

Este archivo y toda la carpeta `data/` están excluidos de Git. Las credenciales se usan en el servidor y no se envían al frontend. El servidor local no carga `.env` automáticamente.

El entorno beta o producción se consulta al proveedor; Factora no lo cambia automáticamente. Consulta [la integración](docs/INTEGRACION.md) antes de emitir.

### Docker

```bash
docker compose up --build -d
```

El volumen conserva la base de datos. Para usar el proveedor en Docker, copia `.env.example` a `.env` y completa tus propias credenciales; Compose las entrega al contenedor. No publiques `.env`. Para proteger el volumen, evita `docker compose down -v` si necesitas conservar sus datos.

## Pruebas

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
```

La versión publicada cuenta con **24 pruebas de backend**. Las pruebas fiscales automatizadas simulan respuestas del proveedor: no necesitan credenciales ni crean documentos externos.

Para comprobar la interfaz:

```bash
npm ci
npx playwright install chromium
npm run test:e2e
```

Si `python` no corresponde al entorno virtual, configura `PYTHON_BIN` con su ruta absoluta antes de ejecutar las pruebas. `CHROMIUM_PATH` permite usar un Chromium o Edge instalado. El recorrido usa una base temporal, datos ficticios y el puerto 8001. Las capturas y PDF se guardan en `test-results/`, excluido de Git. El flujo fiscal de navegador usa respuestas simuladas y no emite ante el proveedor.

## Estructura

```text
app/
  __init__.py       Aplicación y endpoints comerciales
  db.py            Conexiones y transacciones
  schema.sql       Esquema comercial
  services.py      Ventas, importes y stock
  security.py      Sesiones, CSRF, roles y auditoría
  fiscal.py        Adaptador del proveedor y documentos electrónicos
  templates/       Pantallas y comprobante interno
  static/          Interfaz, estilos y vistas
tests/             Pruebas de backend y navegador
docs/              Arquitectura, integración y guías de desarrollo
.vscode/           Configuración de ejecución y pruebas
```

## Límites actuales

- Ventas en PEN, unidades enteras, precios con IGV 18 % y pago al contado.
- El medio de pago es un registro manual; no confirma pagos de Yape, Plin ni bancos.
- Las facturas disponibles en la gestión comercial son internas; el adaptador implementa emisión de boletas y guías remitente por venta.
- Sin notas de crédito, bajas, correcciones fiscales, resúmenes diarios ni guías transportista.
- Las validaciones de DNI/RUC comprueban formato, no identidad ni estado tributario.
- Los archivos electrónicos se descargan del proveedor; no hay archivo fiscal automático independiente.
- SQLite y los listados actuales están orientados a operación pequeña; una instalación de mayor carga necesita mediciones y mejoras.

## Documentación y próximos pasos

- [Arquitectura y decisiones](docs/ARQUITECTURA.md)
- [Integración electrónica y estados](docs/INTEGRACION.md)
- [Pruebas y evidencia](docs/VALIDACION.md)
- [Preparación para producción](docs/PRODUCCION.md)
- [Cómo contribuir y recorrido de commits](CONTRIBUTING.md)

No se ha asignado una licencia de redistribución al código del proyecto. Las dependencias mantienen sus propias licencias.
