import requests
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime

URL = "https://www.inumet.gub.uy/tiempo/pronostico"

r = requests.get(
    URL,
    timeout=30,
    headers={"User-Agent": "Mozilla/5.0"}
)
r.raise_for_status()

soup = BeautifulSoup(r.text, "html.parser")

text = [
    re.sub(r"\s+", " ", x.get_text(" ", strip=True)).strip()
    for x in soup.find_all(["h1", "h2", "h3", "h4", "p", "div", "span"])
]

text = [x for x in text if x]
joined = "\n".join(dict.fromkeys(text))

# Buscar cada día del pronóstico
matches = list(re.finditer(
    r"(Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)\s+\d{1,2}",
    joined
))

days = []
vistos = set()

for i, m in enumerate(matches):
    fecha = m.group(0)

    # Evitar días duplicados
    if fecha in vistos:
        continue

    vistos.add(fecha)

    siguiente = matches[i + 1].start() if i + 1 < len(matches) else len(joined)
    bloque = joined[m.start():siguiente]

    # Temperaturas: formato oficial de INUMET
    temp = re.search(
        r"Temp\.\s*min\s*(\d{1,2})°C\s*máx\s*(\d{1,2})°C",
        bloque,
        re.IGNORECASE
    )

    temp_min = temp.group(1) if temp else "—"
    temp_max = temp.group(2) if temp else "—"

    # Mañana
    mañana = re.search(
        r"Mañana\s+(.*?)(?=Viento:|Tarde/Noche|$)",
        bloque,
        re.IGNORECASE | re.DOTALL
    )

    # Tarde/Noche
    tarde = re.search(
        r"Tarde/Noche\s+(.*?)(?=Viento:|$)",
        bloque,
        re.IGNORECASE | re.DOTALL
    )

    # Viento
    vientos = re.findall(
        r"Viento:\s*(.*?)(?=\n|$)",
        bloque,
        re.IGNORECASE
    )

    morning = (
        re.sub(r"\s+", " ", mañana.group(1)).strip()
        if mañana else "Sin detalle"
    )

    evening = (
        re.sub(r"\s+", " ", tarde.group(1)).strip()
        if tarde else "Sin detalle"
    )

    wind = (
        re.sub(r"\s+", " ", vientos[-1]).strip()
        if vientos else "—"
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
