import json
import sqlite3
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app import app,DB_PATH
from scripts.build_database import normalize

@pytest.fixture
def client():return TestClient(app)

def test_database_integrity_and_content():
    with sqlite3.connect(DB_PATH) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        assert db.execute("SELECT count(*) FROM sections WHERE edition_id='ar' AND kind='section'").fetchone()[0]==167
        assert db.execute("SELECT count(*) FROM sections WHERE edition_id='en' AND kind='chapter'").fetchone()[0]==16
        assert db.execute("SELECT count(*) FROM passages WHERE text LIKE '%�%'").fetchone()[0]==0
        assert db.execute("SELECT count(*) FROM bible_verses WHERE translation='AVD'").fetchone()[0]==31104
        assert db.execute("SELECT count(DISTINCT book_code) FROM bible_verses WHERE translation='AVD'").fetchone()[0]==66

def test_book_and_toc_links(client):
    book=client.get('/v1/books/orthodox-prayer-life').json();assert len(book['editions'])==2
    for lang in ['ar','en']:
        toc=client.get(f'/v1/editions/{lang}/toc').json();assert toc['items']
        def walk(items):
            for item in items:
                r=client.get('/v1/sections/'+item['id']);assert r.status_code==200
                if item['kind']=='navigation':assert r.json()['target_section_id'],item
                walk(item['children'])
        walk(toc['items'])

def test_passage_pagination_and_navigation(client):
    sid='ar:1:003';first=client.get(f'/v1/sections/{sid}/passages?limit=2').json();second=client.get(f'/v1/sections/{sid}/passages?limit=2&offset=2').json()
    assert first['total']>4 and set(p['id'] for p in first['items']).isdisjoint(p['id'] for p in second['items'])
    s=client.get(f'/v1/sections/{sid}').json();assert s['breadcrumbs'] and s['next']
    p=client.get('/v1/passages/'+first['items'][0]['id']);assert p.status_code==200

def test_bilingual_search_and_literal_operators(client):
    for q,lang in [('prayer','en'),('الصلاة','ar'),('الصَّلاة','ar')]:
        r=client.get('/v1/search',params={'q':q,'edition_id':lang}).json();assert r['total']>0;assert all(x['edition_id']==lang for x in r['items'])
    for q in ['" OR *','NEAR()','---']:
        assert client.get('/v1/search',params={'q':q}).status_code in [200,422]

def test_quotes_have_ordered_source_passages(client):
    for lang in ['ar','en']:
        q=client.get('/v1/quotes',params={'edition_id':lang}).json();assert q['total']>300
        item=client.get('/v1/quotes/'+q['items'][0]['id']).json()
        assert item['text']=='\n\n'.join(p['text'] for p in item['passages'])

def test_scripture_translation_identity_and_parallel(client):
    r=client.get('/v1/bible/AVD/John/3/16');assert r.status_code==200 and 'ٱلْعَالَمَ' in r.json()['text']
    r=client.get('/v1/bible/NKJV/John/3/16');assert r.status_code==503
    parallel=client.get('/v1/bible-parallel?book_code=John&chapter=3&verse_start=16').json()
    assert parallel['items'][0]['translation']=='NKJV' and not parallel['items'][0]['verses']
    assert parallel['items'][1]['status']=='available'
    with sqlite3.connect(DB_PATH) as db:
        assert db.execute("SELECT count(*) FROM bible_references WHERE raw_reference LIKE 'رو %' AND book_code!='Rom'").fetchone()[0]==0
        assert db.execute("SELECT count(*) FROM bible_references WHERE raw_reference LIKE 'رؤ %' AND book_code!='Rev'").fetchone()[0]==0

def test_uncertain_references_never_show_guessed_text(client):
    r=client.get('/v1/bible/references?status=needs_review').json();assert r['total']>0
    assert all(x['text_status']=='needs_reference_review' and not x['verses'] for x in r['items'])

def test_invalid_requests_and_cors(client):
    assert client.get('/v1/sections/missing').status_code==404
    assert client.get('/v1/quotes?limit=100000').status_code==422
    assert client.get('/v1/search?q=prayer&edition_id=fr').status_code==422
    assert client.post('/v1/books').status_code==405
    assert client.get('/v1/books',headers={'Origin':'https://example.org'}).headers['access-control-allow-origin']=='*'


def test_numbered_bible_book_is_not_dropped():
    from scripts.build_database import references,SCHEMA
    db=sqlite3.connect(':memory:');db.executescript(SCHEMA)
    db.execute("PRAGMA foreign_keys=OFF")
    references(db,'test','(1 Jn 1.3) and (2 Cor 3.4)','en')
    assert db.execute('SELECT book_code,chapter,verse_start FROM bible_references').fetchall()==[('1John',1,3),('2Cor',3,4)]
