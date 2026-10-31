# Seguridad

No publiques credenciales, bases de datos, certificados ni documentos fiscales en issues o commits. Para un reporte sensible contacta al propietario del repositorio de forma privada.

## Credenciales del proveedor

La integración fiscal permanece bloqueada hasta que el operador configure `FISCAL_COMPANY_ID` con el ID del negocio local autorizado. El ID se encuentra en la respuesta autenticada de `/api/me`, dentro de `company.id`. No es el RUC ni el ID de empresa del proveedor. Configura el valor en el servidor, nunca desde el navegador. Ser administrador de otra cuenta no da acceso al emisor.

Ejemplo de PowerShell, después de comprobar el negocio correcto:

```powershell
$env:FISCAL_COMPANY_ID = 'ID_LOCAL_AUTORIZADO'
```

Una clave compartida en un chat o fuera del gestor privado de secretos debe reemplazarse desde el proveedor. Que no aparezca en Git no demuestra que nunca haya sido expuesta en otro medio. La rotación debe conservar la vinculación al emisor correcto.

## Verificaciones

`python scripts/check_secrets.py` busca patrones de secretos en archivos versionados e historial alcanzable. Es una protección adicional, no una garantía de ausencia de cualquier dato sensible. No inspecciona copias externas, logs del proveedor, forks ni mensajes.

Las respuestas fiscales al navegador incluyen únicamente número y campos de estado utilizados por la interfaz. Se evitan trazas con mensajes externos en el log de errores inesperados. El despliegue público requiere HTTPS, cookies Secure, configuración del proxy, copias privadas y revisión adicional.
