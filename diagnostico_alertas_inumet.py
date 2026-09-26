import requests, re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

HEADERS={"User-Agent":"Tiempo-Uruguay-Alerta-Diagnostico/1.0"}
URLS=["https://www.inumet.gub.uy/","https://www.inumet.gub.uy/alerta","https://www.inumet.gub.uy/aviso","https://www.inumet.gub.uy/tiempo/historico-alertas-meteorologicas"]
CLAVES=["alert","advert","riesgo","warning","aviso","nivel","naranja","amarill","rojo","localidad","departamento","fenomen","pdf","json","ajax","fetch("]

for url in URLS:
    print("\n"+"="*90+"\nURL:",url)
    r=requests.get(url,headers=HEADERS,timeout=30)
    print("HTTP:",r.status_code,"URL final:",r.url,"bytes:",len(r.text))
    r.raise_for_status()
    soup=BeautifulSoup(r.text,"html.parser")
    texto=re.sub(r"\s+"," ",soup.get_text(" ",strip=True))

    print("\nTEXTO RELEVANTE:")
    for patron in [r".{0,180}Advertencia Meteorol[oó]gica.{0,500}",r".{0,180}Nivel\s+(?:Naranja|Amarill[oa]|Rojo).{0,700}",r".{0,180}(?:Artigas|Bella Uni[oó]n).{0,500}",r".{0,180}Vigente.{0,400}"]:
        for m in re.finditer(patron,texto,re.I):
            print(re.sub(r"\s+"," ",m.group(0))[:1200])

    print("\nLINKS RELEVANTES:")
    for a in soup.find_all("a",href=True):
        txt=a.get_text(" ",strip=True); href=urljoin(r.url,a["href"])
        if any(k in (txt+" "+href).lower() for k in CLAVES):
            print(repr(txt),"=>",href)

    print("\nSCRIPTS EXTERNOS RELEVANTES:")
    for tag in soup.find_all("script",src=True):
        js=urljoin(r.url,tag["src"])
        try:
            jr=requests.get(js,headers=HEADERS,timeout=30)
            if jr.status_code==200 and any(k in jr.text.lower() for k in CLAVES):
                print("JS:",js)
                for pat in [r".{0,180}(?:advert|alert|warning|riesgo).{0,500}",r".{0,180}(?:fetch\(|ajax|json).{0,500}"]:
                    for m in list(re.finditer(pat,jr.text,re.I|re.S))[:20]:
                        print(re.sub(r"\s+"," ",m.group(0))[:1000])
        except Exception as e:
            print("ERROR JS:",js,e)
print("\nFIN DEL DIAGNÓSTICO DE ADVERTENCIAS")
