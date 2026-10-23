"""Import user-supplied Bible JSONL without contacting any third-party service.
Each line: {"translation":"NKJV"|"AVD","book_code":"John","chapter":3,"verse":16,"text":"..."}
"""
import argparse,hashlib,json,sqlite3
from pathlib import Path
from scripts.build_database import BIBLE,CHAPTER_COUNTS

def import_file(path:Path,database:Path):
    codes=dict(zip((b[0] for b in BIBLE),CHAPTER_COUNTS));data=path.read_bytes();records=[]
    for i,line in enumerate(data.decode('utf-8-sig').splitlines(),1):
        if not line.strip():continue
        r=json.loads(line)
        if r['translation'] not in ['NKJV','AVD'] or r['book_code'] not in codes:raise ValueError(f'Invalid translation/book on line {i}')
        if type(r['chapter']) is not int or type(r['verse']) is not int or not 1<=r['chapter']<=codes[r['book_code']] or not 1<=r['verse']<=176 or not isinstance(r['text'],str) or not r['text'].strip():raise ValueError(f'Invalid verse on line {i}')
        records.append(tuple(r[k] for k in ['translation','book_code','chapter','verse','text']))
    if not records:raise ValueError('No verses in file')
    if len(set(r[:4] for r in records))!=len(records):raise ValueError('Duplicate verse keys in file')
    with sqlite3.connect(database) as db:
        # A translation import replaces that translation atomically, avoiding mixed source editions.
        for translation in sorted({r[0] for r in records}):
            db.execute('DELETE FROM bible_verses WHERE translation=?',(translation,))
            db.execute('INSERT OR REPLACE INTO bible_sources VALUES(?,?,?)',(translation,path.name,hashlib.sha256(data).hexdigest()))
            db.execute("UPDATE bible_references SET status='candidate' WHERE translation=? AND status='validated'",(translation,))
        db.executemany('INSERT INTO bible_verses VALUES(?,?,?,?,?)',records)
        for rid,tr,book,ch,start,end in db.execute("SELECT id,translation,book_code,chapter,verse_start,coalesce(verse_end,verse_start) FROM bible_references WHERE status='candidate'").fetchall():
            count=db.execute('SELECT count(*) FROM bible_verses WHERE translation=? AND book_code=? AND chapter=? AND verse BETWEEN ? AND ?',(tr,book,ch,start,end)).fetchone()[0]
            if count==end-start+1:db.execute("UPDATE bible_references SET status='validated' WHERE id=?",(rid,))
        report=json.loads(db.execute("SELECT value FROM metadata WHERE key='extraction_report'").fetchone()[0])
        available=[r[0] for r in db.execute('SELECT translation FROM bible_sources')]
        report['bible_text_status']='Imported: '+', '.join(available)+'. Missing: '+', '.join(t for t in ['AVD','NKJV'] if t not in available)
        report['reference_counts']=dict(db.execute('SELECT status,count(*) FROM bible_references GROUP BY status').fetchall())
        db.execute("UPDATE metadata SET value=? WHERE key='extraction_report'",(json.dumps(report,ensure_ascii=False),))
    (database.parent/'extraction_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(f'Imported {len(records)} verses. Uncertain citations remain flagged.')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('file',type=Path);p.add_argument('--database',type=Path,default=Path(__file__).resolve().parents[1]/'data/library.sqlite3');a=p.parse_args();import_file(a.file,a.database)
