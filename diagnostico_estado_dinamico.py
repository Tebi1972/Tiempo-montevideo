import json
import re
import unicodedata
import requests

URL = "https://www.inumet.gub.uy/reportes/estadoActual/estadoActualDatosHorarios.mch"
HEADERS = {"User-Agent": "Tiempo-Uruguay-Diagnostico/1.0"}

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

def norm(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

ALIASES = {
    "montevideo_prado": ["prado"],
    "montevideo_carrasco": ["carrasco", "aeropuerto internacional gral cesareo l berisso"],
    "artigas": ["artigas"],
    "bella_union": ["bella union"],
    "colonia": ["colonia", "laguna de los patos"],
    "durazno": ["durazno", "santa bernardina"],
    "florida": ["florida"],
    "laguna_del_sauce": ["laguna del sauce", "carlos a curbelo"],
    "lavalleja": ["lavalleja"],
    "melilla": ["melilla", "angel s adami"],
    "melo": ["melo"],
    "mercedes": ["mercedes"],
    "paysandu": ["paysandu"],
    "punta_del_este": ["punta del este"],
    "rocha": ["rocha"],
    "salto": ["salto", "nueva hesperides"],
    "san_jose": ["san jose"],
    "atlantida": ["atlantida"],
    "paso_de_los_toros": ["paso de los toros"],
    "rivera_aeropuerto": ["rivera", "oscar d gestido"],
    "san_jacinto": ["san jacinto"],
    "tacuarembo": ["tacuarembo"],
    "treinta_y_tres": ["treinta y tres"],
    "trinidad": ["trinidad"],
    "vichadero": ["vichadero"],
    "young": ["young"],
}

r = requests.get(URL, headers=HEADERS, timeout=30)
r.raise_for_status()
data = r.json()

stations = data.get("estaciones") or []
variables = data.get("variables") or []
observaciones = data.get("observaciones") or []

print("=== VARIABLES DISPONIBLES EN MATRIZ DINÁMICA ===")
for i, v in enumerate(variables):
    print(i, json.dumps(v, ensure_ascii=False))

print("\n=== ESTACIONES DISPONIBLES EN MATRIZ DINÁMICA ===")
for i, s in enumerate(stations):
    print(i, json.dumps(s, ensure_ascii=False))

def station_name(s):
    for k in ("nombre", "name", "estacion", "descripcion", "label"):
        if s.get(k):
            return str(s[k])
    return json.dumps(s, ensure_ascii=False)

def value_at(st_idx, var_idx):
    try:
        row = (observaciones[var_idx] or {}).get("datos") or []
        cell = row[st_idx] if st_idx < len(row) else None
        if isinstance(cell, list):
            return cell[0] if cell else None
        return cell
    except Exception:
        return None

print("\n=== CRUCE TIEMPO URUGUAY -> MATRIZ DINÁMICA ===")
summary = {}
for key, meta in ESTACIONES.items():
    wigos, display, lat, lon = meta
    aliases = [norm(x) for x in ALIASES.get(key, [display])]
    candidates = []
    for i, s in enumerate(stations):
        n = norm(station_name(s))
        score = sum(1 for a in aliases if a and (a in n or n in a))
        if score:
            candidates.append((score, i, s))
    candidates.sort(key=lambda x: (-x[0], x[1]))
    if not candidates:
        print(f"\nNO ENCONTRADA | {key} | {display} | {wigos}")
        summary[key] = {"status": "not_found", "display": display, "wigos": wigos}
        continue

    score, idx, st = candidates[0]
    sid = st.get("id")
    name = station_name(st)
    print(f"\nENCONTRADA | {key} | {display} | WIGOS={wigos} | ID={sid} | MATRIZ={name}")
    vals = {}
    for vi, var in enumerate(variables):
        val = value_at(idx, vi)
        if val not in (None, "", "-", "null"):
            vid = var.get("idInt", var.get("id"))
            vname = var.get("nombre") or var.get("name") or var.get("descripcion") or str(var)
            vals[str(vid)] = {"variable": vname, "valor": val}
            print(f"  VAR {vid}: {vname} = {val}")
    summary[key] = {
        "status": "found",
        "display": display,
        "wigos": wigos,
        "dynamic_id": sid,
        "dynamic_name": name,
        "values": vals,
    }

with open("diagnostico_estado_dinamico.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print("\n=== RESUMEN ===")
print("Encontradas:", sum(1 for x in summary.values() if x["status"] == "found"))
print("No encontradas:", sum(1 for x in summary.values() if x["status"] != "found"))
print("Se creó diagnostico_estado_dinamico.json")
