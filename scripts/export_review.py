"""Export uncertain Bible citations for explicit human correction."""
import csv,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    db=sqlite3.connect(ROOT/'data/library.sqlite3');db.row_factory=sqlite3.Row
    with (ROOT/'data/bible-reference-review.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['id','passage_id','raw_reference','book_code','chapter','verse_start','verse_end','translation','status','context'])
        for r in db.execute("SELECT r.*,p.text FROM bible_references r JOIN passages p ON p.id=r.passage_id WHERE r.status!='validated'"):
            w.writerow([r[k] for k in ['id','passage_id','raw_reference','book_code','chapter','verse_start','verse_end','translation','status','text']])
    print('Exported Bible reference review queue')
