#!/usr/bin/env python3
"""Official-source Riftbound archiver. Never bypasses access controls.
Unknown schemas and ambiguous errata are retained and reported, never invented.
"""
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, html, io, json, re, sqlite3
import sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://playriftbound.com'
GALLERY = BASE + '/en-us/card-gallery/'
RULES = BASE + '/en-us/rules-hub/'
ERRATA = [BASE + '/en-us/news/' + p for p in [
 'rules-and-releases/riftbound-origins-card-errata/',
 'rules-and-releases/riftbound-spiritforged-errata/',
 'rules-and-releases/unleashed-errata-updates/',
 'announcements/vendetta-errata-updates/',
 'announcements/radiance-errata-updates/']]
UA = 'RiftboundOfflineArchive/1.0 (personal archival; robots compliant)'
SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS sources (
 source_id TEXT PRIMARY KEY,url TEXT UNIQUE NOT NULL,kind TEXT,accessed_at TEXT,
 last_checked_at TEXT,status INTEGER,sha256 TEXT,local_path TEXT,error TEXT,
 discovered_from TEXT);
CREATE TABLE IF NOT EXISTS cards (
 official_card_id TEXT PRIMARY KEY,name TEXT,set_code TEXT,set_name TEXT,
 collector_number TEXT,card_type TEXT,rarity TEXT,domains TEXT,cost TEXT,power TEXT,
 tags TEXT,printed_rules_text TEXT,effective_rules_text TEXT,errata_status TEXT,
 image_url TEXT,local_image_path TEXT,source_url TEXT,fetched_at TEXT,
 logical_card_id TEXT,raw_record TEXT,missing_fields TEXT);
CREATE TABLE IF NOT EXISTS errata (
 errata_id TEXT PRIMARY KEY,official_card_id TEXT REFERENCES cards(official_card_id),
 card_name TEXT,set_name TEXT,original_text TEXT,revised_text TEXT,announcement_url TEXT,
 announcement_date TEXT,last_checked_at TEXT,extraction_status TEXT,
 raw_announcement_text TEXT,evidence TEXT);
CREATE TABLE IF NOT EXISTS download_log (
 log_id INTEGER PRIMARY KEY AUTOINCREMENT,url TEXT,card_id TEXT,attempted_at TEXT,
 status TEXT,http_status INTEGER,local_path TEXT,sha256 TEXT,bytes INTEGER,error TEXT);
CREATE TABLE IF NOT EXISTS observations (
 observation_id TEXT PRIMARY KEY,official_card_id TEXT,source_url TEXT,
 observed_at TEXT,raw_record TEXT);
CREATE TABLE IF NOT EXISTS runs (
 run_id TEXT PRIMARY KEY,started_at TEXT,finished_at TEXT,status TEXT,report_json TEXT);
'''
ALIASES = {
 'official_card_id':['official_card_id','card_id','cardId','cardID','printing_id','printingId','id','uid','uuid'],
 'power_cost':['power.value.id'],
 'public_code':['publicCode'],
 'subtitle':['subtitle'],
 'image_width':['cardImage.dimensions.width'],
 'image_height':['cardImage.dimensions.height'],
 'logical_card_id':['logical_card_id','oracle_id','oracleId','base_card_id','baseCardId'],
 'name':['card_name','cardName','name','title'],
 'set_code':['set.value.id','set_code','setCode','set.code','expansion.code','cardSet.code'],
 'set_name':['set.value.label','set_name','setName','set.name','expansion.name','cardSet.name','set.title'],
 'collector_number':['collector_number','collectorNumber','card_number','cardNumber','number'],
 'card_type':['card_type','cardType','type','type.name'],
 'rarity':['rarity.value.label','rarity','rarity.name','rarity.title'],
 'domains':['domains','domain','colors','colour'],
 'cost':['energy.value.id','cost','energy_cost','energyCost','energy'],
 'power':['might.value.id','might','strength'], 'tags':['tags.tags','tags','subtypes','traits'],
 'printed_rules_text':['text.richText.body','effect.richText.body','printed_rules_text','rules_text','rulesText','card_text','cardText','ability','text','description'],
 'image_url':['image_url','imageUrl','card_image.url','cardImage.url','card_image','cardImage','image.url','image','art.url'],
}

def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def digest(value): return hashlib.sha256(value if isinstance(value,bytes) else value.encode()).hexdigest()
def dump(value): return json.dumps(value,ensure_ascii=False,sort_keys=True)
def host(url): return (urllib.parse.urlsplit(url).hostname or '').lower()
def official(url):
 h=host(url)
 return h == 'cmsassets.rgpub.io' or h == 'playriftbound.com' or h.endswith('.playriftbound.com') or h == 'riotgames.com' or h.endswith('.riotgames.com') or h.endswith('.contentstack.io')
def safe_url(url):
 p=urllib.parse.urlsplit(url)
 return p.scheme == 'https' and bool(p.hostname) and not p.username and not p.password

def connect(root):
 (root/'data').mkdir(parents=True,exist_ok=True)
 db=sqlite3.connect(root/'data/riftbound.sqlite'); db.row_factory=sqlite3.Row
 db.executescript(SCHEMA)
 existing={r[1] for r in db.execute('PRAGMA table_info(cards)')}
 for column in ('power_cost','public_code','subtitle','image_width','image_height'):
  if column not in existing: db.execute('ALTER TABLE cards ADD COLUMN '+column+' TEXT')
 db.commit(); return db

class Document(HTMLParser):
 def __init__(self,body):
  super().__init__(convert_charrefs=True); self.links=[]; self.images=[]; self.scripts=[]
  self.text=[]; self.in_script=False; self.script=[]; self.skip=0
  self.feed(body)
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='a' and a.get('href'): self.links.append(a['href'])
  if tag=='img':
   self.images.append(a)
  if tag=='script': self.in_script=True; self.script=[]
  if tag in ('style','noscript'): self.skip+=1
  if tag in ('p','div','h1','h2','h3','h4','li','br','section'): self.text.append('\n')
 def handle_endtag(self,tag):
  if tag=='script': self.in_script=False; self.scripts.append(''.join(self.script))
  if tag in ('style','noscript'): self.skip=max(0,self.skip-1)
  if tag in ('p','h1','h2','h3','h4','li','section'): self.text.append('\n')
 def handle_data(self,data):
  if self.in_script: self.script.append(data)
  elif not self.skip: self.text.append(data)
 def plain(self): return re.sub(r'\n[ \t]*\n+', '\n\n',''.join(self.text)).strip()

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl): return None

class Client:
 def __init__(self,root,db,delay):
  self.root,self.db,self.delay=root,db,max(0.5,delay); self.last=0.; self.robots={}; self.errors=[]
 def request(self,url,limit=100*1024*1024):
  if not safe_url(url): raise ValueError('Only public HTTPS URLs without credentials are permitted')
  for attempt in range(3):
   time.sleep(max(0,self.delay-(time.monotonic()-self.last))); self.last=time.monotonic()
   try:
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'*/*'})
    with urllib.request.build_opener(NoRedirect()).open(req,timeout=60) as r:
     final=r.geturl()
     if host(final)!=host(url):
      # A redirect is not permission to evade another host's robots policy.
      self.check_robots(final)
     data=r.read(limit+1)
     if len(data)>limit: raise ValueError('Response exceeds safety limit')
     return data,r.status,r.headers.get('Content-Type',''),final
   except urllib.error.HTTPError as e:
    if e.code in (301,302,303,307,308):
     target=urllib.parse.urljoin(url,e.headers.get('Location',''))
     if not safe_url(target): raise ValueError('Unsafe redirect')
     if target==url or attempt>=2: raise ValueError('Redirect loop/limit')
     if not target.endswith('/robots.txt'): self.check_robots(target)
     url=target; continue
    if e.code in (429,500,502,503,504) and attempt<2:
     retry=e.headers.get('Retry-After','')
     time.sleep(min(60,max(5,int(retry) if retry.isdigit() else 5*(attempt+1)))); continue
    raise
 def check_robots(self,url):
  origin=urllib.parse.urlunsplit(('https',urllib.parse.urlsplit(url).netloc,'','',''))
  if origin not in self.robots:
   robot_url=origin+'/robots.txt'
   try:
    body,status,typ,final=self.request(robot_url,2*1024*1024)
    rp=urllib.robotparser.RobotFileParser(); rp.parse(body.decode('utf-8','replace').splitlines())
    self.record(robot_url,'robots',body,status,None)
    self.robots[origin]=rp
    crawl=rp.crawl_delay(UA) or rp.crawl_delay('*')
    if crawl: self.delay=max(self.delay,float(crawl))
   except urllib.error.HTTPError as e:
    self.record(robot_url,'robots',b'',e.code,None if e.code==404 else str(e))
    if e.code==404: self.robots[origin]=None
    else: raise RuntimeError(f'robots.txt unavailable ({e.code}); stopped for this host') from e
   except Exception as e:
    self.record(robot_url,'robots',b'',None,str(e)); raise RuntimeError(f'Cannot verify robots.txt for {origin}: {e}') from e
  rp=self.robots[origin]
  if rp and not rp.can_fetch(UA,url): raise RuntimeError('Disallowed by robots.txt: '+url)
 def record(self,url,kind,body,status,error,discovered_from=None):
  stamp=now(); rel=None
  if body:
   rel='data/raw/'+digest(url)+('.json' if body.lstrip()[:1] in (b'{',b'[') else '.html')
   path=self.root/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(body)
  self.db.execute('''INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?)
   ON CONFLICT(url) DO UPDATE SET last_checked_at=excluded.last_checked_at,
   accessed_at=CASE WHEN excluded.error IS NULL THEN excluded.accessed_at ELSE sources.accessed_at END,
   status=excluded.status,sha256=COALESCE(excluded.sha256,sources.sha256),
   local_path=COALESCE(excluded.local_path,sources.local_path),error=excluded.error''',
   (digest(url),url,kind,stamp if body else None,stamp,status,digest(body) if body else None,rel,error,discovered_from))
  self.db.commit()
 def get(self,url,kind='page',parent=None):
  try:
   self.check_robots(url); body,status,ctype,final=self.request(url)
   self.record(url,kind,body,status,None,parent); return body,ctype
  except Exception as e:
   self.record(url,kind,b'',getattr(e,'code',None),str(e),parent)
   self.errors.append({'url':url,'kind':kind,'error':str(e)}); return None,None

# All nested records and JSON string wrappers are inspected, without relying on one CMS layout.
def objects(value):
 if isinstance(value,dict):
  yield value
  for child in value.values(): yield from objects(child)
 elif isinstance(value,list):
  for child in value: yield from objects(child)
 elif isinstance(value,str) and value.lstrip().startswith(('{','[')):
  try: yield from objects(json.loads(value))
  except (ValueError,RecursionError): pass

def at(obj,path):
 for part in path.split('.'):
  if not isinstance(obj,dict) or part not in obj: return None
  obj=obj[part]
 return obj

def pick(obj,paths):
 for path in paths:
  value=at(obj,path)
  if value is not None and value!='': return value
 return None

def scalar(value):
 if isinstance(value,(dict,list)): return dump(value)
 return str(value) if value is not None else None

def plain(value):
 if not isinstance(value,str): return scalar(value)
 return html.unescape(re.sub('<[^>]+>','',re.sub(r'<br\s*/?>|</p>', '\n',value,flags=re.I))).strip()

class Archive:
 def __init__(self,root,args):
  self.root,self.args=root,args; self.db=connect(root); self.client=Client(root,self.db,args.delay)
  self.cached_times={}; self.seen=set(); self.discovered=set(); self.candidates=0; self.conflicts=[]; self.rejected=[]
  self.gallery_metadata={}; self.api_visited=set()
  self.mapping=json.loads(Path(args.mapping).read_text('utf-8')) if args.mapping else {}
 def ingest(self,value,url):
  for obj in objects(value):
   fields={k:pick(obj,self.mapping.get(k,v) if isinstance(self.mapping.get(k,v),list) else [self.mapping[k]]) for k,v in ALIASES.items()}
   image=fields['image_url']
   if isinstance(image,dict): image=image.get('url') or image.get('src')
   # Explicit card identity or a collector number + card-specific attributes, not arbitrary CMS titles.
   marker=any(k in obj for k in ('card_id','cardId','cardID','card_name','cardName','collector_number','collectorNumber','card_number','cardNumber','printing_id','printingId'))
   traits=sum(fields[k] is not None for k in ('card_type','rarity','domains','cost','power','printed_rules_text'))
   if not fields['name'] or not image or not (marker or traits>=2): continue
   self.candidates+=1
   cid=scalar(fields['official_card_id'])
   if not cid:
    # No name-only identity. A printed set/number is an acceptable official printing identifier.
    if fields['set_code'] and fields['collector_number']:
     cid=scalar(fields['set_code'])+':'+scalar(fields['collector_number'])
    else:
     self.rejected.append({'source':url,'reason':'missing official ID and set/collector number','record':obj}); continue
   image=urllib.parse.urljoin(url,str(image))
   if not safe_url(image):
    self.rejected.append({'source':url,'reason':'invalid image URL','record':obj}); continue
   record={k:scalar(v) for k,v in fields.items()}; record['official_card_id']=cid
   record['image_url']=image
   if isinstance(fields['card_type'],dict): record['card_type']=dump([v['label'] for v in fields['card_type'].get('type',[])])
   if isinstance(fields['domains'],dict): record['domains']=dump([v['label'] for v in fields['domains'].get('values',[])])
   record['printed_rules_text']=plain(fields['printed_rules_text'])
   record['name']=plain(fields['name']) + (', '+str(obj['subtitle']) if obj.get('subtitle') else ''); record['source_url']=url; record['fetched_at']=self.cached_times.get(url) or now()
   record['raw_record']=dump(obj); record['local_image_path']=None
   record['errata_status']='not_checked'; record['effective_rules_text']=None
   record['missing_fields']=dump([k for k in ALIASES if k!='logical_card_id' and record.get(k) is None])
   observation=digest(cid+'\n'+url+'\n'+dump(obj))
   self.db.execute('INSERT OR IGNORE INTO observations VALUES (?,?,?,?,?)',(observation,cid,url,now(),dump(obj)))
   old=self.db.execute('SELECT * FROM cards WHERE official_card_id=?',(cid,)).fetchone()
   if old:
    # Conflicting identity/image may represent another printing: never silently collapse it.
    if (old['name']!=record['name'] and json.loads(old['raw_record']).get('name')!=obj.get('name')) or old['image_url']!=image:
     self.conflicts.append({'id':cid,'old_name':old['name'],'new_name':record['name'],'old_image':old['image_url'],'new_image':image,'source':url})
     continue
    record['local_image_path']=old['local_image_path']
    for k in record:
     if record[k] is None and k in old.keys(): record[k]=old[k]
   keys=list(record)
   self.db.execute('INSERT INTO cards ('+','.join(keys)+') VALUES ('+','.join('?' for _ in keys)+') ON CONFLICT(official_card_id) DO UPDATE SET '+','.join(k+'=excluded.'+k for k in keys if k!='official_card_id'),[record[k] for k in keys])
   self.seen.add(cid); self.db.commit()
 def inspect_page(self,url,body,ctype):
  text=body.decode('utf-8','replace')
  try:
   value=json.loads(text); self.ingest(value,url); self.public_lists(value,url); return []
  except ValueError: pass
  doc=Document(text)
  for script in doc.scripts:
   try:
    value=json.loads(script); self.ingest(value,url); self.public_lists(value,url)
   except (ValueError,RecursionError):
    # Next.js flight records contain JSON arrays, some containing nested serialized data.
    for match in re.finditer(r'self\.__next_f\.push\((.*?)\)\s*;?',script,re.S):
     try: self.ingest(json.loads(match.group(1)),url)
     except (ValueError,RecursionError): pass
  # Discover public JSON payload URLs only when explicitly present in the official document.
  payloads=re.findall(r'(?:https://[^\s"<>\\]+|/[^\s"<>\\]+)\.json(?:\?[^\s"<>\\]*)?',text)
  for raw in payloads:
   endpoint=urllib.parse.urljoin(url,html.unescape(raw))
   if official(endpoint) and endpoint not in self.discovered:
    self.discovered.add(endpoint)
    data,ct=self.client.get(endpoint,'public_json',url)
    if data:
     try: self.ingest(json.loads(data),endpoint)
     except ValueError: pass
  return [urllib.parse.urljoin(url,x) for x in doc.links]
 def public_lists(self,value,parent):
  for ob in objects(value):
   async_data=ob.get('async')
   if not isinstance(async_data,dict): continue
   meta=async_data.get('metadata',{}); links=async_data.get('linkdata',{})
   if meta.get('smartListMachineName')=='riftbound_gallery_cards': self.gallery_metadata=meta
   for key in ('first','next'):
    raw=links.get(key)
    if not raw: continue
    url=urllib.parse.urljoin(parent,raw)
    if host(url)!=host(GALLERY) or url in self.api_visited: continue
    if len(self.api_visited)>=self.args.max_pages:
     self.client.errors.append({'kind':'api_pagination','error':'max-pages reached','url':url}); continue
    self.api_visited.add(url)
    body,ct=self.client.get(url,'public_gallery_api',parent)
    if body:
     try:
      result=json.loads(body); self.ingest(result,url); self.public_lists(result,url)
     except ValueError as e: self.client.errors.append({'kind':'api_json','url':url,'error':str(e)})
 def gallery(self):
  queue=[GALLERY]; visited=set()
  while queue:
   url=queue.pop(0)
   if url in visited: continue
   if len(visited)>=self.args.max_pages:
    self.client.errors.append({'kind':'pagination','error':'max-pages reached','remaining':queue+[url]}); break
   visited.add(url)
   body,ct=self.client.get(url,'gallery')
   if not body: continue
   links=self.inspect_page(url,body,ct)
   for link in links:
    p=urllib.parse.urlsplit(link)
    if host(link)==host(GALLERY) and '/en-us/card-gallery/' in p.path:
     clean=urllib.parse.urlunsplit((p.scheme,p.netloc,p.path,p.query,''))
     if clean not in visited and clean not in queue: queue.append(clean)
  if self.args.browser and self.seen is not None: self.browser()
 def browser(self):
  try: from playwright.sync_api import sync_playwright
  except ImportError:
   self.client.errors.append({'kind':'browser','error':'Install playwright and run: python -m playwright install chromium'}); return
  try:
   self.client.check_robots(GALLERY)
   with sync_playwright() as p:
    browser=p.chromium.launch(headless=True); context=browser.new_context(user_agent=UA)
    page=context.new_page(); captures=[]; policy_errors=set()
    def route_handler(route):
     u=route.request.url
     if u.startswith(('data:','blob:')): route.continue_(); return
     try:
      self.client.check_robots(u)
      time.sleep(self.client.delay)
      route.continue_()
     except Exception as e:
      policy_errors.add((u,str(e))); route.abort()
    context.route('**/*',route_handler)
    def response_handler(response):
     try:
      if official(response.url) and response.status==200 and 'json' in response.headers.get('content-type',''):
       captures.append((response.url,response.body()))
     except Exception: pass
    page.on('response',response_handler)
    response=page.goto(GALLERY,wait_until='domcontentloaded',timeout=90000)
    if response and response.status in (401,403,429): raise RuntimeError(f'Browser access denied: HTTP {response.status}; no bypass attempted')
    # Normal UI only; no challenge solving, hidden endpoint guessing or authentication.
    stable=0; previous=None
    for _ in range(self.args.max_pages):
     page.wait_for_timeout(2000)
     content=page.content(); self.inspect_page(GALLERY,content.encode(),'text/html')
     while captures:
      url,body=captures.pop(0)
      self.client.record(url,'browser_public_json',body,200,None,GALLERY)
      try: self.ingest(json.loads(body),url)
      except ValueError: pass
     signature=digest(content)
     stable=stable+1 if signature==previous else 0; previous=signature
     # Common accessible paging controls; explicit filters are audited in browser_controls.json.
     buttons=page.get_by_role('button',name=re.compile(r'^(load more|show more|next|next page)$',re.I))
     clicked=False
     for i in range(buttons.count()):
      b=buttons.nth(i)
      if b.is_visible() and b.is_enabled(): b.click(); clicked=True; break
     if not clicked:
      page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
      if stable>=2: break
    controls=page.locator('select, [role="tab"], [role="combobox"]').evaluate_all('(els) => els.map(e => ({tag:e.tagName,text:e.innerText,label:e.getAttribute("aria-label")}))')
    (self.root/'data/browser_controls.json').write_text(dump(controls),encoding='utf-8')
    if controls: self.client.errors.append({'kind':'coverage_review','error':'Gallery filters found. Review browser_controls.json; pass public filter/page URLs through --extra-gallery-url if not embedded in payload.'})
    for u,error in policy_errors: self.client.errors.append({'url':u,'kind':'browser_resource','error':error})
    browser.close()
  except Exception as e: self.client.errors.append({'kind':'browser','url':GALLERY,'error':str(e)})
 def errata(self):
  urls=list(ERRATA); body,ct=self.client.get(RULES,'rules_hub')
  if body:
   doc=Document(body.decode('utf-8','replace'))
   for href in doc.links:
    url=urllib.parse.urljoin(RULES,href).rstrip('/')+'/'
    if host(url)==host(BASE) and ('errata' in url.lower() or 'card-update' in url.lower()):
     if url not in urls: urls.append(url)
  for url in urls:
   body,ct=self.client.get(url,'errata',RULES)
   if not body: continue
   doc=Document(body.decode('utf-8','replace')); raw=doc.plain(); date=None
   # Only published date from structured data, never infer it from crawl date or URL.
   for script in doc.scripts:
    try:
     for obj in objects(json.loads(script)):
      if obj.get('datePublished'): date=str(obj['datePublished'])
    except ValueError: pass
   eid=digest(url)
   self.db.execute('''INSERT INTO errata VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(errata_id) DO UPDATE SET last_checked_at=excluded.last_checked_at,
    raw_announcement_text=excluded.raw_announcement_text,announcement_date=excluded.announcement_date''',
    (eid,None,None,None,None,None,url,date,now(),'unparsed_official_announcement',raw,None))
   self.db.commit()
   self.parse_announcement(url,body,date)
  # Never turn prose into authoritative per-card corrections using an uncertain heuristic.
  # Human-reviewed structured mappings can be supplied with exact official evidence.
  if self.args.errata_reviewed:
   reviewed=json.loads(Path(self.args.errata_reviewed).read_text('utf-8'))
   for item in reviewed:
    required=('official_card_id','announcement_url','revised_text','evidence')
    if any(not item.get(k) for k in required): raise ValueError('Reviewed errata missing required fields: '+str(required))
    source=self.db.execute('SELECT * FROM sources WHERE url=? AND error IS NULL',(item['announcement_url'],)).fetchone()
    ann=self.db.execute('SELECT * FROM errata WHERE announcement_url=? AND raw_announcement_text IS NOT NULL',(item['announcement_url'],)).fetchone()
    card=self.db.execute('SELECT * FROM cards WHERE official_card_id=?',(item['official_card_id'],)).fetchone()
    if not source or not ann or not card: raise ValueError('Reviewed errata must refer to a fetched official announcement and existing card')
    norm=lambda s: re.sub(r'\s+',' ',s).strip()
    if norm(item['evidence']) not in norm(ann['raw_announcement_text']): raise ValueError('Errata evidence not found in official announcement')
    if norm(item['revised_text']) not in norm(ann['raw_announcement_text']): raise ValueError('Revised text not found verbatim in official announcement')
    eid=digest(item['official_card_id']+'\n'+item['announcement_url']+'\n'+item['revised_text'])
    self.db.execute('INSERT OR REPLACE INTO errata VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
     (eid,item['official_card_id'],card['name'],card['set_name'],item.get('original_text'),item['revised_text'],item['announcement_url'],ann['announcement_date'],now(),'reviewed',None,item['evidence']))
  self.apply_effective()
 def apply_effective(self):
  for card in self.db.execute('SELECT official_card_id,printed_rules_text FROM cards').fetchall():
   corrections=self.db.execute("SELECT * FROM errata WHERE official_card_id=? AND extraction_status IN ('reviewed','official_labeled_text')",(card[0],)).fetchall()
   if len(corrections)==1: effective=corrections[0]['revised_text']; status='official_errata_labeled'
   elif len(corrections)>1:
    dated=[x for x in corrections if x['announcement_date']]
    if len(dated)==len(corrections) and len({x['announcement_date'] for x in dated})==len(dated):
     effective=sorted(dated,key=lambda x:x['announcement_date'])[-1]['revised_text']; status='official_errata_labeled'
    else: effective=None; status='multiple_errata_need_review'
   else:
    unresolved=self.db.execute("SELECT COUNT(*) FROM errata WHERE extraction_status='unparsed_official_announcement'").fetchone()[0]
    unavailable=self.db.execute("SELECT COUNT(*) FROM sources WHERE kind IN ('errata','rules_hub') AND error IS NOT NULL").fetchone()[0]
    effective=None if unresolved or unavailable else card['printed_rules_text']
    status='errata_check_incomplete' if unresolved or unavailable else 'no_official_errata_found'
   self.db.execute('UPDATE cards SET effective_rules_text=?,errata_status=? WHERE official_card_id=?',(effective,status,card[0]))
  self.db.commit()
 def parse_announcement(self,url,body,date):
  text=body.decode('utf-8','replace')
  self.db.execute("DELETE FROM errata WHERE announcement_url=? AND extraction_status IN ('official_labeled_text','unmatched_official_labeled_text')",(url,))
  # These published pages use named headings and explicit NEW TEXT / OLD TEXT labels.
  heads=[]
  for match in re.finditer(r'<h[1-6]\b[^>]*>(.*?)</h[1-6]>',text,re.S|re.I):
   title=plain(match.group(1)).strip()
   if title and title not in ('▲','[NEW TEXT]','[OLD TEXT]'):
    heads.append((match.start(),match.end(),title))
  section='Origins' if 'origins-card-errata' in url else None
  matched=0; sections=0; unresolved=[]
  norm=lambda value: re.sub(r'[^a-z0-9]','',value.casefold())
  cards=self.db.execute('SELECT * FROM cards').fetchall()
  for i,(start,end,title) in enumerate(heads):
   if title=='Related Articles': break
   if title.endswith(' Cards'): section=title[:-6]; continue
   chunk=text[end:heads[i+1][0] if i+1<len(heads) else len(text)]
   prose=Document(chunk).plain()
   if '[NEW TEXT]' not in prose: continue
   sections+=1
   match=re.search(r'\[NEW TEXT\](.*?)\[OLD TEXT\](.*)',prose,re.S)
   if not match: unresolved.append({'title':title,'reason':'missing paired NEW/OLD labels'}); continue
   revised=match.group(1).strip().rstrip('▲').strip(); original=match.group(2).strip()
   candidates=[c for c in cards if norm(c['name'])==norm(title)]
   if not candidates:
    fallback=[c for c in cards if norm(json.loads(c['raw_record']).get('name',''))==norm(title)]
    if len({norm(c['name']) for c in fallback})==1: candidates=fallback
   # Errata apply to the named rules identity, including its gallery alternate printings.
   if not candidates:
    unresolved.append({'title':title,'reason':'no exact normalized name match'})
    candidates=[None]
   for card in candidates:
    cid=card['official_card_id'] if card else None
    eid=digest(url+'\n'+(cid or title)+'\n'+revised)
    self.db.execute('INSERT OR REPLACE INTO errata VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
     (eid,cid,title,section,original,revised,url,date,now(),
      'official_labeled_text' if card else 'unmatched_official_labeled_text',None,prose))
    if card: matched+=1
  labels=text.count('[NEW TEXT]')
  if sections and not unresolved:
   self.db.execute("UPDATE errata SET extraction_status='parsed_announcement' WHERE errata_id=?",(digest(url),))
  else:
   self.client.errors.append({'kind':'errata_parse','url':url,'sections':sections,'unresolved':unresolved,'html_label_occurrences':labels})
  self.db.commit()
 def offline_rebuild(self):
  sources=self.db.execute("SELECT * FROM sources WHERE error IS NULL AND local_path IS NOT NULL").fetchall()
  for source in sources:
   path=self.root/source['local_path']
   if not path.is_file():
    self.client.errors.append({'kind':'missing_cached_source','url':source['url']}); continue
   body=path.read_bytes()
   if digest(body)!=source['sha256']:
    self.client.errors.append({'kind':'cached_source_checksum','url':source['url']}); continue
   self.cached_times[source['url']]=source['accessed_at']
   if source['kind'] in ('gallery','public_gallery_api','extra_public_gallery','browser_public_json'):
    text=body.decode('utf-8','replace')
    try: values=[json.loads(text)]
    except ValueError:
     values=[]
     for script in Document(text).scripts:
      try: values.append(json.loads(script))
      except ValueError: pass
    for value in values:
     self.ingest(value,source['url'])
     for obj in objects(value):
      ad=obj.get('async')
      if isinstance(ad,dict) and ad.get('metadata',{}).get('smartListMachineName')=='riftbound_gallery_cards':
       self.gallery_metadata=ad['metadata']
   elif source['kind']=='errata' and source['url'].endswith('/'):
    old=self.db.execute('SELECT announcement_date FROM errata WHERE announcement_url=? LIMIT 1',(source['url'],)).fetchone()
    self.parse_announcement(source['url'],body,old[0] if old else None)
  self.apply_effective()
  # Normalize paths after schema improvements; preserve every original image byte.
  for row in self.db.execute('SELECT * FROM cards WHERE local_image_path IS NOT NULL').fetchall():
   old=self.root/row['local_image_path']
   if not old.is_file(): continue
   folder=re.sub('[^a-zA-Z0-9_.-]','_',row['set_code'] or row['set_name'] or '_unknown')
   rel='images/'+folder+'/'+old.name; new=self.root/rel
   if old!=new:
    new.parent.mkdir(parents=True,exist_ok=True)
    if new.exists() and digest(new.read_bytes())!=digest(old.read_bytes()):
     self.client.errors.append({'kind':'image_path_conflict','card_id':row['official_card_id']}); continue
    if new.exists(): old.unlink()
    else: old.replace(new)
    self.db.execute('UPDATE cards SET local_image_path=? WHERE official_card_id=?',(rel,row['official_card_id']))
  self.db.commit()
 def images(self):
  rows=self.db.execute('SELECT * FROM cards ORDER BY set_code,official_card_id').fetchall()
  # Download a small batch first, validate signatures, then continue all remaining records.
  first=rows[:self.args.sample_size]; rest=rows[self.args.sample_size:]
  failures=0
  for row in first: failures+=not self.image(row)
  if first and failures==len(first):
   self.client.errors.append({'kind':'image_sample','error':'All sample downloads failed; full download paused. Fix cause and rerun.'}); return
  for i,row in enumerate(rest,len(first)+1):
   self.image(row)
   if i%50==0: print(f'Images processed {i}/{len(rows)}',flush=True)
 def image(self,row):
  url=row['image_url']; rel=row['local_image_path']
  if rel and (self.root/rel).is_file():
   data=(self.root/rel).read_bytes()
   if image_extension(data): return True
  try:
   self.client.check_robots(url)
   data,status,ctype,final=self.client.request(url)
   ext=image_extension(data)
   if not ext: raise ValueError('Response is not a supported original card image')
   folder=re.sub('[^a-zA-Z0-9_.-]','_',row['set_code'] or row['set_name'] or '_unknown')
   # Image URL is retained exactly: no thumbnail transformations or invented higher-res URLs.
   rel='images/'+folder+'/'+digest(row['official_card_id'])[:24]+ext
   path=self.root/rel; path.parent.mkdir(parents=True,exist_ok=True)
   temp=path.with_suffix(path.suffix+'.part'); temp.write_bytes(data); temp.replace(path)
   self.db.execute('UPDATE cards SET local_image_path=? WHERE official_card_id=?',(rel,row['official_card_id']))
   self.db.execute('INSERT INTO download_log(url,card_id,attempted_at,status,http_status,local_path,sha256,bytes) VALUES (?,?,?,?,?,?,?,?)',(url,row['official_card_id'],now(),'success',status,rel,digest(data),len(data)))
   self.db.commit(); return True
  except Exception as e:
   self.db.execute('INSERT INTO download_log(url,card_id,attempted_at,status,http_status,error) VALUES (?,?,?,?,?,?)',(url,row['official_card_id'],now(),'failed',getattr(e,'code',None),str(e)))
   self.db.commit(); self.client.errors.append({'kind':'image','url':url,'card_id':row['official_card_id'],'error':str(e)}); return False

def image_extension(data):
 if data.startswith(b'\x89PNG\r\n\x1a\n'): return '.png'
 if data.startswith(b'\xff\xd8\xff'): return '.jpg'
 if data[:4]==b'RIFF' and data[8:12]==b'WEBP': return '.webp'
 if data[:6] in (b'GIF87a',b'GIF89a'): return '.gif'
 if data[4:8]==b'ftyp' and (b'avif' in data[8:32] or b'avis' in data[8:32]): return '.avif'
 return None

def export_validate(archive,run_id):
 root,db=archive.root,archive.db
 counts={}; missing=Counter(); sets=defaultdict(list)
 for table in ('cards','errata','sources','download_log'):
  rows=[dict(r) for r in db.execute('SELECT * FROM '+table)]
  (root/'data'/f'{table}.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
  headers=[r[1] for r in db.execute('PRAGMA table_info('+table+')')]
  with (root/'data'/f'{table}.csv').open('w',encoding='utf-8-sig',newline='') as f:
   writer=csv.DictWriter(f,fieldnames=headers); writer.writeheader(); writer.writerows(rows)
  assert len(json.loads((root/'data'/f'{table}.json').read_text('utf-8')))==len(rows)
  with (root/'data'/f'{table}.csv').open(encoding='utf-8-sig',newline='') as f: assert len(list(csv.DictReader(f)))==len(rows)
  counts[table]=len(rows)
 cards=[dict(r) for r in db.execute('SELECT * FROM cards')]
 good=0; missing_images=[]
 for c in cards:
  sets[c['set_code'] or c['set_name'] or '_unknown'].append(c)
  for key in json.loads(c['missing_fields']): missing[key]+=1
  p=root/c['local_image_path'] if c['local_image_path'] else None
  if p and p.is_file() and image_extension(p.read_bytes()): good+=1
  else: missing_images.append(c['official_card_id'])
 stats=[]
 for name,rows in sorted(sets.items()):
  known={r['logical_card_id'] for r in rows if r['logical_card_id']}
  stats.append({'set':name,'printing_records':len(rows),
   'unique_logical_cards':len(known) if all(r['logical_card_id'] for r in rows) else None,
   'distinct_names_for_reference_only':len({r['name'] for r in rows}),
   'different_printing_versions':len(rows),'distinct_collector_numbers':len({r['collector_number'] for r in rows if r['collector_number'] is not None}),
   'images_success':sum(bool(r['local_image_path'] and (root/r['local_image_path']).is_file()) for r in rows)})
 duplicate=db.execute('SELECT official_card_id,COUNT(*) FROM cards GROUP BY official_card_id HAVING COUNT(*)>1').fetchall()
 integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
 fk=[list(x) for x in db.execute('PRAGMA foreign_key_check')]
 errors=list(archive.client.errors)
 failed_sources=[dict(r) for r in db.execute('SELECT url,kind,status,error,last_checked_at FROM sources WHERE error IS NOT NULL')]
 latest_failures=[dict(r) for r in db.execute("SELECT d.* FROM download_log d JOIN (SELECT card_id,MAX(log_id) AS last_id FROM download_log GROUP BY card_id) l ON d.log_id=l.last_id WHERE d.status='failed'")]
 errors.extend({'kind':'source_unavailable',**r} for r in failed_sources)
 errors.extend({'kind':'identity_conflict',**x} for x in archive.conflicts)
 if archive.rejected: errors.append({'kind':'rejected_candidates','count':len(archive.rejected),'path':'data/rejected_records.json'})
 if not archive.seen: errors.append({'kind':'no_current_cards','error':'No card records discovered in this run. No completeness claim is possible.'})
 unparsed=db.execute("SELECT COUNT(*) FROM errata WHERE extraction_status='unparsed_official_announcement'").fetchone()[0]
 report={'snapshot_at_utc':now(),'run_id':run_id,'counts':counts,'cards_seen_this_run':len(archive.seen),
  'images_success':good,'latest_image_failures':latest_failures,'historical_failed_download_attempts':db.execute("SELECT COUNT(*) FROM download_log WHERE status='failed'").fetchone()[0],'missing_images':missing_images,'field_missing_counts':dict(missing),
  'per_set':stats,'duplicate_ids':len(duplicate),'identity_conflicts':len(archive.conflicts),
  'unparsed_errata_announcements':unparsed,'unmatched_errata': [dict(r) for r in db.execute("SELECT card_name,announcement_url FROM errata WHERE extraction_status='unmatched_official_labeled_text'")],'linked_errata_records':db.execute("SELECT COUNT(*) FROM errata WHERE official_card_id IS NOT NULL").fetchone()[0],'sqlite_integrity':integrity,'foreign_key_errors':fk,
  'json_csv_roundtrip':'passed','completeness_verified':False,'official_gallery_metadata':archive.gallery_metadata,'gallery_visible_record_count':len(archive.seen),'text_provenance':'Gallery-published text retained as printed_rules_text; historical printing fidelity requires image comparison. Errata old/new texts kept separately.',
  'coverage':{'official_total':archive.gallery_metadata.get('totalItems'),'card_coverage_percent':round(100*len(archive.seen)/archive.gallery_metadata['totalItems'],2) if archive.gallery_metadata.get('totalItems') else None,
   'image_coverage_of_stored_records_percent':round(100*good/len(cards),2) if cards else None,
   'reason':'Compare official_gallery_metadata with cards_seen_this_run and source errors. Metadata counts can differ from embedded visible records. Independent logical IDs may be unavailable; unresolved errata remain explicit. Counts alone do not establish full completeness.'},
  'failures':errors,'requested_sources':[GALLERY,RULES]+ERRATA,
  'current_run_discovered_ids':sorted(archive.seen)}
 (root/'data/rejected_records.json').write_text(json.dumps(archive.rejected,ensure_ascii=False,indent=2),encoding='utf-8')
 (root/'data/report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 (root/'data/errors.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2),encoding='utf-8')
 (root/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 db.execute('UPDATE runs SET finished_at=?,status=?,report_json=? WHERE run_id=?',(now(),'incomplete' if errors or unparsed else 'collected_unverified',dump(report),run_id)); db.commit()
 return report

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--root',type=Path,default=ROOT); p.add_argument('--delay',type=float,default=1.5)
 p.add_argument('--browser',action='store_true',help='Use ordinary public Chromium page to capture JSON; never solves challenges')
 p.add_argument('--max-pages',type=int,default=300); p.add_argument('--sample-size',type=int,default=3)
 p.add_argument('--mapping',help='JSON mapping canonical field names to dot-paths or arrays of dot-paths')
 p.add_argument('--errata-reviewed',help='Reviewed, evidence-backed per-card errata JSON')
 p.add_argument('--extra-gallery-url',action='append',default=[],help='Explicit public official gallery filter/page/JSON URL')
 p.add_argument('--offline-rebuild',action='store_true',help='Reparse and validate saved official responses without network access')
 p.add_argument('--init-only',action='store_true',help='Create empty database and exports; does not claim collection')
 args=p.parse_args()
 if args.sample_size<1 or args.max_pages<1: p.error('sample-size and max-pages must be positive')
 archive=Archive(args.root.resolve(),args); run_id=now()
 archive.db.execute('INSERT INTO runs(run_id,started_at,status) VALUES (?,?,?)',(run_id,run_id,'running')); archive.db.commit()
 try:
  if args.offline_rebuild:
   archive.offline_rebuild()
  elif not args.init_only:
   archive.gallery()
   for url in args.extra_gallery_url:
    if not official(url): raise ValueError('Extra data URLs must be an official site/CMS host')
    body,ct=archive.client.get(url,'extra_public_gallery',GALLERY)
    if body: archive.inspect_page(url,body,ct)
   archive.errata(); archive.images()
 except (Exception,KeyboardInterrupt) as e:
  archive.client.errors.append({'kind':'run','error':str(e) or 'interrupted'})
 finally:
  report=export_validate(archive,run_id); archive.db.close()
 print(json.dumps({k:report[k] for k in ('counts','images_success','cards_seen_this_run','completeness_verified','coverage')},ensure_ascii=False,indent=2))
 print('Full report:',args.root/'data/report.json')
 return 2 if report['failures'] or report['unparsed_errata_announcements'] else 0

if __name__=='__main__': sys.exit(main())
