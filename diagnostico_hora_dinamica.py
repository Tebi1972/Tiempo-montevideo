import json
import re
from datetime import datetime, timezone
import requests

URL = "https://www.inumet.gub.uy/reportes/estadoActual/estadoActualDatosHorarios.mch"
HEADERS = {
    "User-Agent": "Tiempo-Uruguay-Diagnostico/1.0",
    "Cache-Control": "no-cache, no-store, max-age=0",
    "Pragma": "no-cache",
}

def parece_temporal(clave):
    return bool(re.search(
        r"(fecha|hora|time|date|actualiz|observ|timestamp|emision|vigencia)",
        str(clave), re.I
    ))

def recorrer(obj, ruta="$", hallazgos=None):
    if hallazgos is None:
        hallazgos = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            nr = f"{ruta}.{k}"
            if parece_temporal(k):
                hallazgos.append((nr, v))
            recorrer(v, nr, hallazgos)
    elif isinstance(obj, list):
        # Inspeccionamos una muestra de cada lista para evitar un log gigantesco.
        for i, v in enumerate(obj[:5]):
            recorrer(v, f"{ruta}[{i}]", hallazgos)
    return hallazgos

def resumen_tipo(v):
    if isinstance(v, (dict, list)):
        s = json.dumps(v, ensure_ascii=False)
        return s[:700] + ("..." if len(s) > 700 else "")
    return repr(v)

def main():
    cache_buster = int(datetime.now(timezone.utc).timestamp() * 1000)
    r = requests.get(URL, params={"_": cache_buster}, headers=HEADERS, timeout=30)
    r.raise_for_status()
    datos = r.json()

    print("=== DIAGNÓSTICO DE HORA - TIEMPO URUGUAY ===")
    print("HTTP:", r.status_code)
    print("URL final:", r.url)
    print("Date header HTTP:", r.headers.get("Date"))
    print("Last-Modified:", r.headers.get("Last-Modified"))
    print("Age:", r.headers.get("Age"))
    print("Cache-Control:", r.headers.get("Cache-Control"))
    print()

    print("CLAVES RAÍZ:")
    if isinstance(datos, dict):
        for k, v in datos.items():
            tam = len(v) if isinstance(v, (list, dict)) else "-"
            print(f"  {k}: {type(v).__name__} len={tam}")
    print()

    print("CAMPOS POTENCIALMENTE TEMPORALES:")
    hallazgos = recorrer(datos)
    if not hallazgos:
        print("  NO SE ENCONTRARON CAMPOS DE FECHA/HORA POR NOMBRE.")
    else:
        for ruta, valor in hallazgos:
            print(" ", ruta, "=", resumen_tipo(valor))
    print()

    # Estructura de una estación, una variable y una observación, sin volcar
    # toda la matriz.
    for clave in ("estaciones", "variables", "observaciones"):
        valor = datos.get(clave) if isinstance(datos, dict) else None
        print(f"MUESTRA {clave}:")
        if isinstance(valor, list) and valor:
            print(json.dumps(valor[0], ensure_ascii=False, indent=2)[:5000])
        else:
            print(repr(valor))
        print()

    # Buscamos específicamente Prado (211) y temperatura (47), que ya están
    # validados en Tiempo Uruguay.
    try:
        estaciones = datos.get("estaciones") or []
        variables = datos.get("variables") or []
        observaciones = datos.get("observaciones") or []
        ids_est = [x.get("id") for x in estaciones]
        ids_var = [x.get("idInt") for x in variables]
        ie = ids_est.index(211)
        iv = ids_var.index(47)
        fila = (observaciones[iv] or {}).get("datos") or []
        celda = fila[ie] if ie < len(fila) else None
        print("CELDA PRADO (ID 211) / TEMPERATURA (47):")
        print(json.dumps(celda, ensure_ascii=False, indent=2))
        print()
        print("OBJETO COMPLETO DE LA VARIABLE TEMPERATURA (47):")
        print(json.dumps(observaciones[iv], ensure_ascii=False, indent=2)[:12000])
    except Exception as e:
        print("No se pudo aislar Prado/temperatura:", repr(e))

    # Guardamos una copia del diagnóstico estructural, no modifica data.json.
    salida = {
        "consulta_utc": datetime.now(timezone.utc).isoformat(),
        "http_headers": {
            "Date": r.headers.get("Date"),
            "Last-Modified": r.headers.get("Last-Modified"),
            "Age": r.headers.get("Age"),
            "Cache-Control": r.headers.get("Cache-Control"),
        },
        "root_keys": list(datos.keys()) if isinstance(datos, dict) else [],
        "temporal_fields": [
            {"path": ruta, "value": valor}
            for ruta, valor in hallazgos
            if isinstance(valor, (str, int, float, bool)) or valor is None
        ],
    }
    with open("diagnostico_hora_dinamica.json", "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2, default=str)

    print()
    print("Diagnóstico terminado. No se modificó data.json.")

if __name__ == "__main__":
    main()
