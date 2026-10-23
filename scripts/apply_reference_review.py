"""Apply explicitly reviewed reference rows from CSV. Set status=reviewed to accept a row."""
import argparse,csv,sqlite3
from pathlib import Path
from scripts.build_database import BIBLE,CHAPTER_COUNTS
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('file',type=Path);a=p.parse_args();dbpath=Path(__file__).resolve().parents[1]/'data/library.sqlite3';codes=dict(zip([b[0] for b in BIBLE],CHAPTER_COUNTS));n=0
    with sqlite3.connect(dbpath) as db,a.file.open() as f:
        for r in csv.DictReader(f):
            if r['status']!='reviewed':continue
            ch,start,end=int(r['chapter']),int(r['verse_start']),int(r['verse_end'] or r['verse_start'])
            if r['book_code'] not in codes or not 1<=ch<=codes[r['book_code']] or not 1<=start<=end<=176 or r['translation'] not in ['AVD','NKJV']:raise ValueError('Invalid reference')
            if not db.execute('SELECT 1 FROM bible_references WHERE id=? AND passage_id=?',(r['id'],r['passage_id'])).fetchone():raise ValueError('Stale or invalid review row')
            count=db.execute('SELECT count(*) FROM bible_verses WHERE translation=? AND book_code=? AND chapter=? AND verse BETWEEN ? AND ?',(r['translation'],r['book_code'],ch,start,end)).fetchone()[0]
            db.execute('UPDATE bible_references SET book_code=?,chapter=?,verse_start=?,verse_end=?,translation=?,status=?,notation=? WHERE id=?',(r['book_code'],ch,start,end,r['translation'],'validated' if count==end-start+1 else 'candidate','human-reviewed',r['id']));n+=1
    print(f'Applied {n} reviewed references')
