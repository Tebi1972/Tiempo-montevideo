import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pathlib import Path

BASE = "https://www.inumet.gub.uy"
URL = BASE + "/tiempo/pronostico"
HEADERS = {"User-Agent": "Tiempo-Uruguay-Diagnostico/1.0"}

r = requests.get(URL, headers=HEADERS, timeout=30)
r.raise_for_status()

html = r.text
soup = BeautifulSoup(html, "html.parser")

print("=" * 80)
print("DIAGNÓSTICO SELECTOR DE ZONAS INUMET")
print("=" * 80)
print("URL final:", r.url)
print("HTTP:", r.status_code)
print("HTML bytes:", len(html))

zonas = [
    "Noroeste", "Noreste", "Suroeste", "Centro-Sur",
    "Este", "Punta del Este", "Área Metropolitana"
]

print("\n--- ELEMENTOS HTML QUE CONTIENEN NOMBRES DE ZONA ---")
for zona in zonas:
    encontrados = soup.find_all(string=re.compile(re.escape(zona), re.I))
    print(f"\n### {zona} ({len(encontrados)} coincidencias)")
    for nodo in encontrados[:10]:
        padre = nodo.parent
        print(str(padre)[:1200])

print("\n--- FORMULARIOS ---")
for i, form in enumerate(soup.find_all("form"), 1):
    print(f"\nFORM {i}")
    print(str(form)[:4000])

print("\n--- ELEMENTOS CON ATRIBUTOS DATA-* ---")
for tag in soup.find_all(True):
    attrs = {k: v for k, v in tag.attrs.items() if str(k).startswith("data-")}
    if attrs:
        texto = tag.get_text(" ", strip=True)
        if any(z.lower() in texto.lower() for z in zonas) or "pron" in str(attrs).lower() or "zona" in str(attrs).lower():
            print(tag.name, attrs, texto[:500])

print("\n--- LINKS RELACIONADOS CON PRONÓSTICO/ZONA ---")
for a in soup.find_all("a", href=True):
    txt = a.get_text(" ", strip=True)
    href = a.get("href")
    blob = (txt + " " + href).lower()
    if "pron" in blob or "zona" in blob or any(z.lower() in blob for z in zonas):
        print(txt, "=>", href)

print("\n--- SCRIPTS EXTERNOS ---")
scripts = []
for tag in soup.find_all("script", src=True):
    u = urljoin(r.url, tag["src"])
    scripts.append(u)
    print(u)

patrones = [
    r"pronost", r"zona", r"forecast", r"ajax", r"fetch\(",
    r"drupalSettings", r"views/ajax", r"/api/", r"/oapi/"
]

print("\n--- COINCIDENCIAS EN JAVASCRIPT ---")
for js_url in scripts:
    try:
        jr = requests.get(js_url, headers=HEADERS, timeout=30)
        if jr.status_code != 200:
            continue
        text = jr.text
        hits = []
        for pat in patrones:
            if re.search(pat, text, re.I):
                hits.append(pat)
        if not hits:
            continue

        print("\nJS:", js_url)
        print("Patrones:", ", ".join(hits))
        for m in re.finditer(r".{0,180}(?:pronost|zona|forecast|views/ajax|fetch\().{0,350}", text, re.I | re.S):
            frag = re.sub(r"\s+", " ", m.group(0))
            print(frag[:900])
    except Exception as e:
        print("ERROR JS:", js_url, e)

print("\n--- TEXTO/HTML CERCA DE 'Noroeste' ---")
idx = html.lower().find("noroeste")
if idx >= 0:
    print(html[max(0, idx-2500):idx+5000])
else:
    print("No se encontró Noroeste en HTML crudo.")

Path("diagnostico_zonas_inumet.html").write_text(html, encoding="utf-8")
print("\nGuardado HTML crudo en diagnostico_zonas_inumet.html")
print("FIN DEL DIAGNÓSTICO")
