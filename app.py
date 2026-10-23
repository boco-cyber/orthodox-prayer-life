import json
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from scripts.build_database import normalize

DB_PATH=Path(os.getenv('DATABASE_PATH',Path(__file__).parent/'data/library.sqlite3')).resolve()
app=FastAPI(title='Orthodox Prayer Library API',version='1.0.0',description='Bilingual books, sections, sayings, navigation, search and Bible references. Chapter relationships are structural, not verified sentence translations. Bible text is returned only when supplied and imported.')
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CORS_ORIGINS','*').split(','),allow_credentials=False,allow_methods=['GET'],allow_headers=['*'])
@contextmanager
def connection():
    db=sqlite3.connect(DB_PATH.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:yield db
    finally:db.close()
def rows(db,sql,args=()):return [dict(r) for r in db.execute(sql,args)]
def one(db,sql,args=()):
    r=db.execute(sql,args).fetchone()
    if r is None:raise HTTPException(404,'Not found')
    return dict(r)
def ref_text(db,ref):
    ref=dict(ref);end=ref['verse_end'] or ref['verse_start']
    found=rows(db,'SELECT verse,text FROM bible_verses WHERE translation=? AND book_code=? AND chapter=? AND verse BETWEEN ? AND ? ORDER BY verse',(ref['translation'],ref['book_code'],ref['chapter'],ref['verse_start'],end))
    ref['verses']=found if ref['status']=='validated' else []
    ref['text_status']='available' if ref['status']=='validated' and len(found)==end-ref['verse_start']+1 else 'needs_reference_review' if ref['status']=='needs_review' else 'bible_source_required'
    return ref

def add_refs(db,passages):
    if not passages:return passages
    ids=[p['id'] for p in passages];by_id={p['id']:p for p in passages}
    for p in passages:p['bible_references']=[]
    for ref in rows(db,'SELECT * FROM bible_references WHERE passage_id IN ('+','.join('?' for _ in ids)+')',ids):by_id[ref['passage_id']]['bible_references'].append(ref_text(db,ref))
    return passages

@app.get('/')
def index():return {'name':app.title,'docs':'/docs','books':'/v1/books','health':'/health','version':app.version}
@app.get('/health')
def health():
    with connection() as db:db.execute('SELECT id FROM books LIMIT 1').fetchone()
    return {'status':'ok'}
@app.get('/v1/books')
def books():
    with connection() as db:return {'items':rows(db,'SELECT * FROM books')}
@app.get('/v1/books/{book_id}')
def book(book_id:str):
    with connection() as db:
        result=one(db,'SELECT * FROM books WHERE id=?',(book_id,));result['editions']=rows(db,'SELECT * FROM editions WHERE book_id=?',(book_id,));return result
@app.get('/v1/editions/{edition_id}/toc')
def toc(edition_id:str):
    with connection() as db:
        edition=one(db,'SELECT * FROM editions WHERE id=?',(edition_id,));sections=rows(db,'SELECT * FROM sections WHERE edition_id=? ORDER BY position,id',(edition_id,))
        indexed={s['id']:{**s,'children':[]} for s in sections};roots=[]
        for s in sections:
            target=indexed[s['id']]
            if s['parent_id']:indexed[s['parent_id']]['children'].append(target)
            else:roots.append(target)
        # EPUB navigation carries the publisher hierarchy. Content sections remain addressable.
        for s in sections:
            if s['kind']=='navigation':
                locator=s['source_locator'];file,_,anchor=locator.partition('#')
                target=next((x for x in sections if x['kind']!='navigation' and x['source_locator']==file),None)
                indexed[s['id']]['target_section_id']=target['id'] if target else None
                indexed[s['id']]['target_anchor']=anchor or None
        return {'edition':edition,'items':[r for r in roots if r['kind']=='navigation'] if edition_id=='en' else roots,'content_sections':[r for r in roots if r['kind']!='navigation'] if edition_id=='en' else []}
@app.get('/v1/sections/{section_id}')
def section(section_id:str):
    with connection() as db:
        result=one(db,'SELECT * FROM sections WHERE id=?',(section_id,));result['children']=rows(db,'SELECT * FROM sections WHERE parent_id=? ORDER BY position,id',(section_id,))
        result['previous']=db.execute('SELECT id FROM sections WHERE edition_id=? AND parent_id IS ? AND kind != ? AND (position,id)<(?,?) ORDER BY position DESC,id DESC LIMIT 1',(result['edition_id'],result['parent_id'],'navigation',result['position'],section_id)).fetchone()
        result['next']=db.execute('SELECT id FROM sections WHERE edition_id=? AND parent_id IS ? AND kind != ? AND (position,id)>(?,?) ORDER BY position,id LIMIT 1',(result['edition_id'],result['parent_id'],'navigation',result['position'],section_id)).fetchone()
        for key in ['previous','next']:result[key]=result[key][0] if result[key] else None
        result['alignments']=rows(db,'SELECT * FROM alignments WHERE english_section_id=? OR arabic_section_id=?',(section_id,section_id))
        reading=db.execute('SELECT position FROM reading_order WHERE section_id=?',(section_id,)).fetchone()
        for direction,op,order in [('reading_previous','<','DESC'),('reading_next','>','ASC')]:
            adjacent=db.execute(f'SELECT section_id FROM reading_order WHERE edition_id=? AND position {op} ? ORDER BY position {order} LIMIT 1',(result['edition_id'],reading[0])).fetchone() if reading else None
            result[direction]=adjacent[0] if adjacent else None
        result['breadcrumbs']=[]
        parent=result['parent_id']
        while parent:
            ancestor=one(db,'SELECT id,parent_id,title FROM sections WHERE id=?',(parent,));result['breadcrumbs'].insert(0,ancestor);parent=ancestor['parent_id']
        if result['kind']=='navigation':
            file,_,anchor=result['source_locator'].partition('#')
            target=db.execute("SELECT id FROM sections WHERE edition_id=? AND source_locator=? AND kind!='navigation'",(result['edition_id'],file)).fetchone()
            result['target_section_id']=target[0] if target else None
            if target:
                passage=db.execute('SELECT id,position FROM passages WHERE section_id=? AND source_anchor=?',(target[0],anchor)).fetchone() if anchor else None
                result['target_passage_id']=passage[0] if passage else None
                result['target_passage_offset']=passage[1]-1 if passage else 0
        return result
@app.get('/v1/sections/{section_id}/passages')
def passages(section_id:str,limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0)):
    with connection() as db:
        one(db,'SELECT id FROM sections WHERE id=?',(section_id,));total=db.execute('SELECT count(*) FROM passages WHERE section_id=?',(section_id,)).fetchone()[0]
        return {'total':total,'offset':offset,'limit':limit,'items':add_refs(db,rows(db,'SELECT * FROM passages WHERE section_id=? ORDER BY position LIMIT ? OFFSET ?',(section_id,limit,offset)))}
@app.get('/v1/passages/{passage_id}')
def passage(passage_id:str):
    with connection() as db:return add_refs(db,[one(db,'SELECT * FROM passages WHERE id=?',(passage_id,))])[0]
@app.get('/v1/quotes')
def quotes(edition_id:Literal['ar','en']|None=None,section_id:str|None=None,limit:int=Query(30,ge=1,le=100),offset:int=Query(0,ge=0)):
    where=[];args=[]
    if edition_id:where.append('s.edition_id=?');args.append(edition_id)
    if section_id:where.append('q.section_id=?');args.append(section_id)
    clause=' WHERE '+' AND '.join(where) if where else ''
    with connection() as db:
        total=db.execute('SELECT count(*) FROM quotes q JOIN sections s ON s.id=q.section_id'+clause,args).fetchone()[0]
        return {'total':total,'limit':limit,'offset':offset,'items':rows(db,'SELECT q.*,s.edition_id FROM quotes q JOIN sections s ON s.id=q.section_id'+clause+' ORDER BY s.edition_id,s.position,q.id LIMIT ? OFFSET ?',args+[limit,offset])}
@app.get('/v1/quotes/{quote_id}')
def quote(quote_id:str):
    with connection() as db:
        q=one(db,'SELECT * FROM quotes WHERE id=?',(quote_id,));q['passages']=add_refs(db,rows(db,'SELECT p.* FROM passages p JOIN quote_passages qp ON qp.passage_id=p.id WHERE qp.quote_id=? ORDER BY p.position',(quote_id,)));return q
@app.get('/v1/search')
def search(q:str=Query(min_length=1,max_length=200),edition_id:Literal['ar','en']|None=None,book_id:str|None=None,limit:int=Query(30,ge=1,le=100),offset:int=Query(0,ge=0)):
    terms=re.findall(r'\w+',normalize(q))
    if not terms:raise HTTPException(422,'Enter words to search for')
    # Treat all input as literal words, never as FTS operators.
    match='normalized : ('+' AND '.join('"'+t+'"' for t in terms)+')'
    where=['search_index MATCH ?'];args=[match]
    if edition_id:where.append('search_index.edition_id=?');args.append(edition_id)
    if book_id:where.append('e.book_id=?');args.append(book_id)
    base=' FROM search_index JOIN sections s ON s.id=search_index.section_id JOIN editions e ON e.id=s.edition_id WHERE '+' AND '.join(where)
    with connection() as db:
        total=db.execute('SELECT count(*)'+base,args).fetchone()[0]
        items=rows(db,'SELECT search_index.passage_id,search_index.section_id,search_index.edition_id,s.title,snippet(search_index,3,\'\',\'\',\' … \',40) AS excerpt,bm25(search_index) AS rank'+base+' ORDER BY rank,passage_id LIMIT ? OFFSET ?',args+[limit,offset]);return {'total':total,'items':items,'limit':limit,'offset':offset}
@app.get('/v1/bible/references')
def bible_references(section_id:str|None=None,status:Literal['candidate','validated','needs_review']|None=None,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    where=[];args=[]
    if section_id:where.append('p.section_id=?');args.append(section_id)
    if status:where.append('r.status=?');args.append(status)
    base=' FROM bible_references r JOIN passages p ON p.id=r.passage_id'+(' WHERE '+' AND '.join(where) if where else '')
    with connection() as db:return {'total':db.execute('SELECT count(*)'+base,args).fetchone()[0],'items':[ref_text(db,r) for r in rows(db,'SELECT r.*'+base+' ORDER BY r.id LIMIT ? OFFSET ?',args+[limit,offset])],'limit':limit,'offset':offset}
@app.get('/v1/bible/{translation}/{book_code}/{chapter}/{verse}')
def verse(translation:Literal['NKJV','AVD'],book_code:str,chapter:int,verse:int):
    with connection() as db:
        if not db.execute('SELECT 1 FROM bible_sources WHERE translation=?',(translation,)).fetchone():raise HTTPException(503,f'{translation} Bible source has not been imported')
        return one(db,'SELECT * FROM bible_verses WHERE translation=? AND book_code=? AND chapter=? AND verse=?',(translation,book_code,chapter,verse))
@app.get('/v1/status')
def status():
    with connection() as db:
        report=json.loads(one(db,'SELECT value FROM metadata WHERE key=?',('extraction_report',))['value']);report['bible_sources']=rows(db,'SELECT translation,source_name FROM bible_sources');report['bible_verse_counts']=rows(db,'SELECT translation,count(*) AS verses FROM bible_verses GROUP BY translation');report['reference_counts']=rows(db,'SELECT status,count(*) AS count FROM bible_references GROUP BY status');return report

@app.get('/v1/bible-parallel')
def parallel(book_code:str,chapter:int=Query(ge=1,le=150),verse_start:int=Query(ge=1,le=176),verse_end:int|None=Query(None,ge=1,le=176)):
    end=verse_end or verse_start
    if end<verse_start:raise HTTPException(422,'verse_end must be >= verse_start')
    with connection() as db:
        items=[]
        for translation in ['NKJV','AVD']:
            found=rows(db,'SELECT verse,text FROM bible_verses WHERE translation=? AND book_code=? AND chapter=? AND verse BETWEEN ? AND ? ORDER BY verse',(translation,book_code,chapter,verse_start,end))
            items.append({'translation':translation,'status':'available' if len(found)==end-verse_start+1 else 'source_required' if not db.execute('SELECT 1 FROM bible_sources WHERE translation=?',(translation,)).fetchone() else 'not_found','verses':found})
        return {'book_code':book_code,'chapter':chapter,'verse_start':verse_start,'verse_end':end,'items':items}

@app.get('/v1/bible/translations')
def bible_translations():
    with connection() as db:return {'items':[{'id':tr,'available':bool(db.execute('SELECT 1 FROM bible_sources WHERE translation=?',(tr,)).fetchone()),'name':name} for tr,name in [('NKJV','New King James Version'),('AVD','Arabic Smith–Van Dyke (1865)')]]}
@app.get('/v1/bible/books')
def bible_books(translation:Literal['AVD','NKJV']='AVD'):
    with connection() as db:return {'items':rows(db,'SELECT book_code,count(DISTINCT chapter) AS chapters,count(*) AS verses FROM bible_verses WHERE translation=? GROUP BY book_code ORDER BY min(rowid)',(translation,))}
@app.get('/v1/bible/{translation}/{book_code}/{chapter}')
def bible_chapter(translation:Literal['AVD','NKJV'],book_code:str,chapter:int):
    with connection() as db:
        if not db.execute('SELECT 1 FROM bible_sources WHERE translation=?',(translation,)).fetchone():raise HTTPException(503,'Bible source has not been imported')
        items=rows(db,'SELECT verse,text FROM bible_verses WHERE translation=? AND book_code=? AND chapter=? ORDER BY verse',(translation,book_code,chapter))
        if not items:raise HTTPException(404,'Chapter not found')
        return {'translation':translation,'book_code':book_code,'chapter':chapter,'items':items}
