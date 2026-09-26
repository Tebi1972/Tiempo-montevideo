import requests
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

HEADERS = {"User-Agent": "Tiempo-Uruguay/1.0"}
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
# 1B. PRONÓSTICOS REGIONALES - 7 ZONAS INUMET
# =================================================
ZONE_NAMES = {
    "M": "Área Metropolitana",
    "NW": "Noroeste",
    "NE": "Noreste",
    "SO": "Suroeste",
    "C": "Centro-Sur",
    "E": "Este",
    "PE": "Punta del Este",
}

def extraer_objeto_balanceado(html, nombre):
    m = re.search(r"(?:var|let|const)\s+" + re.escape(nombre) + r"\s*=\s*\{", html, re.I)
    if not m:
        return None
    inicio = html.find("{", m.start())
    nivel, comilla, escape = 0, None, False
    for i in range(inicio, len(html)):
        ch = html[i]
        if comilla:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == comilla:
                comilla = None
            continue
        if ch in ("'", '"', "`"):
            comilla = ch
        elif ch == "{":
            nivel += 1
        elif ch == "}":
            nivel -= 1
            if nivel == 0:
                return html[inicio:i+1]
    return None

def limpiar_texto_html(v):
    if v is None:
        return None
    return re.sub(r"\s+", " ", BeautifulSoup(str(v), "html.parser").get_text(" ", strip=True)).strip() or None

def parsear_pronosticos_objetos(js):
    """
    Extrae cada zona y sus días sin ejecutar JavaScript.
    Aprovecha los nombres de campos observados en pronosticosObjetos.
    """
    forecasts = {}
    if not js:
        return forecasts

    # Separamos cada zona por sus claves conocidas, balanceando su objeto/array.
    posiciones = []
    for cod in ZONE_NAMES:
        m = re.search(r'(?:"|\')?' + re.escape(cod) + r'(?:"|\')?\s*:', js)
        if m:
            posiciones.append((m.start(), cod))
    posiciones.sort()

    for idx, (pos, cod) in enumerate(posiciones):
        fin = posiciones[idx+1][0] if idx+1 < len(posiciones) else len(js)
        ztxt = js[pos:fin]

        # Los días de INUMET contienen fecha y temperaturas con IDs/campos
        # pron_min_X / pron_max_X. Extraemos por bloques de día.
        fechas = list(re.finditer(
            r'(Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)\s+(\d{1,2})',
            ztxt, re.I
        ))
        dias = []
        for j, fm in enumerate(fechas[:3]):
            db = ztxt[fm.start(): fechas[j+1].start() if j+1 < len(fechas) else len(ztxt)]

            mn = re.search(r'(?:pron_min_\d+|temp(?:eratura)?[_ ]?min(?:ima)?)\D{0,80}?(-?\d{1,2})', db, re.I)
            mx = re.search(r'(?:pron_max_\d+|temp(?:eratura)?[_ ]?max(?:ima)?)\D{0,80}?(-?\d{1,2})', db, re.I)

            # Textos de mañana/tarde y viento, conservando la terminología INUMET.
            plain = limpiar_texto_html(db) or ""
            ma = re.search(r'Mañana\s+(.*?)(?=\s+Viento:|\s+Tarde/Noche)', plain, re.I)
            ta = re.search(r'Tarde/Noche\s+(.*?)(?=\s+Viento:|$)', plain, re.I)
            vi = re.findall(r'Viento:\s*(.*?)(?=\s+(?:Tarde/Noche|Mañana)|$)', plain, re.I)

            morning = ma.group(1).strip() if ma else None
            evening = ta.group(1).strip() if ta else None
            wind = " ".join(x.strip() for x in vi if x.strip()) or "—"
            texto_dia = " ".join(x for x in (morning, evening) if x)
            rain = "Precipitaciones" if re.search(
                r"precipit|lluvia|chaparr|torment", texto_dia, re.I
            ) else "No indicada"

            if mn and mx:
                dias.append({
                    "date": f"{fm.group(1)} {fm.group(2)}",
                    "min": mn.group(1),
                    "max": mx.group(1),
                    "morning": morning,
                    "evening": evening,
                    "wind": wind,
                    "rain": rain,
                })

        if dias:
            forecasts[cod] = {"name": ZONE_NAMES[cod], "days": dias}

    return forecasts

obj_js = extraer_objeto_balanceado(r.text, "pronosticosObjetos")
print("pronosticosObjetos detectado:", bool(obj_js))

forecasts = parsear_pronosticos_objetos(obj_js)

# Compatibilidad y red de seguridad: el pronóstico metropolitano histórico
# continúa disponible en 'days' y completa M si hiciera falta.
if "M" not in forecasts or not forecasts["M"].get("days"):
    forecasts["M"] = {"name": ZONE_NAMES["M"], "days": days}

print("Zonas regionales extraídas:", ", ".join(forecasts.keys()))
for _cod, _fc in forecasts.items():
    print("Pronóstico", _cod, "-", _fc["name"], "- días:", len(_fc["days"]))

# =================================================
# 2. OBSERVACIONES REALES - RED NACIONAL SYNOP
# =================================================
API_OBSERVACIONES = (
    "https://w2b.inumet.gub.uy/oapi/collections/"
    "urn:wmo:md:uy-inumet:surface-based-observations.synop/items"
)

# Estaciones verificadas por el diagnóstico nacional.
# Conservamos Prado como "current" para no alterar todavía la PWA.
ESTACIONES = {
    "montevideo_prado": ("0-20000-0-86585", "Prado", -34.860639, -56.207389),
    "montevideo_carrasco": ("0-20000-0-86580", "Carrasco", -34.832923, -56.012876),
    "artigas": ("0-20000-0-86330", "Artigas", -30.39911, -56.51267),
    "bella_union": ("0-858-0-A000000000000009", "Bella Unión", -30.253235, -57.602608),
    "colonia": ("0-20000-0-86560", "Colonia", -34.45182199, -57.76804181),
    "durazno": ("0-20000-0-86530", "Durazno", -33.350522, -56.4972385),
    "florida": ("0-20000-0-86545", "Florida", -34.086325, -56.18795),
    "laguna_del_sauce": ("0-20000-0-86586", "Laguna del Sauce", -34.8604, -55.1071),
    "lavalleja": ("0-858-0-A000000000000001", "Lavalleja", -34.336, -55.0841),
    "melilla": ("0-20000-0-86575", "Melilla", -34.781, -56.2663),
    "melo": ("0-20000-0-86440", "Melo", -32.36675, -54.19257),
    "mercedes": ("0-20000-0-86490", "Mercedes", -33.2506, -58.0692),
    "paysandu": ("0-20000-0-86430", "Paysandú", -32.381, -58.0312),
    "punta_del_este": ("0-858-0-86595", "Punta del Este", -34.9689, -54.9512),
    "rocha": ("0-20000-0-86565", "Rocha", -34.4936, -54.3125),
    "salto": ("0-20000-0-86360", "Salto", -31.4388, -57.981),
    "san_jose": ("0-858-0-86550", "San José", -34.3519, -56.7497),
    "atlantida": ("0-858-0-A000000000000003", "Atlántida", -34.7797, -55.7528),
    "paso_de_los_toros": ("0-20000-0-86460", "Paso de los Toros", -32.7967, -56.5147),
    "rivera_aeropuerto": ("0-858-0-A000000000000004", "Rivera Aeropuerto", -30.9703, -55.4735),
    "san_jacinto": ("0-858-0-A000000000000002", "San Jacinto", -34.5145, -55.8464),
    "tacuarembo": ("0-20000-0-86370", "Tacuarembó", -31.7499634024, -55.9288138511),
    "treinta_y_tres": ("0-858-0-A000000000000005", "Treinta y Tres Aeropuerto", -33.1968, -54.3481),
    "trinidad": ("0-858-0-A000000000000007", "Trinidad", -33.486257, -56.890246),
    "vichadero": ("0-858-0-A000000000000008", "Vichadero", -31.74309, -54.58984),
    "young": ("0-858-0-A000000000000006", "Young", -32.66447, -57.58991),
}
WIGOS_A_KEY = {v[0]: k for k, v in ESTACIONES.items()}

# Zona oficial de pronóstico asociada a cada estación de la aplicación.
FORECAST_ZONE_BY_LOCATION = {
    "montevideo_prado": "M",
    "montevideo_carrasco": "M",
    "melilla": "M",
    "atlantida": "M",
    "san_jacinto": "M",
    "artigas": "NW",
    "bella_union": "NW",
    "salto": "NW",
    "paysandu": "NW",
    "young": "NW",
    "rivera_aeropuerto": "NE",
    "tacuarembo": "NE",
    "vichadero": "NE",
    "melo": "NE",
    "colonia": "SO",
    "mercedes": "SO",
    "san_jose": "SO",
    "durazno": "C",
    "florida": "C",
    "paso_de_los_toros": "C",
    "trinidad": "C",
    "lavalleja": "E",
    "rocha": "E",
    "treinta_y_tres": "E",
    "laguna_del_sauce": "E",
    "punta_del_este": "PE",
}

def instante(props):
    return str(props.get("phenomenonTime", "")).split("/")[0]

def edad_horas(hora, ahora):
    try:
        dt = datetime.fromisoformat(hora.replace("Z", "+00:00"))
        return (ahora - dt).total_seconds() / 3600
    except Exception:
        return None

def observacion_vacia(meta):
    wigos, nombre, lat, lon = meta
    return {
        "temperature": None, "station": nombre, "wigos": wigos,
        "latitude": lat, "longitude": lon, "observation_time": None,
        "condition": "neutral", "condition_time": None,
        "present_weather": None, "cloud_amount": None,
        "cloud_types": [], "wind_speed_kmh": None,
    }

def construir_observacion(meta, registros, ahora):
    out = observacion_vacia(meta)

    temps = [p for p in registros if p.get("name") == "air_temperature"
             and p.get("value") is not None]
    temps.sort(key=instante, reverse=True)
    if temps:
        hora = instante(temps[0])
        edad = edad_horas(hora, ahora)
        if edad is not None and 0 <= edad <= 2:
            out["temperature"] = temps[0].get("value")
            out["observation_time"] = hora

    nombres = {"present_weather", "cloud_amount", "cloud_cover_total",
               "cloud_type", "wind_speed"}
    recientes = []
    for p in registros:
        if p.get("name") not in nombres:
            continue
        hora = instante(p)
        edad = edad_horas(hora, ahora)
        if edad is not None and 0 <= edad <= 2:
            recientes.append(p)

    if not recientes:
        return out

    recientes.sort(key=instante, reverse=True)
    out["condition_time"] = instante(recientes[0])

    def ultimo(nombre):
        xs = [p for p in recientes if p.get("name") == nombre]
        xs.sort(key=instante, reverse=True)
        if not xs:
            return []
        h = instante(xs[0])
        return [p for p in xs if instante(p) == h]

    weather = ultimo("present_weather")
    clouds = ultimo("cloud_amount")
    totals = ultimo("cloud_cover_total")
    types = ultimo("cloud_type")
    winds = ultimo("wind_speed")

    wd = [str(p.get("description") or "") for p in weather]
    cd = [str(p.get("description") or "") for p in clouds]
    out["present_weather"] = " | ".join(x for x in wd if x) or None
    out["cloud_amount"] = " | ".join(x for x in cd if x) or None
    out["cloud_types"] = [str(p["description"]) for p in types
                          if p.get("description")]

    if winds and winds[0].get("value") is not None:
        out["wind_speed_kmh"] = round(float(winds[0]["value"]) * 3.6, 1)

    weather_text = " ".join(wd).upper()
    cloud_text = " ".join(cd).upper()

    if any(x in weather_text for x in ("THUNDER", "LIGHTNING")):
        out["condition"] = "stormy"
    elif any(x in weather_text for x in
             ("RAIN", "DRIZZLE", "SHOWER", "PRECIPIT", "HAIL", "SNOW")):
        out["condition"] = "rainy"
    elif any(x in weather_text for x in ("FOG", "MIST")):
        out["condition"] = "cloudy"
    else:
        oktas = [int(x) for x in re.findall(r"(\d+)\s*OKTAS?", cloud_text)]
        cobertura = max(oktas) if oktas else None

        if cobertura is None and totals:
            try:
                valor = float(totals[0].get("value"))
                cobertura = round(valor) if 0 <= valor <= 8 else (
                    round(valor * 8 / 100) if 0 <= valor <= 100 else None
                )
            except (TypeError, ValueError):
                pass

        if cobertura is not None:
            out["condition"] = (
                "cloudy" if cobertura >= 7 else
                "partly" if cobertura >= 3 else
                "sunny"
            )
    return out

locations = {k: observacion_vacia(v) for k, v in ESTACIONES.items()}
for _key in locations:
    locations[_key]["forecast_zone"] = FORECAST_ZONE_BY_LOCATION.get(_key, "M")

try:
    ahora = datetime.now(timezone.utc)
    desde = ahora - timedelta(hours=24)
    rango_tiempo = (desde.strftime("%Y-%m-%dT%H:%M:%SZ") + "/" +
                    ahora.strftime("%Y-%m-%dT%H:%M:%SZ"))

    registros = {k: [] for k in ESTACIONES}
    url_actual = API_OBSERVACIONES
    params = {"f": "json", "limit": 1000, "datetime": rango_tiempo}
    pagina = 1

    while url_actual and pagina <= 20:
        print("Consultando página nacional:", pagina)
        respuesta = requests.get(url_actual, params=params, headers=HEADERS, timeout=60)
        print("Código respuesta API:", respuesta.status_code)
        respuesta.raise_for_status()
        api_data = respuesta.json()
        print("Registros recibidos:", len(api_data.get("features", [])))

        for feature in api_data.get("features", []):
            props = feature.get("properties", {})
            key = WIGOS_A_KEY.get(str(props.get("wigos_station_identifier")))
            if key and props.get("phenomenonTime"):
                registros[key].append(props)

        siguiente = next((x.get("href") for x in api_data.get("links", [])
                          if x.get("rel") == "next"), None)
        if siguiente:
            url_actual, params, pagina = siguiente, None, pagina + 1
        else:
            url_actual = None

    for key, meta in ESTACIONES.items():
        locations[key] = construir_observacion(meta, registros[key], ahora)
        locations[key]["forecast_zone"] = FORECAST_ZONE_BY_LOCATION.get(key, "M")
        o = locations[key]
        print(key, o["temperature"], o["condition"], o["wind_speed_kmh"])

except Exception as error:
    print("Error obteniendo observaciones nacionales:", error)

# Compatibilidad con la aplicación actual: current sigue siendo Prado.
prado = locations["montevideo_prado"]
current_temp = prado["temperature"]
current_time = prado["observation_time"]
current_station = prado["station"]
condition = prado["condition"]
condition_time = prado["condition_time"]
present_weather = prado["present_weather"]
cloud_amount = prado["cloud_amount"]
cloud_types = prado["cloud_types"]
wind_speed_kmh = prado["wind_speed_kmh"]

# =================================================
# 3. ADVERTENCIA METEOROLÓGICA OFICIAL INUMET
# =================================================
# Primera etapa segura:
# - comprobamos únicamente si INUMET declara que NO hay advertencia vigente;
# - todavía no interpretamos nivel, fenómeno ni localidades.
# Esto evita falsos positivos porque la página puede contener textos de
# plantillas ocultas aunque no exista una advertencia activa.

URL_ALERTA = "https://www.inumet.gub.uy/alerta"
alert = {"active": False}

try:
    respuesta_alerta = requests.get(URL_ALERTA, headers=HEADERS, timeout=30)
    print("Código respuesta advertencias:", respuesta_alerta.status_code)
    respuesta_alerta.raise_for_status()

    soup_alerta = BeautifulSoup(respuesta_alerta.text, "html.parser")
    texto_alerta = re.sub(r"\s+", " ", soup_alerta.get_text(" ", strip=True))

    sin_advertencia = re.search(
        r"No\s+hay\s+advertencia\s+meteorol[oó]gica\s+vigente",
        texto_alerta,
        re.IGNORECASE,
    )

    if sin_advertencia:
        alert = {"active": False}
        print("Advertencia INUMET: no hay advertencia meteorológica vigente.")
    else:
        # Hay indicios de una advertencia activa, pero en esta primera etapa
        # no publicamos datos que todavía no hayan sido validados.
        alert = {
            "active": True,
            "status": "pending_validation"
        }
        print("Advertencia INUMET: posible advertencia vigente detectada.")
        print("Se requiere validar nivel, fenómeno y área antes de mostrarla.")

except Exception as error:
    # Si INUMET no responde, no inventamos una advertencia.
    alert = {
        "active": False,
        "check_error": True
    }
    print("Error consultando advertencias INUMET:", error)

# =================================================
# 4. RESUMEN DEL PRONÓSTICO
# =================================================
t = days[0]
parts = [f"Temperaturas de {t['min']}° a {t['max']}°"]
texto_hoy = f"{t.get('morning') or ''} {t.get('evening') or ''}"
if re.search(r"precipit|lluvia|chaparr", texto_hoy, re.IGNORECASE):
    parts.append("con posibilidad de precipitaciones")
if re.search(r"viento|ráfaga", t["wind"], re.IGNORECASE):
    parts.append("y viento a tener en cuenta")

# =================================================
# 5. CREAR DATA.JSON
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
    "alert": alert,
    "locations": locations,
    "forecasts": forecasts,
    "days": days,
    "summary": "; ".join(parts) + ".",
}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("--------------------------------")
print("Temperatura Prado:", current_temp)
print("Condición visual observada:", condition)
print("Hora condición UTC:", condition_time)
print("Advertencia:", alert)
print("Hora actualización Uruguay:", ahora_uruguay.strftime("%d/%m/%Y %H:%M"))
print("Pronóstico, observación y advertencia actualizados correctamente.")
