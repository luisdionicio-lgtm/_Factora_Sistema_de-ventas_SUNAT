# Integración electrónica

El adaptador usa la API de Kodevo con cabeceras `X-Api-Key` y `X-Api-Secret`. Consulta el perfil del emisor y sus series; prepara boletas y guías remitente con datos de una venta local. La colección Postman privada usada como referencia no se distribuye en este repositorio.

## Requisitos

Necesitas una cuenta propia del proveedor, credenciales vigentes, empresa configurada y series activas del tipo correspondiente. El certificado y el entorno dependen de esa cuenta. La ausencia de credenciales no impide usar la gestión comercial local.

## Recorrido

1. El administrador revisa el perfil y vincula el emisor con su negocio local.
2. El usuario registra una venta y sus productos.
3. El administrador selecciona serie y tipo de documento.
4. Para la guía completa fecha, peso, partida, llegada y transporte.
5. Factora persiste la intención de emisión y llama al proveedor.
6. Guarda ID y respuesta externa cuando puede confirmarlos.
7. El administrador consulta estados y descarga los archivos disponibles.

Una guía soportada utiliza motivo venta, peso en KGM y unidades NIU. El transporte público requiere datos del transportista y registro MTC; el privado requiere vehículo y conductor. El destinatario procede del cliente identificado de la venta.

## Estados

| Estado | Qué significa | Acción |
| --- | --- | --- |
| ENVIANDO | Solicitud registrada localmente y llamada en curso | Esperar; no repetir |
| POR_VERIFICAR | Respuesta incierta o solicitud que quedó inconclusa | Consultar el panel del proveedor |
| enviado / pendiente | Existe documento externo, sin aceptación confirmada | Consultar nuevamente |
| aceptado | El proveedor informa aceptación | Descargar y conservar los archivos |
| rechazado | El proveedor informa rechazo | Revisar descripción y resolver con el proveedor |

Un HTTP 200/201 no demuestra aceptación fiscal. Tampoco la disponibilidad de un PDF. Debe revisarse el estado y la respuesta correspondiente del entorno configurado.

Si una respuesta se perdió pero el proveedor creó el documento, utiliza **Verificar ID** para asociarlo. No crees otra venta para saltarte el bloqueo de duplicados.

## Alcance y límites

La aplicación no cambia beta a producción, no configura certificados remotos ni automatiza correcciones, notas de crédito, bajas o resúmenes. Los errores de proveedor se muestran de manera limitada para no exponer información sensible; algunos casos requieren revisar su panel.

Una emisión aceptada en beta valida una parte de la integración técnica. No demuestra habilitación en producción ni cumplimiento de todos los requisitos del negocio.
