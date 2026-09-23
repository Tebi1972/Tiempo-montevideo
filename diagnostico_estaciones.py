import requests
import json
from datetime import datetime, timezone, timedelta

HEADERS = {"User-Agent": "Tiempo-Uruguay-Diagnostico/1.0"}

BASE = "https://w2b.inumet.gub.uy/oapi"
OBS_URL = (
    BASE + "/collections/"
    "urn:wmo:md:uy-inumet:surface-based-observations.synop/items"
)
STATIONS_URL = BASE + "/collections/stations/items"

VARIABLES = {
    "air_temperature": "temperatura",
    "present_weather": "tiempo_presente",
    "cloud_amount": "nubosidad",
    "cloud_cover_total": "nubosidad_total",
    "cloud_type": "tipo_nube",
    "wind_speed": "viento",
}

def iso_start(value):
    return str(value or "").split("/")[0]

def get_pages(url, params=None, max_pages=30):
    page = 1
    while url and page <= max_pages:
        print(f"Consultando página {page}: {url}")
        r = requests.get(url, params=params, headers=HEADERS, timeout=60)
        print("HTTP:", r.status_code)
        r.raise_for_status()
        data = r.json()

        yield data

        next_url = next(
            (x.get("href") for x in data.get("links", [])
             if x.get("rel") == "next"),
            None
        )
        url = next_url
        params = None
        page += 1

def station_id(props, feature=None):
    candidates = [
        props.get("wigos_station_identifier"),
        props.get("wigosStationIdentifier"),
        props.get("wigos_id"),
        props.get("wigosId"),
        props.get("identifier"),
    ]
    if feature:
        candidates.append(feature.get("id"))
    for x in candidates:
        if x:
            return str(x)
    return None

def station_label(props):
    for key in (
        "name", "station_name", "stationName",
        "title", "description"
    ):
        if props.get(key):
            return str(props[key])
    return None

def department_label(props):
    for key in (
        "department", "departamento",
        "administrative_area", "administrativeArea"
    ):
        if props.get(key):
            return str(props[key])
    return None

# ==========================================================
# 1. CATÁLOGO DE ESTACIONES
# ==========================================================

stations = {}

try:
    for data in get_pages(
        STATIONS_URL,
        params={"f": "json", "limit": 1000},
        max_pages=10
    ):
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            sid = station_id(props, feature)
            if not sid:
                continue

            coords = None
            geom = feature.get("geometry") or {}
            if geom.get("type") == "Point":
                coords = geom.get("coordinates")

            stations[sid] = {
                "name": station_label(props),
                "department": department_label(props),
                "coordinates": coords,
            }

    print("Estaciones del catálogo:", len(stations))

except Exception as e:
    print("No se pudo cargar el catálogo de estaciones:", e)

# ==========================================================
# 2. OBSERVACIONES RECIENTES DE TODO EL PAÍS
# ==========================================================

now = datetime.now(timezone.utc)
since = now - timedelta(hours=6)
time_range = (
    since.strftime("%Y-%m-%dT%H:%M:%SZ")
    + "/"
    + now.strftime("%Y-%m-%dT%H:%M:%SZ")
)

summary = {}

for data in get_pages(
    OBS_URL,
    params={
        "f": "json",
        "limit": 1000,
        "datetime": time_range,
    },
    max_pages=30
):
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        sid = props.get("wigos_station_identifier")
        name = props.get("name")
        time = iso_start(props.get("phenomenonTime"))

        if not sid or not name or not time:
            continue

        if name not in VARIABLES:
            continue

        row = summary.setdefault(str(sid), {
            "wigos": str(sid),
            "name": stations.get(str(sid), {}).get("name"),
            "department": stations.get(str(sid), {}).get("department"),
            "coordinates": stations.get(str(sid), {}).get("coordinates"),
            "latest_observation": None,
            "variables": {},
        })

        if (
            row["latest_observation"] is None
            or time > row["latest_observation"]
        ):
            row["latest_observation"] = time

        old = row["variables"].get(name)
        if old is None or time > old["time"]:
            row["variables"][name] = {
                "time": time,
                "value": props.get("value"),
                "description": props.get("description"),
                "units": props.get("units"),
            }

# ==========================================================
# 3. CALIFICAR ESTACIONES
# ==========================================================

results = []

for sid, row in summary.items():
    latest = row["latest_observation"]
    age_hours = None

    try:
        dt = datetime.fromisoformat(latest.replace("Z", "+00:00"))
        age_hours = round((now - dt).total_seconds() / 3600, 2)
    except Exception:
        pass

    v = row["variables"]

    has_temp = "air_temperature" in v
    has_weather = "present_weather" in v
    has_cloud = (
        "cloud_amount" in v
        or "cloud_cover_total" in v
    )
    has_wind = "wind_speed" in v

    score = sum([
        has_temp,
        has_weather,
        has_cloud,
        has_wind,
    ])

    result = {
        **row,
        "age_hours": age_hours,
        "has_temperature": has_temp,
        "has_present_weather": has_weather,
        "has_cloud": has_cloud,
        "has_wind": has_wind,
        "score": score,
    }
    results.append(result)

results.sort(
    key=lambda x: (
        -x["score"],
        x["age_hours"] if x["age_hours"] is not None else 9999,
        x["name"] or x["wigos"],
    )
)

# ==========================================================
# 4. RESULTADO
# ==========================================================

print("\n" + "=" * 86)
print("DIAGNÓSTICO NACIONAL DE ESTACIONES INUMET")
print("=" * 86)
print(
    f"{'ESTACIÓN / WIGOS':38} "
    f"{'TEMP':5} {'CIELO':6} {'TIEMPO':7} {'VIENTO':6} "
    f"{'EDAD':>8}"
)
print("-" * 86)

for x in results:
    label = x["name"] or x["wigos"]
    if x["name"]:
        label = f"{x['name']} ({x['wigos']})"

    print(
        f"{label[:38]:38} "
        f"{'✓' if x['has_temperature'] else '—':5} "
        f"{'✓' if x['has_cloud'] else '—':6} "
        f"{'✓' if x['has_present_weather'] else '—':7} "
        f"{'✓' if x['has_wind'] else '—':6} "
        f"{str(x['age_hours']) + ' h' if x['age_hours'] is not None else '—':>8}"
    )

output = {
    "generated_utc": now.isoformat(),
    "window_hours": 6,
    "stations_found": len(results),
    "stations": results,
}

with open(
    "diagnostico_estaciones.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("\nEstaciones con observaciones recientes:", len(results))
print("Archivo creado: diagnostico_estaciones.json")
print("Diagnóstico terminado.")
