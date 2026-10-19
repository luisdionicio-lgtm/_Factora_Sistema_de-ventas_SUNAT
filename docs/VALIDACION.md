# Validación

## Automatización

La versión inicial publicada pasó 22 pruebas de backend: sesiones, CSRF, permisos, aislamiento de negocios, stock, importes, idempotencia, concurrencia, snapshots, anulación interna e integración fiscal simulada.

Las pruebas fiscales verifican emisión única, bloqueo ante respuesta incierta, correspondencia de conciliación, protección del RUC vinculado, actualización de estado y guías sin doble descuento de stock.

El recorrido Playwright comprueba registro, catálogo, venta, comprobante, clientes, vistas y formularios de emisión. Incluye comprobación de desbordamiento horizontal en móvil y errores JavaScript. La parte fiscal del navegador usa respuestas simuladas.

## Comprobación externa de desarrollo

Se verificó autenticación contra el proveedor, lectura de perfil y series y una boleta de prueba aceptada en beta con código 0. Se comprobaron PDF, XML y CDR. La prueba utilizó una base local separada del negocio y un producto identificado como prueba.

Las credenciales, respuesta completa, archivos fiscales y datos de la cuenta no se publican. Esta comprobación externa no se repite en CI y no demuestra validez tributaria en producción.

## Pendiente

- Guía completa con destinatario, ruta y transporte válidos.
- Habilitación y validación controlada del entorno de producción.
- Evaluación de carga, respaldo/restauración y revisión independiente de seguridad.
- Cobertura de las funciones fiscales aún no implementadas según el negocio objetivo.
