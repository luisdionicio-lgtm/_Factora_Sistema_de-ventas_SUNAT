# Preparación para producción

Esta entrega está orientada a portafolio y pruebas. No debe anunciarse como un producto fiscal certificado o como una solución con todo el flujo tributario implementado.

## Antes de emitir documentos reales

- Confirmar con el proveedor la habilitación de la cuenta y del emisor en producción.
- Verificar identidad de empresa, certificado, series y régimen/tasa compatibles.
- Validar boleta y guía con datos reales del negocio y consultar sus respuestas finales.
- Definir cómo resolver rechazos, respuestas inciertas, correcciones, notas y bajas. Varias de estas funciones requieren implementación adicional.
- Definir un archivo y respaldo de PDF, XML y CDR independiente de la disponibilidad del proveedor.

## Operación de la aplicación

- Servir por HTTPS con proxy correctamente configurado y `COOKIE_SECURE=1`.
- Mantener las credenciales en variables del servidor o en almacenamiento privado; no publicarlas en Git, capturas ni logs.
- Restringir acceso a base de datos y copias de seguridad.
- Probar restauraciones. `backup.py` utiliza la API de backup de SQLite; no copies solamente el archivo `.db` de una instancia activa.
- Medir carga y concurrencia con el volumen esperado.
- Definir monitoreo, mantenimiento, actualizaciones y política de datos personales.

Para ejecución local el servidor escucha en `127.0.0.1`. Docker publica el puerto en esa interfaz por defecto. La exposición pública y el despliegue remoto no forman parte de la subida al repositorio.

## Distribución

El repositorio no incluye una licencia de redistribución. El propietario debe decidirla antes de autorizar usos de terceros. No se incorporaron credenciales de desarrollo ni bases de datos reales.
