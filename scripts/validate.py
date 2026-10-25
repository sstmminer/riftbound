#!/usr/bin/env python3
"""Read-only validation of the archive; writes data/validation.json."""
import collections, csv, hashlib, json, sqlite3, struct, sys, zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def image_check(data):
 if data.startswith(b'\x89PNG\r\n\x1a\n'):
  p=8; dims=None; ended=False
  while p+12<=len(data):
   n=struct.unpack('>I',data[p:p+4])[0]; tag=data[p+4:p+8]; payload=data[p+8:p+8+n]
   if p+12+n>len(data): raise ValueError('Truncated PNG chunk')
   expected=struct.unpack('>I',data[p+8+n:p+12+n])[0]
   if zlib.crc32(tag+payload)&0xffffffff!=expected: raise ValueError('PNG CRC mismatch')
   if tag==b'IHDR': dims=struct.unpack('>II',payload[:8])
   p+=12+n
   if tag==b'IEND': ended=True; break
  if not ended or not dims: raise ValueError('Missing PNG header/end')
  return dims
 if data.startswith(b'\xff\xd8\xff'):
  if not data.rstrip().endswith(b'\xff\xd9'): raise ValueError('Truncated JPEG')
  return None
 if data[:4]==b'RIFF' and data[8:12]==b'WEBP':
  if len(data)!=struct.unpack('<I',data[4:8])[0]+8: raise ValueError('Truncated WebP')
  return None
 if data[:6] in (b'GIF87a',b'GIF89a'):
  if not data.endswith(b';'): raise ValueError('Truncated GIF')
  return struct.unpack('<HH',data[6:10])
 if data[4:8]==b'ftyp' and b'avif' in data[8:32]: return None
 raise ValueError('Unknown image format')
def main():
 db=sqlite3.connect(ROOT/'data/riftbound.sqlite'); db.row_factory=sqlite3.Row
 errors=[]; integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
 if integrity!='ok':errors.append({'kind':'sqlite','result':integrity})
 fk=[list(r) for r in db.execute('PRAGMA foreign_key_check')]
 if fk:errors.append({'kind':'foreign_keys','rows':fk})
 exports={}
 for table in ('cards','errata','sources','download_log'):
  rows=[dict(r) for r in db.execute('SELECT * FROM '+table)]
  actual=json.loads((ROOT/'data'/f'{table}.json').read_text('utf-8'))
  if rows!=actual:errors.append({'kind':'json_mismatch','table':table})
  with (ROOT/'data'/f'{table}.csv').open(encoding='utf-8-sig',newline='') as f: csvrows=list(csv.DictReader(f))
  if len(csvrows)!=len(rows):errors.append({'kind':'csv_count','table':table})
  else:
   for row,parsed in zip(rows,csvrows):
    if any(parsed[k] != ('' if v is None else str(v)) for k,v in row.items()):
     errors.append({'kind':'csv_values','table':table});break
  exports[table]=len(rows)
 cards=[dict(r) for r in db.execute('SELECT * FROM cards')]
 ids=[r['official_card_id'] for r in cards]
 if len(ids)!=len(set(ids)):errors.append({'kind':'duplicate_ids'})
 success=0; byte_count=0; dimensions=collections.Counter(); missing=[]
 for card in cards:
  rel=card['local_image_path']; path=ROOT/rel if rel else None
  if not path or not path.is_file():missing.append(card['official_card_id']);continue
  try:
   data=path.read_bytes(); dims=image_check(data); byte_count+=len(data)
   log=db.execute("SELECT sha256 FROM download_log WHERE card_id=? AND status='success' ORDER BY log_id DESC LIMIT 1",(card['official_card_id'],)).fetchone()
   if not log or hashlib.sha256(data).hexdigest()!=log[0]:raise ValueError('File does not match recorded SHA256')
   if dims:
    dimensions[f'{dims[0]}x{dims[1]}']+=1
    if card['image_width'] and card['image_height']:
     if dims!=(int(card['image_width']),int(card['image_height'])):raise ValueError('Dimensions differ from official source metadata')
   success+=1
  except Exception as e:errors.append({'kind':'image_invalid','card_id':card['official_card_id'],'error':str(e)})
  if (success+len(errors))%200==0: print('Validated images:',success,flush=True)
 if missing:errors.append({'kind':'missing_images','ids':missing})
 results={'sqlite_integrity':integrity,'foreign_key_errors':fk,'export_counts':exports,
 'duplicate_card_ids':len(ids)-len(set(ids)),'images_checked':success,'image_bytes':byte_count,
 'image_dimensions':dict(dimensions),'errors':errors,'validation_passed':not errors,
 'scope':'File/database consistency only; does not certify complete official coverage or semantic errata correctness.'}
 (ROOT/'data/validation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
 db.close();print(json.dumps(results,ensure_ascii=False,indent=2));return 0 if not errors else 2
if __name__=='__main__':sys.exit(main())
