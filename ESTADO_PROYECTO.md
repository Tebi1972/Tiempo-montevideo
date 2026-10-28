# Tiempo Uruguay — Estado técnico del proyecto

**Revisión:** 28 de octubre de 2026  
**Estado:** documentación de continuidad publicada.  
**Repositorio:** https://github.com/Tebi1972/Tiempo-montevideo  
**Aplicación:** https://tebi1972.github.io/Tiempo-montevideo/  
**Datos publicados:** https://tebi1972.github.io/Tiempo-montevideo/data.json

## 1. Propósito y reglas de trabajo

Aplicación pública de información meteorológica de Uruguay basada en fuentes de INUMET. La prioridad es conservar la exactitud, distinguir datos actuales de pronósticos y no presentar advertencias no verificadas como confirmadas.

**Regla permanente:** ninguna modificación definitiva en GitHub, Cloudflare o la aplicación sin autorización expresa previa del responsable. Probar primero, revisar resultados, obtener aprobación y recién entonces publicar. No incluir tokens, contraseñas ni credenciales en este documento.

## 2. Arquitectura verificada

- **Interfaz:** `index.html` (título Tiempo Uruguay, comentario V5.0, PWA instalable), `manifest.webmanifest`, `sw.js` e íconos.
- **Datos:** `data.json`, servido desde GitHub Pages; la interfaz vuelve a consultarlo cada cinco minutos y al recuperar foco tras cinco minutos.
- **Generación principal:** `fetch_inumet.py`, ejecutado por `.github/workflows/update.yml` mediante cron `0 * * * *` (UTC; ejecución de GitHub Actions puede demorarse). Consulta INUMET y actualiza `data.json`.
- **Advertencias:** `fetch_alertas.py`, ejecutado por `.github/workflows/actualizar_alertas.yml` con cron `15,45 * * * *`; modifica solo campos de advertencias de `data.json` y no cambia `updated`.
- **Respaldo en construcción:** Cloudflare Worker que consulta INUMET directamente, sin depender de GitHub para recuperar observaciones. Aún no se ha confirmado compatibilidad integral ni activación de respaldo en producción.

## 3. Fuentes meteorológicas verificadas en el código

- Pronóstico corto: `https://www.inumet.gub.uy/tiempo/pronostico`. Se extraen arreglos JavaScript `pronosticos["M"]`, `pronosticos["NW"]`, etc. para los primeros tres días.
- Pronóstico extendido: `https://www.inumet.gub.uy/reportes/pronosticos/pronosticoV4.json`. Se anexan fechas futuras desde `diaMasN >= 3`, sin duplicados, hasta siete días por zona. Si falla, se conservan los días disponibles del pronóstico corto.
- Observaciones SYNOP: `https://w2b.inumet.gub.uy/oapi/collections/urn:wmo:md:uy-inumet:surface-based-observations.synop/items`.
- Matriz dinámica: `https://www.inumet.gub.uy/reportes/estadoActual/estadoActualDatosHorarios.mch`.
- Advertencias: página `https://www.inumet.gub.uy/alerta` y portada `https://www.inumet.gub.uy/`; se contrasta la información de vigencia.

## 4. Estaciones, regiones y formatos

El código principal contiene 26 estaciones con clave, WIGOS, coordenadas y correspondencias de identificadores de la matriz dinámica. Consultar **siempre** el diccionario `ESTACIONES`, `DYNAMIC_IDS` y `FORECAST_ZONE_BY_LOCATION` de `fetch_inumet.py` como fuente de verdad; no duplicar manualmente listas que puedan quedar obsoletas.

Regiones de pronóstico del JSON: `M` Área Metropolitana, `NW` Noroeste, `NE` Noreste, `SO` Suroeste, `C` Centro-Sur, `E` Este, `PE` Punta del Este. La portada regional usa, según decisiones previas, Norte/Artigas, Este/Rocha, Sur/Carrasco y Oeste/Mercedes; verificar el mapeo exacto en `index.html` antes de cambiarlo.

Estructura de salida de `data.json` confirmada en `fetch_inumet.py`: `updated`, `current`, `alert`, `alert_check`, `locations`, `forecasts`, `days`, `summary`.

- `current`: resumen de Prado (temperatura, estación, hora, cielo, viento, humedad, presión, punto de rocío, sensación térmica).
- `locations`: observaciones por clave de estación, con fuente, WIGOS, latitud/longitud y zona de pronóstico.
- `forecasts`: objetos por zona con `name` y `days`; cada día puede incluir `date`, `min`, `max`, `morning`, `evening`, `wind`, `rain`, `extended` y `weather_code`.
- `alert` y `alert_check`: verificación independiente de advertencias, con distinción entre ausencia confirmada y datos no verificables.

## 5. Advertencias: reglas de seguridad

El sistema contrasta portada y objeto estructurado de INUMET, analiza fechas y vigencia de las zonas, e identifica advertencias amarillas, naranjas y rojas. Cuando no puede confirmar la ausencia de advertencias, marca `data_unavailable: true`. No reutilizar zonas vencidas como vigentes; solo conservar avisos anteriores dentro de su período válido y marcados como no verificados. La interfaz muestra advertencias confirmadas arriba y la información no verificada al pie, según pruebas previas; confirmar comportamiento actual antes de modificar.

## 6. Cloudflare: estado exacto al 28/10/2026

El código del Worker compartido en el chat actual es una **prueba diagnóstica**, no un respaldo definitivo. Utiliza las 26 estaciones, SYNOP y la matriz dinámica. Se cargó en el editor y se ejecutó en **Preview, sin pulsar Deploy**.

**Resultado de Preview suministrado:** `consultaCompleta=true`; `datosDinamicosRecibidos=true`; 167 estaciones en la matriz dinámica; 8 páginas SYNOP; 7.436 registros; 26 estaciones identificadas; 26 con observaciones de menos de dos horas; 18 con código de nubosidad. Fecha de observaciones reportadas: 28/10/2026 12:00 UTC. Esto acredita la prueba, no la disponibilidad continua futura.

**Pendiente antes de producción:**
1. Manejar el fallo de la fuente dinámica sin derribar toda la consulta.
2. Reproducir el esquema completo de `data.json` con observaciones, pronósticos cortos/extendidos y advertencias.
3. Verificar conversiones y semántica de variables, particularmente códigos de nubosidad y viento/dirección.
4. Comparar datos y horas con el generador principal; la prueba mostraba Prado 17,1 °C y `data.json` publicado 16,6 °C para 09:00 local; investigar origen antes de asumir equivalencia.
5. Probar degradación controlada cuando fallen fuentes o falten datos.
6. Definir el mecanismo real de conmutación de la interfaz al respaldo cuando GitHub falle; un Worker que entrega datos no garantiza por sí solo la disponibilidad de una página alojada exclusivamente en GitHub Pages.
7. Verificar el comportamiento de caché y de `sw.js`.
8. Confirmar qué Worker y ruta exacta se utilizarán; no se documentó aquí un nombre/URL de producción.

## 7. Próxima sesión: procedimiento de reanudación

1. Abrir este documento desde el repositorio y comprobar su fecha de revisión.
2. Consultar los archivos reales de `main` y el historial reciente antes de inferir que nada cambió.
3. Comprobar el estado de GitHub Pages y el `data.json` publicado.
4. Recuperar el código actual del Worker desde Cloudflare o de una copia validada; **no asumir** que la versión de Preview está desplegada.
5. Continuar con una propuesta de esquema JSON compatible y plan de pruebas; no modificar producción sin aprobación.
6. Al finalizar la sesión, actualizar esta bitácora con decisiones, pruebas, resultados, pendientes y siguiente paso, solicitando autorización antes de escribir en GitHub.

## 8. Asuntos pendientes fuera del respaldo

- Publicación en Google Play después de completar el respaldo.
- Posible extensión futura a Argentina y Brasil, aún no implementada.
- Tokens de GitHub: según revisión previa, vencen el **02/01/2027**; recordatorio previsto para el **26/12/2026**. No guardar valores de tokens aquí.

## 9. Historial de esta documentación

- **28/10/2026:** inspección de la estructura del repositorio y de `fetch_inumet.py`, `fetch_alertas.py`, `index.html` y ambos workflows. Incorporados resultados de la prueba Preview del Worker y decisiones previas identificadas. Documento de continuidad incorporado al repositorio con autorización expresa.

## 10. Fuentes de consulta

- https://github.com/Tebi1972/Tiempo-montevideo/blob/main/fetch_inumet.py
- https://github.com/Tebi1972/Tiempo-montevideo/blob/main/fetch_alertas.py
- https://github.com/Tebi1972/Tiempo-montevideo/blob/main/index.html
- https://github.com/Tebi1972/Tiempo-montevideo/blob/main/.github/workflows/update.yml
- https://github.com/Tebi1972/Tiempo-montevideo/blob/main/.github/workflows/actualizar_alertas.yml

**Nota:** el historial de conversaciones no se conserva íntegramente en este archivo. Las decisiones basadas en conversaciones anteriores y no verificadas directamente en el código están identificadas como tales.
