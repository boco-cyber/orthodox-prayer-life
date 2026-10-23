"""Fetch a pinned public-domain Van Dyke edition, keeping source provenance."""
import concurrent.futures,hashlib,json,urllib.request
from pathlib import Path
from scripts.build_database import BIBLE
from scripts.import_bible import import_file
ROOT=Path(__file__).resolve().parents[1]
REVISION='d9fe1779447717bbfcb578e505b893125cad581c'
BASE=f'https://raw.githubusercontent.com/midvash/bible-data/{REVISION}/versions/ar/svd/'
def download(code):
    with urllib.request.urlopen(BASE+'books/'+code+'.json',timeout=30) as r:data=r.read()
    return code,data
if __name__=='__main__':
    metadata=json.load(urllib.request.urlopen(BASE+'metadata.json',timeout=30))
    if metadata['license']!='public-domain':raise ValueError('Unexpected source license')
    raw=ROOT/'data/bible-source/ar-vandyke';raw.mkdir(parents=True,exist_ok=True)
    entries=[];hashes={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for code,data in pool.map(download,[b[0] for b in BIBLE]):
            (raw/(code+'.json')).write_bytes(data);hashes[code]=hashlib.sha256(data).hexdigest();book=json.loads(data)
            if book['book']!=code:raise ValueError('Wrong book')
            for ch in book['chapters']:
                for v in ch['verses']:entries.append({'translation':'AVD','book_code':code,'chapter':ch['chapter'],'verse':v['number'],'text':v['text']})
    if len(entries)!=metadata['stats']['verses']:raise ValueError('Incomplete Bible download')
    (raw/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    target=ROOT/'data/arabic-vandyke.jsonl';target.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in entries)+'\n')
    (ROOT/'data/bible-source.json').write_text(json.dumps({'repository':'https://github.com/midvash/bible-data','revision':REVISION,'translation':'AVD','license':'Public domain, Smith–Van Dyke 1865','source':BASE,'books_sha256':hashes,'jsonl_sha256':hashlib.sha256(target.read_bytes()).hexdigest()},indent=2))
    import_file(target,ROOT/'data/library.sqlite3')
