import requests
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

HEADERS = {"User-Agent": "Tiempo-Montevideo/1.0"}
URUGUAY_TZ = ZoneInfo("America/Montevideo")

# =================================================
# 1. PRONÓSTICO INUMET - ÁREA METROPOLITANA
# =================================================
URL_PRONOSTICO = "https://www.inumet.gub.uy/tiempo/pronostico"
r = requests.get(URL_PRONOSTICO, headers=HEADERS, timeout=30)
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")
texto = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

patron = re.compile(
    r"(Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)"
    r"\s+(\d{1,2})"
    r".{0,100}?"
    r"Temp\.\s*min\s*(\d{1,2})\s*°C"
    r"\s*máx\s*(\d{1,2})\s*°C",
    re.IGNORECASE,
)

matches = list(patron.finditer(texto))
days, vistos = [], set()
for i, m in enumerate(matches):
    fecha = f"{m.group(1)} {m.group(2)}"
    if fecha in vistos:
        continue
    vistos.add(fecha)
    inicio = m.end()
    fin = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
    bloque = texto[inicio:fin]

    manana = re.search(r"Mañana\s+(.*?)(?=\s+Viento:|\s+Tarde/Noche)", bloque, re.IGNORECASE)
    tarde = re.search(r"Tarde/Noche\s+(.*?)(?=\s+Viento:|$)", bloque, re.IGNORECASE)
    vientos = re.findall(r"Viento:\s*(.*?)(?=\s+(?:Tarde/Noche|Mañana)|$)", bloque, re.IGNORECASE)

    morning = manana.group(1).strip() if manana else None
    evening = tarde.group(1).strip() if tarde else None
    wind = " ".join(vientos) if vientos else "—"
    lluvia = "Precipitaciones" if re.search(r"precipit|lluvia|chaparr", bloque, re.IGNORECASE) else "No indicada"

    days.append({
        "date": fecha,
        "min": m.group(3),
        "max": m.group(4),
        "morning": morning,
        "evening": evening,
        "wind": wind,
        "rain": lluvia,
    })
    if len(days) == 3:
        break

if not days:
    raise SystemExit("No se encontraron temperaturas del pronóstico.")

# =================================================
# 2. OBSERVACIÓN REAL - PRADO / SYNOP
# =================================================
API_OBSERVACIONES = (
    "https://w2b.inumet.gub.uy/oapi/collections/"
    "urn:wmo:md:uy-inumet:surface-based-observations.synop/items"
)
PRADO_WIGOS = "0-20000-0-86585"

current_temp = None
current_time = None
current_station = "Prado"
condition = "neutral"
condition_time = None
present_weather = None
cloud_amount = None
cloud_types = []
wind_speed_kmh = None

try:
    ahora = datetime.now(timezone.utc)
    desde = ahora - timedelta(hours=24)
    rango_tiempo = desde.strftime("%Y-%m-%dT%H:%M:%SZ") + "/" + ahora.strftime("%Y-%m-%dT%H:%M:%SZ")

    url_actual = API_OBSERVACIONES
    params = {"f": "json", "limit": 1000, "datetime": rango_tiempo}
    registros_prado = []
    pagina = 1

    while url_actual and pagina <= 20:
        print("Consultando página:", pagina)
        respuesta = requests.get(url_actual, params=params, headers=HEADERS, timeout=60)
        print("Código respuesta API:", respuesta.status_code)
        respuesta.raise_for_status()
        api_data = respuesta.json()
        features = api_data.get("features", [])
        print("Registros recibidos en página:", len(features))

        for feature in features:
            props = feature.get("properties", {})
            if props.get("wigos_station_identifier") == PRADO_WIGOS and props.get("phenomenonTime"):
                registros_prado.append(props)

        siguiente = next((x.get("href") for x in api_data.get("links", []) if x.get("rel") == "next"), None)
        if siguiente:
            url_actual, params, pagina = siguiente, None, pagina + 1
        else:
            url_actual = None

    print("Registros de Prado encontrados:", len(registros_prado))

    def instante(props):
        # Algunos campos usan intervalos ISO: tomamos el inicio de la observación.
        return str(props.get("phenomenonTime", "")).split("/")[0]

    # Temperatura más reciente.
    temps = [p for p in registros_prado if p.get("name") == "air_temperature" and p.get("value") is not None]
    temps.sort(key=instante, reverse=True)
    if temps:
        t = temps[0]
        hora = instante(t)
        dt = datetime.fromisoformat(hora.replace("Z", "+00:00"))
        edad_h = (ahora - dt).total_seconds() / 3600
        print("Temperatura Prado encontrada:", t.get("value"))
        print("Hora encontrada:", hora)
        print("Antigüedad de la observación:", round(edad_h, 2), "horas")
        if 0 <= edad_h <= 2:
            current_temp = t.get("value")
            current_time = hora
            print("Temperatura aceptada como actual:", current_temp)

    # Para el entorno usamos un único instante de observación: el más reciente
    # que contenga información de cielo/tiempo/viento y no tenga más de 2 horas.
    nombres_entorno = {"present_weather", "cloud_amount", "cloud_cover_total", "cloud_type", "wind_speed"}
    candidatos = [p for p in registros_prado if p.get("name") in nombres_entorno]
    candidatos.sort(key=instante, reverse=True)

    if candidatos:
        latest_time = instante(candidatos[0])
        latest_dt = datetime.fromisoformat(latest_time.replace("Z", "+00:00"))
        edad_entorno = (ahora - latest_dt).total_seconds() / 3600
        print("Hora observación para entorno:", latest_time)
        print("Antigüedad entorno:", round(edad_entorno, 2), "horas")

        if 0 <= edad_entorno <= 2:
            mismos = [p for p in candidatos if instante(p) == latest_time]
            condition_time = latest_time

            weather_desc = [str(p.get("description") or "") for p in mismos if p.get("name") == "present_weather"]
            cloud_desc = [str(p.get("description") or "") for p in mismos if p.get("name") == "cloud_amount"]
            cloud_types = [str(p.get("description") or "") for p in mismos if p.get("name") == "cloud_type" and p.get("description")]
            present_weather = " | ".join(x for x in weather_desc if x) or None
            cloud_amount = " | ".join(x for x in cloud_desc if x) or None

            winds = [p for p in mismos if p.get("name") == "wind_speed" and p.get("value") is not None]
            if winds:
                # La colección publica wind_speed en m/s; lo pasamos a km/h.
                wind_speed_kmh = round(float(winds[0]["value"]) * 3.6, 1)

            weather_text = " ".join(weather_desc).upper()
            cloud_text = " ".join(cloud_desc).upper()

            if any(x in weather_text for x in ["THUNDER", "LIGHTNING"]):
                condition = "stormy"
            elif any(x in weather_text for x in ["RAIN", "DRIZZLE", "SHOWER", "PRECIPIT", "HAIL", "SNOW"]):
                condition = "rainy"
            elif any(x in weather_text for x in ["FOG", "MIST"]):
                condition = "cloudy"
            else:
                # cloud_amount suele describirse como "N OKTAS".
                oktas = [int(x) for x in re.findall(r"(\d+)\s*OKTAS?", cloud_text)]
                max_oktas = max(oktas) if oktas else None
                if max_oktas is not None:
                    if max_oktas >= 7:
                        condition = "cloudy"
                    elif max_oktas >= 3:
                        condition = "partly"
                    else:
                        condition = "sunny"
                else:
                    # Si no hay información suficiente, ambiente neutral.
                    condition = "neutral"

            print("Tiempo presente:", present_weather)
            print("Nubosidad:", cloud_amount)
            print("Condición visual:", condition)
            print("Viento observado km/h:", wind_speed_kmh)
        else:
            print("Observación de entorno descartada por antigüedad.")

except Exception as error:
    print("Error obteniendo observación actual:", error)

# =================================================
# 3. RESUMEN DEL PRONÓSTICO
# =================================================
t = days[0]
parts = [f"Temperaturas de {t['min']}° a {t['max']}°"]
texto_hoy = f"{t.get('morning') or ''} {t.get('evening') or ''}"
if re.search(r"precipit|lluvia|chaparr", texto_hoy, re.IGNORECASE):
    parts.append("con posibilidad de precipitaciones")
if re.search(r"viento|ráfaga", t["wind"], re.IGNORECASE):
    parts.append("y viento a tener en cuenta")

# =================================================
# 4. CREAR DATA.JSON
# =================================================
ahora_uruguay = datetime.now(URUGUAY_TZ)
data = {
    "updated": ahora_uruguay.strftime("%d/%m/%Y %H:%M"),
    "current": {
        "temperature": current_temp,
        "station": current_station,
        "observation_time": current_time,
        "condition": condition,
        "condition_time": condition_time,
        "present_weather": present_weather,
        "cloud_amount": cloud_amount,
        "cloud_types": cloud_types,
        "wind_speed_kmh": wind_speed_kmh,
    },
    "days": days,
    "summary": "; ".join(parts) + ".",
}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("--------------------------------")
print("Temperatura Prado:", current_temp)
print("Condición visual observada:", condition)
print("Hora condición UTC:", condition_time)
print("Hora actualización Uruguay:", ahora_uruguay.strftime("%d/%m/%Y %H:%M"))
print("Pronóstico y observación actualizados correctamente.")
