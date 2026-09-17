import requests
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

HEADERS = {
    "User-Agent": "Tiempo-Montevideo/1.0"
}

# =================================================
# 1. PRONÓSTICO INUMET - ÁREA METROPOLITANA
# =================================================

URL_PRONOSTICO = "https://www.inumet.gub.uy/tiempo/pronostico"

r = requests.get(
    URL_PRONOSTICO,
    headers=HEADERS,
    timeout=30
)

r.raise_for_status()

soup = BeautifulSoup(r.text, "html.parser")

texto = soup.get_text(" ", strip=True)
texto = re.sub(r"\s+", " ", texto)


patron = re.compile(
    r"(Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)"
    r"\s+(\d{1,2})"
    r".{0,100}?"
    r"Temp\.\s*min\s*(\d{1,2})\s*°C"
    r"\s*máx\s*(\d{1,2})\s*°C",
    re.IGNORECASE
)

matches = list(patron.finditer(texto))

days = []
vistos = set()


for i, m in enumerate(matches):

    fecha = f"{m.group(1)} {m.group(2)}"

    if fecha in vistos:
        continue

    vistos.add(fecha)

    temp_min = m.group(3)
    temp_max = m.group(4)

    inicio = m.end()

    if i + 1 < len(matches):
        fin = matches[i + 1].start()
    else:
        fin = len(texto)

    bloque = texto[inicio:fin]


    manana = re.search(
        r"Mañana\s+(.*?)(?=\s+Viento:|\s+Tarde/Noche)",
        bloque,
        re.IGNORECASE
    )


    tarde = re.search(
        r"Tarde/Noche\s+(.*?)(?=\s+Viento:|$)",
        bloque,
        re.IGNORECASE
    )


    vientos = re.findall(
        r"Viento:\s*(.*?)(?=\s+(?:Tarde/Noche|Mañana)|$)",
        bloque,
        re.IGNORECASE
    )


    morning = (
        manana.group(1).strip()
        if manana
        else "Sin detalle"
    )


    evening = (
        tarde.group(1).strip()
        if tarde
        else "Sin detalle"
    )


    wind = (
        " ".join(vientos)
        if vientos
        else "—"
    )


    lluvia = (
        "Precipitaciones"
        if re.search(
            r"precipit|lluvia|chaparr",
            bloque,
            re.IGNORECASE
        )
        else "No indicada"
    )


    days.append({
        "date": fecha,
        "min": temp_min,
        "max": temp_max,
        "morning": morning,
        "evening": evening,
        "wind": wind,
        "rain": lluvia
    })


    if len(days) == 3:
        break


if not days:
    raise SystemExit(
        "No se encontraron temperaturas del pronóstico."
    )


# =================================================
# 2. TEMPERATURA ACTUAL - API OFICIAL INUMET
# =================================================

API_OBSERVACIONES = (
    "https://w2b.inumet.gub.uy/oapi/collections/"
    "urn:wmo:md:uy-inumet:surface-based-observations.synop/"
    "items"
)

PRADO_WIGOS = "0-20000-0-86585"

current_temp = None
current_time = None
current_station = "Prado"


try:

    # Buscamos observaciones recientes.
    # La ventana de 48 horas permite que la app siga
    # funcionando aunque haya algún retraso en la estación.

    ahora = datetime.now(timezone.utc)

    desde = ahora - timedelta(hours=48)

    rango_tiempo = (
        desde.strftime("%Y-%m-%dT%H:%M:%SZ")
        + "/"
        + ahora.strftime("%Y-%m-%dT%H:%M:%SZ")
    )


    params = {
        "f": "json",
        "limit": 100,
        "datetime": rango_tiempo,
        "filter-lang": "cql-text",
        "filter": (
            "wigos_station_identifier='"
            + PRADO_WIGOS +
            "' AND name='air_temperature'"
        ),
        "sortby": "-phenomenonTime"
    }


    respuesta = requests.get(
        API_OBSERVACIONES,
        params=params,
        headers=HEADERS,
        timeout=30
    )


    print(
        "Consulta API INUMET:",
        respuesta.url
    )


    print(
        "Código respuesta API:",
        respuesta.status_code
    )


    respuesta.raise_for_status()

    api_data = respuesta.json()

    features = api_data.get(
        "features",
        []
    )


    print(
        "Observaciones encontradas:",
        len(features)
    )


    # Como protección adicional, comprobamos nosotros
    # mismos estación y variable.

    observaciones = []


    for feature in features:

        props = feature.get(
            "properties",
            {}
        )


        station = props.get(
            "wigos_station_identifier"
        )

        name = props.get(
            "name"
        )

        value = props.get(
            "value"
        )

        phenomenon_time = props.get(
            "phenomenonTime"
        )


        if (
            station == PRADO_WIGOS
            and name == "air_temperature"
            and value is not None
        ):

            observaciones.append({
                "temperature": value,
                "time": phenomenon_time
            })


    # Ordenamos por hora para asegurarnos de utilizar
    # siempre la observación más reciente.

    observaciones.sort(
        key=lambda x: x["time"] or "",
        reverse=True
    )


    if observaciones:

        current_temp = observaciones[0][
            "temperature"
        ]

        current_time = observaciones[0][
            "time"
        ]


        print(
            "Temperatura actual Prado:",
            current_temp
        )


        print(
            "Hora observación:",
            current_time
        )


    else:

        print(
            "No se encontró una temperatura "
            "reciente de Prado."
        )


except Exception as error:

    # Muy importante:
    # si la API de observaciones falla,
    # NO rompemos el pronóstico.

    print(
        "Error obteniendo temperatura actual:",
        error
    )


# =================================================
# 3. RESUMEN DEL DÍA
# =================================================

t = days[0]

parts = [
    f"Temperaturas de {t['min']}° a {t['max']}°"
]


if re.search(
    r"precipit|lluvia|chaparr",
    t["morning"] + " " + t["evening"],
    re.IGNORECASE
):

    parts.append(
        "con posibilidad de precipitaciones"
    )


if re.search(
    r"viento|ráfaga",
    t["wind"],
    re.IGNORECASE
):

    parts.append(
        "y viento a tener en cuenta"
    )


# =================================================
# 4. GENERAR DATA.JSON
# =================================================

data = {

    "updated": datetime.now().strftime(
        "%d/%m/%Y %H:%M"
    ),

    "current": {

        "temperature": current_temp,

        "station": current_station,

        "observation_time": current_time
    },

    "days": days,

    "summary": "; ".join(parts) + "."
}


with open(
    "data.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        data,
        f,
        ensure_ascii=False,
        indent=2
    )


print("--------------------------------")

print(
    "Temperatura Prado:",
    current_temp
)

print(
    "Hora observación:",
    current_time
)

print(
    "Pronóstico actualizado correctamente."
)
