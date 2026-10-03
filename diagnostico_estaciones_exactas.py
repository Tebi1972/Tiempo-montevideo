import json
import requests

URL = "https://www.inumet.gub.uy/reportes/estadoActual/estadoActualDatosHorarios.mch"
HEADERS = {"User-Agent": "Tiempo-Uruguay-Diagnostico-Exacto/1.0"}

# Candidatos exactos que queremos verificar. No se usa coincidencia parcial.
CANDIDATOS = {
    "montevideo_prado": [211, 652],
    "montevideo_carrasco": [39],
    "artigas": [16, 1337],
    "bella_union": [1671],
    "colonia": [66, 594],
    "durazno": [96, 610],
    "florida": [110, 1522],
    "laguna_del_sauce": [138, 953],
    "lavalleja": [1334],
    "melilla": [159, 608],
    "melo": [160, 1336, 1758],
    "mercedes": [162, 609],
    "paysandu": [201, 1333],
    "punta_del_este": [219, 1605],
    "rocha": [236, 590],
    "salto": [239, 600],
    "san_jose": [252, 1606],
    "atlantida": [1341],
    "paso_de_los_toros": [603],
    "rivera_aeropuerto": [1693, 1332],
    "san_jacinto": [1335],
    "tacuarembo": [1326, 587, 588],
    "treinta_y_tres": [272, 1342, 585],
    "trinidad": [276, 1611],
    "vichadero": [1680],
    "young": [293, 1628],
}

VARS = {
    74: "visibilidad_km",
    8: "direccion_viento_grados",
    29: "viento_nudos",
    28: "rafaga_nudos",
    105: "viento_max_hora_nudos",
    47: "temperatura_c",
    25: "humedad_pct",
    59: "punto_rocio_c",
    43: "presion_estacion_hpa",
    45: "presion_mar_hpa",
    123: "estado_actual",
    31: "nubes",
    3: "cielo",
    94: "precipitacion_horaria_mm",
}

r = requests.get(URL, headers=HEADERS, timeout=30)
r.raise_for_status()
data = r.json()
stations = data.get("estaciones") or []
variables = data.get("variables") or []
obs = data.get("observaciones") or []

station_index = {s.get("id"): (i, s) for i, s in enumerate(stations)}
var_index = {v.get("idInt"): (i, v) for i, v in enumerate(variables)}

def value(st_idx, var_id):
    if var_id not in var_index:
        return None
    vi, _ = var_index[var_id]
    try:
        row = (obs[vi] or {}).get("datos") or []
        cell = row[st_idx] if st_idx < len(row) else None
        if isinstance(cell, list):
            return cell[0] if cell else None
        return cell
    except Exception:
        return None

resultado = {}
print("=== DIAGNÓSTICO EXACTO DE CANDIDATOS ===")
for key, ids in CANDIDATOS.items():
    print(f"\n### {key}")
    resultado[key] = []
    for sid in ids:
        if sid not in station_index:
            print(f"ID {sid}: NO EXISTE EN MATRIZ")
            resultado[key].append({"id": sid, "existe": False})
            continue
        si, st = station_index[sid]
        nombre = st.get("NombreEstacion") or st.get("Estacion")
        vals = {name: value(si, vid) for vid, name in VARS.items()}
        disponibles = sum(v not in (None, "", "-", "null") for v in vals.values())
        print(f"ID {sid} | {nombre} | variables con dato: {disponibles}")
        for name, val in vals.items():
            if val not in (None, "", "-", "null"):
                print(f"  {name}: {val}")
        resultado[key].append({
            "id": sid,
            "existe": True,
            "nombre": nombre,
            "variables_con_dato": disponibles,
            "valores": vals,
        })

with open("diagnostico_estaciones_exactas.json", "w", encoding="utf-8") as f:
    json.dump(resultado, f, ensure_ascii=False, indent=2)

print("\n=== FIN DIAGNÓSTICO EXACTO ===")
