#!/usr/bin/env python3
"""Create a portable ZIP, excluding local Python environments and caches."""
from pathlib import Path
import hashlib, zipfile
ROOT=Path(__file__).resolve().parents[1]
def include(p):
 return p.is_file() and not p.is_symlink() and not any(x in ('.venv','venv','__pycache__','.git') for x in p.relative_to(ROOT).parts) and p.suffix not in ('.pyc','.part','.zip')
def main():
 paths=sorted(p for p in ROOT.rglob('*') if include(p) and p.name!='SHA256SUMS.txt')
 (ROOT/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in paths),encoding='utf-8')
 target=ROOT.parent/(ROOT.name+'.zip')
 with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in sorted(ROOT.rglob('*')):
   if include(p): z.write(p,ROOT.name+'/'+p.relative_to(ROOT).as_posix())
 with zipfile.ZipFile(target) as z:
  bad=z.testzip()
  if bad: raise RuntimeError('Invalid ZIP entry: '+bad)
 print(target)
 print('ZIP SHA256:',hashlib.sha256(target.read_bytes()).hexdigest())
if __name__=='__main__': main()
