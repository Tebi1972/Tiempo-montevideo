import requests
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime

URL = "https://www.inumet.gub.uy/tiempo/pronostico"

r = requests.get(
    URL,
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=30
)
r.raise_for_status()

soup = BeautifulSoup(r.text, "html.parser")

# Texto completo de INUMET
texto = soup.get_text(" ", strip=True)
texto = re.sub(r"\s+", " ", texto)

# Buscamos cada día junto con su temperatura
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
        if manana else "Sin detalle"
    )

    evening = (
        tarde.group(1).strip()
        if tarde else "Sin detalle"
    )

    wind = " ".join(vientos) if vientos else "—"

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
        "No se encontraron temperaturas en INUMET"
    )

t = days[0]

parts = [
    f"Temperaturas de {t['min']}° a {t['max']}°"
]

if re.search(
    r"precipit|lluvia|chaparr",
    t["morning"] + " " + t["evening"],
    re.IGNORECASE
):
    parts.append("con posibilidad de precipitaciones")

if re.search(
    r"viento|ráfaga",
    t["wind"],
    re.IGNORECASE
):
    parts.append("y viento a tener en cuenta")

data = {
    "updated": datetime.now().strftime("%d/%m/%Y %H:%M"),
    "days": days,
    "summary": "; ".join(parts) + "."
}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(
        data,
        f,
        ensure_ascii=False,
        indent=2
    )        "evening": evening,
        "wind": wind,
        "rain": lluvia
    })

    if len(days) >= 3:
        break

if not days:
    raise SystemExit(
        "No se pudo interpretar el pronóstico de INUMET"
    )

# Resumen
t = days[0]
parts = []

if t["min"] != "—":
    parts.append(
        f"Temperaturas de {t['min']}° a {t['max']}°"
    )

if re.search(
    r"precipit|lluvia|chaparr",
    t["morning"] + " " + t["evening"],
    re.IGNORECASE
):
    parts.append("con posibilidad de precipitaciones")

if re.search(
    r"viento|ráfaga",
    t["wind"],
    re.IGNORECASE
):
    parts.append("y viento a tener en cuenta")

data = {
    "updated": datetime.now().strftime("%d/%m/%Y %H:%M"),
    "days": days,
    "summary": "; ".join(parts) + "."
}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(
        data,
        f,
        ensure_ascii=False,
        indent=2
    )
