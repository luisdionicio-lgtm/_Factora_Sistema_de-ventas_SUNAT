# Desarrollo y recorrido del repositorio

La publicación se organiza en commits progresivos para facilitar su lectura. Son etapas de incorporación del proyecto existente, no una reconstrucción de su historial de desarrollo:

1. **Backend y persistencia:** aplicación Flask, autenticación, reglas comerciales, SQLite y adaptador fiscal.
2. **Interfaz:** pantallas comerciales, comprobantes internos y emisión electrónica.
3. **Calidad y ejecución:** pruebas, CI, contenedores y configuración de VS Code.
4. **Documentación:** instalación, arquitectura, uso de credenciales propias y limitaciones.

Los primeros commits son parciales; utiliza la última revisión para ejecutar la aplicación completa.

## Trabajar en una mejora

1. Crea una rama para el cambio.
2. Reproduce el problema con datos ficticios y una base separada.
3. Mantén las validaciones y permisos en el servidor.
4. Ejecuta pytest. Si cambias la interfaz, ejecuta también el recorrido Playwright.
5. Explica el cambio, cómo comprobarlo y sus límites.

No uses documentos reales ni credenciales en fixtures, capturas, issues o commits. Las pruebas automáticas no deben enviar documentos al proveedor. Si descubres un problema sensible, evita publicarlo con datos que permitan explotarlo o con secretos del emisor.
