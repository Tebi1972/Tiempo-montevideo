import requests,re,json
from bs4 import BeautifulSoup
from datetime import datetime
URL='https://www.inumet.gub.uy/tiempo/pronostico'
r=requests.get(URL,timeout=30,headers={'User-Agent':'Mozilla/5.0'});r.raise_for_status();s=BeautifulSoup(r.text,'html.parser')
text=[re.sub(r'\s+',' ',x.get_text(' ',strip=True)).strip() for x in s.find_all(['h1','h2','h3','h4','p','div','span'])]
text=[x for x in text if x]; joined='\n'.join(dict.fromkeys(text)); ms=list(re.finditer(r'(Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)\s+\d{1,2}',joined)); days=[]
for i,m in enumerate(ms[:5]):
 b=joined[m.start():ms[i+1].start() if i+1<len(ms) else len(joined)];tm=re.search(r'(\d{1,2})\s*°?C?\s+(\d{1,2})\s*°?C?',b);am=re.search(r'Mañana\s+(.*?)(?=Viento:|Tarde/Noche|$)',b,re.S|re.I);ev=re.search(r'Tarde/Noche\s+(.*?)(?=Viento:|$)',b,re.S|re.I);wi=re.findall(r'Viento:\s*(.*?)(?=\n|$)',b,re.I);days.append({'date':m.group(0),'min':tm.group(1) if tm else '—','max':tm.group(2) if tm else '—','morning':re.sub(r'\s+',' ',am.group(1)).strip() if am else 'Sin detalle','evening':re.sub(r'\s+',' ',ev.group(1)).strip() if ev else 'Sin detalle','wind':re.sub(r'\s+',' ',wi[-1]).strip() if wi else '—','rain':'Precipitaciones' if re.search('precipit',b,re.I) else 'No indicada'})
if not days: raise SystemExit('No se pudo interpretar el pronóstico de INUMET')
t=days[0];parts=[]
if t['min']!='—':parts.append(f"Temperaturas de {t['min']}° a {t['max']}°")
if re.search('precipit|lluvia|chaparr',t['morning']+' '+t['evening'],re.I):parts.append('con posibilidad de precipitaciones')
if re.search('viento|ráfaga',t['wind'],re.I):parts.append('y viento a tener en cuenta')
data={'updated':datetime.now().strftime('%d/%m/%Y %H:%M'),'days':days,'summary':'; '.join(parts)+'.'}
json.dump(data,open('data.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
