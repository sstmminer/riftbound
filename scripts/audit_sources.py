#!/usr/bin/env python3
"""Summarize the cached official gallery's actual exposed scope, without network."""
import json, sqlite3
from pathlib import Path
import sync
ROOT=Path(__file__).resolve().parents[1]
def main():
 db=sqlite3.connect(ROOT/'data/riftbound.sqlite');db.row_factory=sqlite3.Row
 source=db.execute('SELECT * FROM sources WHERE url=?',(sync.GALLERY,)).fetchone()
 if not source or not source['local_path']:raise RuntimeError('No successful official gallery snapshot')
 body=(ROOT/source['local_path']).read_bytes()
 if sync.digest(body)!=source['sha256']:raise RuntimeError('Source checksum mismatch')
 page=None
 for script in sync.Document(body.decode('utf-8')).scripts:
  try:
   obj=json.loads(script)
   if isinstance(obj,dict) and 'props' in obj:page=obj
  except ValueError:pass
 if not page:raise RuntimeError('Official page data schema changed; inspect data/raw')
 blades=page['props']['pageProps']['page']['blades']
 gallery=next(b for b in blades if b.get('type')=='riftboundCardGallery')
 items=gallery['cards']['items'];meta=gallery['cards']['async']['metadata']
 ids=[str(v['id']) for v in items if v.get('id')]
 stored={r[0] for r in db.execute('SELECT official_card_id FROM cards')}
 out={'source_url':sync.GALLERY,'source_accessed_at':source['accessed_at'],
  'source_sha256':source['sha256'],'json_path':'props.pageProps.page.blades[type=riftboundCardGallery].cards',
  'embedded_records':len(items),'embedded_unique_print_ids':len(set(ids)),
  'embedded_records_missing_official_id':len(items)-len(ids),
  'embedded_duplicate_ids':len(ids)-len(set(ids)),
  'embedded_ids_not_in_database':sorted(set(ids)-stored),
  'database_ids_not_in_embedded_snapshot':sorted(stored-set(ids)),
  'metadata':meta,'metadata_count_gap':meta['totalItems']-len(set(ids)),
  'embedded_array_coverage_percent':round(100*len(stored&set(ids))/len(set(ids)),2) if ids else None,
  'metadata_count_ratio_percent':round(100*len(set(ids))/meta['totalItems'],2) if meta.get('totalItems') else None,
  'sets':gallery['sets']['items'],'filters':gallery['filters'],
  'hinted_pagination':gallery['cards']['async']['linkdata'],
  'pagination_observations':[dict(r) for r in db.execute("SELECT url,status,error FROM sources WHERE kind LIKE 'public_gallery_api%'")],
  'unmatched_errata':[dict(r) for r in db.execute("SELECT card_name,original_text,revised_text,announcement_url FROM errata WHERE extraction_status='unmatched_official_labeled_text'")],
  'global_completeness_verified':False,
  'notes':['Metadata gap has unknown cause; unknown print IDs cannot be invented.',
   'The gallery exposes no verified canonical cross-printing identity; logical card counts remain null.',
   'All variants present in the public array are retained. Unlisted promotion/printing coverage is unknown.']}
 (ROOT/'data/coverage.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:out[k] for k in ('embedded_records','embedded_array_coverage_percent','metadata_count_gap','metadata_count_ratio_percent')},ensure_ascii=False,indent=2))
 db.close()
if __name__=='__main__':main()
