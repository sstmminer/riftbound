#!/usr/bin/env python3
"""Build a fully self-contained offline HTML catalogue (no HTTP server needed)."""
import json, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 db=sqlite3.connect(ROOT/'data/riftbound.sqlite'); db.row_factory=sqlite3.Row
 fields='official_card_id,name,set_code,set_name,collector_number,card_type,rarity,domains,cost,power,power_cost,tags,printed_rules_text,effective_rules_text,errata_status,image_url,local_image_path'
 cards=[dict(r) for r in db.execute('SELECT '+fields+' FROM cards ORDER BY set_code,collector_number,official_card_id')]
 errata=[dict(r) for r in db.execute('SELECT official_card_id,original_text,revised_text,announcement_url,announcement_date FROM errata WHERE official_card_id IS NOT NULL')]; db.close()
 payload=json.dumps({'cards':cards,'errata':errata},ensure_ascii=False).replace('<','\\u003c')
 page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Riftbound 离线卡牌资料库</title>
<style>body{font:16px system-ui;background:#111a22;color:#e8edf2;margin:0;padding:24px}header{max-width:1200px;margin:auto}h1{font-size:26px}input,select,button{font:inherit;padding:10px;margin:4px;border-radius:6px;border:1px solid #678;background:#1b2a36;color:inherit}input{width:min(440px,85%)}#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:18px;max-width:1500px;margin:24px auto}article{background:#1b2a36;padding:14px;border-radius:10px}img{width:100%;height:350px;object-fit:contain}h2{font-size:19px}pre{white-space:pre-wrap;font:14px system-ui;line-height:1.5}small{color:#b7c8d8}a{color:#97d2ff}details{margin-top:12px}footer{text-align:center}</style>
<header><h1>Riftbound 离线卡牌资料库</h1><p>本页不发出网络请求。官方图片与文本版权归权利人。收录范围和未解决项目见 README 与 manifest。</p><p>图鉴快照文本与公告修订文本分别显示；未知项保持空缺。图片属于原始印刷版本，可能包含已勘误文本。</p><input id="q" type="search" placeholder="搜索卡名、印刷 ID、规则文本"><select id="set"><option value="">全部系列</option></select><button id="prev">上一页</button><button id="next">下一页</button><p id="status"></p></header><main id="grid"></main><footer><p>全部内容来自本地文件。查看官方公告链接需联网。</p></footer><script type="application/json" id="archive-data">PAYLOAD</script><script>
const data=JSON.parse(document.getElementById('archive-data').textContent), all=data.cards;
const sel=document.getElementById('set'), q=document.getElementById('q'),grid=document.getElementById('grid');let page=0;
for(const s of [...new Set(all.map(c=>c.set_code||'_unknown'))].sort()){const o=document.createElement('option');o.value=s;o.textContent=s;sel.append(o)}
function el(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n}
function render(){const query=q.value.toLocaleLowerCase();const rows=all.filter(c=>(!sel.value||(c.set_code||'_unknown')===sel.value)&&JSON.stringify([c.name,c.official_card_id,c.printed_rules_text,c.effective_rules_text]).toLocaleLowerCase().includes(query));const pages=Math.max(1,Math.ceil(rows.length/60));page=Math.min(page,pages-1);grid.replaceChildren();document.getElementById('status').textContent=`找到 ${rows.length} 条印刷记录 · 第 ${page+1}/${pages} 页`;document.getElementById('prev').disabled=page===0;document.getElementById('next').disabled=page+1>=pages;
for(const c of rows.slice(page*60,(page+1)*60)){const a=el('article');if(c.local_image_path){const im=el('img');im.src=c.local_image_path;im.alt=c.name;im.loading='lazy';a.append(im)}else a.append(el('p','图片缺失'));a.append(el('h2',c.name),el('small',`${c.official_card_id} · ${c.set_name||'?'} · ${c.rarity||'?'}`),el('p',`能量 ${c.cost??'—'} / 符能 ${c.power_cost??'—'} / 力量 ${c.power??'—'}`));const d=el('details');d.append(el('summary','规则文本与勘误'));d.append(el('h3','图鉴快照文本'),el('pre',c.printed_rules_text??'未提供'),el('h3','最新已关联生效文本'),el('pre',c.effective_rules_text??'未确定；查阅勘误公告'),el('small',c.errata_status));for(const e of data.errata.filter(e=>e.official_card_id===c.official_card_id)){d.append(el('h4',e.announcement_date||'发布日期未核实'),el('pre','公告旧文本：\n'+(e.original_text??'未提供')),el('pre','公告修订文本：\n'+(e.revised_text??'未提供')));const link=el('a','官方公告（联网）');link.href=e.announcement_url;link.rel='noreferrer';d.append(link)}a.append(d);grid.append(a)}}
q.addEventListener('input',()=>{page=0;render()});sel.addEventListener('change',()=>{page=0;render()});document.getElementById('prev').onclick=()=>{page--;render()};document.getElementById('next').onclick=()=>{page++;render()};render();</script></html>'''
 # Replace escaped line breaks in JS string literals with literal backslash-n sequences.
 page=page.replace("'公告旧文本：\n'", "'公告旧文本：\\n'").replace("'公告修订文本：\n'", "'公告修订文本：\\n'")
 (ROOT/'index.html').write_text(page.replace('PAYLOAD',payload),encoding='utf-8')
 print('Offline viewer:',ROOT/'index.html')
if __name__=='__main__': main()
