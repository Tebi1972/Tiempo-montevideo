import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Tiempo-Montevideo/1.0"}
URUGUAY_TZ = ZoneInfo("America/Montevideo")
URL_ALERTA = "https://www.inumet.gub.uy/alerta"
URL_INICIO = "https://www.inumet.gub.uy/"
DATA_PATH = Path("data.json")


def extraer_objeto_js_variable(html, nombre):
    patrones = [
        r'(?:var|let|const)\s+' + re.escape(nombre) + r'\s*=\s*',
        r'\b' + re.escape(nombre) + r'\s*=\s*',
    ]
    m = None
    for patron in patrones:
        m = re.search(patron, html, re.I)
        if m:
            break
    if not m:
        return None

    inicio = html.find("{", m.end())
    if inicio < 0:
        return None

    nivel = 0
    comilla = None
    escape = False
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
        if ch in ('"', "'"):
            comilla = ch
        elif ch == "{":
            nivel += 1
        elif ch == "}":
            nivel -= 1
            if nivel == 0:
                return html[inicio:i + 1]
    return None


def nivel_advertencia(riesgos):
    valores = []
    for valor in (riesgos or {}).values():
        try:
            valores.append(int(valor))
        except (TypeError, ValueError):
            pass
    maximo = max(valores) if valores else 1
    return {2: "amarilla", 3: "naranja", 4: "roja"}.get(maximo)


def texto_zonas(zonas):
    if zonas is None:
        return ""
    return re.sub(
        r"\s+", " ",
        BeautifulSoup(str(zonas), "html.parser").get_text(" ", strip=True),
    ).strip()


def fecha_uruguay(fecha):
    if not fecha:
        return None

    texto_fecha = str(fecha).strip()
    formatos = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
    )
    for formato in formatos:
        try:
            return datetime.strptime(texto_fecha, formato).replace(tzinfo=URUGUAY_TZ)
        except ValueError:
            pass

    try:
        dt = datetime.fromisoformat(texto_fecha.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=URUGUAY_TZ)
        return dt.astimezone(URUGUAY_TZ)
    except Exception:
        return None


def marca_frescura_alerta(datos):
    # No usamos "finalizacion" como marca de actualización.
    fechas = []

    for campo in ("fechaActualizacion", "actualizacion", "updated"):
        dt = fecha_uruguay(datos.get(campo))
        if dt:
            fechas.append(dt)

    for adv in datos.get("advertencias") or []:
        for campo in ("actualizacion", "emision", "emitido", "comienzo"):
            dt = fecha_uruguay(adv.get(campo))
            if dt:
                fechas.append(dt)

    return max(fechas) if fechas else None


def portada_indica_vigente():
    try:
        headers = dict(HEADERS)
        headers.update({
            "Cache-Control": "no-cache, no-store, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        })
        cache_buster = int(datetime.now(timezone.utc).timestamp() * 1000)
        respuesta = requests.get(
            URL_INICIO,
            params={"_": cache_buster},
            headers=headers,
            timeout=30,
        )
        respuesta.raise_for_status()

        texto_portada = re.sub(
            r"\s+", " ",
            BeautifulSoup(respuesta.text, "html.parser").get_text(" ", strip=True),
        )

        vigente = bool(re.search(
            r"Advertencia\s+Meteorol[oó]gica.{0,300}\bVigente\b",
            texto_portada,
            re.I,
        ))
        print("Portada INUMET indica advertencia vigente:", vigente)
        return vigente

    except Exception as error:
        print("No se pudo verificar portada INUMET:", error)
        return None


def descargar_objetos_alerta():
    candidatos = []
    headers_alerta = dict(HEADERS)
    headers_alerta.update({
        "Cache-Control": "no-cache, no-store, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    })

    for intento in range(1, 4):
        try:
            cache_buster = int(datetime.now(timezone.utc).timestamp() * 1000) + intento
            respuesta = requests.get(
                URL_ALERTA,
                params={"_": cache_buster},
                headers=headers_alerta,
                timeout=30,
            )

            print(
                f"Advertencias intento {intento}:",
                respuesta.status_code,
                "| bytes:",
                len(respuesta.text),
            )
            respuesta.raise_for_status()

            bruto = extraer_objeto_js_variable(respuesta.text, "alerta")
            print(f"Objeto alerta intento {intento}:", bool(bruto))
            if not bruto:
                continue

            datos = json.loads(bruto)
            if not isinstance(datos, dict):
                continue

            marca = marca_frescura_alerta(datos)
            print(
                f"Marca de frescura intento {intento}:",
                marca.strftime("%d/%m/%Y %H:%M:%S") if marca else "SIN FECHA",
            )
            print(
                f"Bloques recibidos intento {intento}:",
                len(datos.get("advertencias") or []),
            )
            candidatos.append((marca, datos))

        except Exception as error:
            print(f"Error leyendo advertencias intento {intento}:", error)

    return candidatos


def obtener_alerta():
    portada_vigente = portada_indica_vigente()
    candidatos = descargar_objetos_alerta()
    ahora_local = datetime.now(URUGUAY_TZ)

    candidatos.sort(
        key=lambda item: item[0] or datetime(1970, 1, 1, tzinfo=URUGUAY_TZ),
        reverse=True,
    )

    datos_alerta = candidatos[0][1] if candidatos else None
    marca_fuente = candidatos[0][0] if candidatos else None

    edad_fuente_h = None
    if marca_fuente:
        edad_fuente_h = (ahora_local - marca_fuente).total_seconds() / 3600

    print(
        "Objeto de advertencias seleccionado:",
        marca_fuente.strftime("%d/%m/%Y %H:%M:%S") if marca_fuente else "SIN FECHA",
    )
    print(
        "Edad de la fuente (h):",
        round(edad_fuente_h, 2) if edad_fuente_h is not None else "?",
    )

    vigentes = []
    if isinstance(datos_alerta, dict):
        for adv in datos_alerta.get("advertencias") or []:
            inicio_dt = fecha_uruguay(adv.get("comienzo"))
            fin_dt = fecha_uruguay(adv.get("finalizacion"))

            if fin_dt is not None and fin_dt < ahora_local:
                continue
            if inicio_dt is not None and inicio_dt > ahora_local:
                continue

            nivel = nivel_advertencia(adv.get("riesgoFenomeno"))
            if not nivel:
                continue

            vigentes.append({
                "level": nivel,
                "phenomenon": adv.get("fenomeno"),
                "probability": adv.get("probabilidad"),
                "start": adv.get("comienzo"),
                "end": adv.get("finalizacion"),
                "description": adv.get("descripcion"),
                "zones": texto_zonas(adv.get("zonas")),
                "risk": adv.get("riesgoFenomeno") or {},
            })

    if vigentes:
        prioridad = {"amarilla": 2, "naranja": 3, "roja": 4}
        vigentes.sort(
            key=lambda x: prioridad.get(x.get("level"), 0),
            reverse=True,
        )
        principal = vigentes[0]

        alert = {
            "active": True,
            "level": principal["level"],
            "phenomenon": principal["phenomenon"],
            "probability": principal["probability"],
            "start": principal["start"],
            "end": principal["end"],
            "description": principal["description"],
            "zones": principal["zones"],
            "warnings": vigentes,
            "updated": (
                datos_alerta.get("fechaActualizacion")
                or datos_alerta.get("actualizacion")
            ),
            "pdf": datos_alerta.get("pdf"),
            "source": "inumet_alerta_object_v4",
            "source_timestamp": marca_fuente.isoformat() if marca_fuente else None,
            "source_age_hours": (
                round(edad_fuente_h, 2) if edad_fuente_h is not None else None
            ),
            "homepage_says_active": portada_vigente,
            "data_unavailable": False,
        }

        print("Advertencias INUMET vigentes:", len(vigentes))
        for adv in vigentes:
            print(
                "ALERTA",
                adv["level"].upper(),
                "|",
                adv.get("phenomenon"),
                "|",
                adv.get("start"),
                "->",
                adv.get("end"),
            )
            print("ZONAS:", adv.get("zones"))
        return alert

    if portada_vigente is True:
        print(
            "ATENCIÓN: portada INUMET = VIGENTE, "
            "pero no hay zonas estructuradas vigentes."
        )
        return {
            "active": False,
            "data_unavailable": True,
            "homepage_says_active": True,
            "source": "inumet_sources_out_of_sync",
            "source_timestamp": marca_fuente.isoformat() if marca_fuente else None,
            "source_age_hours": (
                round(edad_fuente_h, 2) if edad_fuente_h is not None else None
            ),
            "message": (
                "INUMET informa una advertencia vigente, pero la fuente "
                "estructurada de zonas aún no entrega datos vigentes."
            ),
        }

    print("INUMET no entrega advertencias vigentes.")
    return {
        "active": False,
        "data_unavailable": False,
        "homepage_says_active": portada_vigente,
        "source": "inumet_alerta_object_v4",
        "source_timestamp": marca_fuente.isoformat() if marca_fuente else None,
        "source_age_hours": (
            round(edad_fuente_h, 2) if edad_fuente_h is not None else None
        ),
    }


def main():
    if not DATA_PATH.exists():
        raise SystemExit("No existe data.json. Ejecutá primero fetch_inumet.py.")

    with DATA_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    try:
        alert = obtener_alerta()
    except Exception as error:
        # Importante: si falla la consulta, NO borramos una advertencia válida
        # que ya estuviera en data.json. Solo registramos el fallo.
        print("Error procesando advertencias INUMET:", error)
        data["alert_check"] = {
            "ok": False,
            "checked_at": datetime.now(URUGUAY_TZ).isoformat(timespec="minutes"),
            "error": str(error),
        }
        with DATA_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        raise

    data["alert"] = alert
    data["alert_check"] = {
        "ok": True,
        "checked_at": datetime.now(URUGUAY_TZ).isoformat(timespec="minutes"),
    }

    # No modificamos data["updated"]: esa hora sigue indicando cuándo se
    # actualizaron pronóstico y observaciones. Solo reemplazamos advertencias.
    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Advertencias actualizadas sin modificar pronóstico ni observaciones.")


if __name__ == "__main__":
    main()
