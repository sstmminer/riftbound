import argparse, importlib.util, json, tempfile, unittest
from pathlib import Path
SPEC=importlib.util.spec_from_file_location('sync',Path(__file__).resolve().parents[1]/'scripts/sync.py')
m=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(m)

class SyncTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
  args=argparse.Namespace(delay=.5,mapping=None,errata_reviewed=None,sample_size=3,max_pages=5,browser=False)
  self.a=m.Archive(self.root,args)
 def tearDown(self): self.a.db.close(); self.temp.cleanup()
 def card(self,id='official-print-1'):
  return dict(cardId=id,cardName='Fixture only',setCode='TEST',collectorNumber='001',cardType='Unit',rarity='Rare',domains=['Body'],cost=0,power=3,rulesText='<b>Fixture</b>',imageUrl='https://assets.riotgames.com/fixture.png')
 def test_distinct_printings_and_conflicts(self):
  self.a.ingest({'nested':[self.card(),self.card('official-print-2')]},m.GALLERY)
  self.a.ingest(self.card(),m.GALLERY)
  altered=self.card(); altered['imageUrl']='https://assets.riotgames.com/other.png'; self.a.ingest(altered,m.GALLERY)
  self.assertEqual(self.a.db.execute('SELECT COUNT(*) FROM cards').fetchone()[0],2)
  self.assertEqual(len(self.a.conflicts),1)
  row=self.a.db.execute('SELECT * FROM cards LIMIT 1').fetchone()
  self.assertEqual(row['cost'],'0'); self.assertEqual(row['printed_rules_text'],'Fixture')
  self.assertIsNone(row['effective_rules_text'])
 def test_source_record_and_roundtrip(self):
  self.a.client.record(m.GALLERY,'gallery',b'{"fixture":true}',200,None)
  self.a.client.record(m.GALLERY,'gallery',b'',403,'denied')
  source=self.a.db.execute('SELECT * FROM sources').fetchone()
  self.assertTrue(source['local_path']); self.assertEqual(source['status'],403)
  self.a.ingest(self.card(),m.GALLERY)
  self.a.db.execute('INSERT INTO runs(run_id) VALUES (?)',('test',))
  report=m.export_validate(self.a,'test')
  self.assertEqual(report['counts']['cards'],1); self.assertEqual(report['sqlite_integrity'],'ok')
  self.assertEqual(report['images_success'],0); self.assertFalse(report['completeness_verified'])
 def test_announcement_preserves_unparsed_text(self):
  def get(url,*a):
   return (b'<html><h1>Official announcement fixture</h1><p>Changed text needing review.</p></html>','text/html')
  self.a.client.get=get; self.a.errata()
  self.assertEqual(self.a.db.execute('SELECT COUNT(*) FROM errata').fetchone()[0],5)
  self.assertEqual(self.a.db.execute('SELECT COUNT(*) FROM errata WHERE revised_text IS NOT NULL').fetchone()[0],0)
 def test_official_labeled_errata_and_printings(self):
  fixture=self.card(); fixture['cardName']='Card'; fixture['subtitle']='Identity'
  self.a.ingest(fixture,m.GALLERY)
  fixture['cardId']='official-print-2'; self.a.ingest(fixture,m.GALLERY)
  body=b'<h1>Origins Cards</h1><h2>Card, Identity</h2><p>[NEW TEXT]</p><p>Corrected text.</p><p>\xe2\x96\xb2</p><p>[OLD TEXT]</p><p>Printed text.</p><h2>Related Articles</h2>'
  self.a.db.execute('INSERT INTO errata(errata_id,announcement_url,extraction_status) VALUES (?,?,?)',(m.digest(m.ERRATA[0]),m.ERRATA[0],'unparsed_official_announcement'))
  self.a.parse_announcement(m.ERRATA[0],body,'2026-01-01T00:00:00Z')
  self.a.apply_effective()
  rows=self.a.db.execute('SELECT printed_rules_text,effective_rules_text FROM cards').fetchall()
  self.assertEqual(len(rows),2)
  for row in rows:
   self.assertEqual(row[0],'Fixture');self.assertEqual(row[1],'Corrected text.')
  self.assertEqual(self.a.db.execute("SELECT COUNT(*) FROM errata WHERE extraction_status='official_labeled_text'").fetchone()[0],2)
 def test_invalid_image_not_accepted(self):
  self.assertIsNone(m.image_extension(b'<html>Access denied</html>'))
  self.assertEqual(m.image_extension(b'\x89PNG\r\n\x1a\nfixture'),'.png')

if __name__=='__main__': unittest.main()
