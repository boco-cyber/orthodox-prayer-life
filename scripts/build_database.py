"""Rebuild the read-only library from the supplied XAPK and converted EPUB."""
import argparse, hashlib, io, json, re, sqlite3, unicodedata, zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
def clean(s): return re.sub(r'\s+', ' ', s).strip()
def normalize(s):
    s = ''.join(c for c in unicodedata.normalize('NFKD',s) if not unicodedata.combining(c))
    return s.translate(str.maketrans('أإآىؤئ', 'ااايوي')).replace('ـ','').lower()
def digest(data): return hashlib.sha256(data).hexdigest()

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE books(id TEXT PRIMARY KEY,title_en TEXT,title_ar TEXT,author TEXT);
CREATE TABLE editions(id TEXT PRIMARY KEY,book_id TEXT REFERENCES books(id),language TEXT,title TEXT,source_name TEXT,source_sha256 TEXT,source_format TEXT);
CREATE TABLE sections(id TEXT PRIMARY KEY,edition_id TEXT REFERENCES editions(id),parent_id TEXT REFERENCES sections(id),position INTEGER,title TEXT,kind TEXT,source_locator TEXT);
CREATE INDEX sections_parent ON sections(parent_id,position);
CREATE TABLE reading_order(section_id TEXT PRIMARY KEY REFERENCES sections(id),edition_id TEXT REFERENCES editions(id),position INTEGER);
CREATE TABLE passages(id TEXT PRIMARY KEY,section_id TEXT REFERENCES sections(id),position INTEGER,kind TEXT,text TEXT,source_anchor TEXT);
CREATE INDEX passages_section ON passages(section_id,position);
CREATE TABLE quotes(id TEXT PRIMARY KEY,section_id TEXT REFERENCES sections(id),number INTEGER,attribution TEXT,attribution_status TEXT,text TEXT);
CREATE TABLE quote_passages(quote_id TEXT REFERENCES quotes(id),passage_id TEXT REFERENCES passages(id),PRIMARY KEY(quote_id,passage_id));
CREATE TABLE alignments(id INTEGER PRIMARY KEY,english_section_id TEXT REFERENCES sections(id),arabic_section_id TEXT REFERENCES sections(id),level TEXT,status TEXT,note TEXT);
CREATE TABLE bible_references(id INTEGER PRIMARY KEY,passage_id TEXT REFERENCES passages(id),raw_reference TEXT,book_code TEXT,chapter INTEGER,verse_start INTEGER,verse_end INTEGER,translation TEXT,status TEXT,notation TEXT);
CREATE TABLE bible_verses(translation TEXT,book_code TEXT,chapter INTEGER,verse INTEGER,text TEXT,PRIMARY KEY(translation,book_code,chapter,verse));
CREATE TABLE bible_sources(translation TEXT PRIMARY KEY,source_name TEXT,sha256 TEXT);
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
CREATE VIRTUAL TABLE search_index USING fts5(passage_id UNINDEXED,edition_id UNINDEXED,section_id UNINDEXED,text,normalized,tokenize='unicode61');
'''

# OSIS codes, source abbreviations. Arabic citations use verse:chapter in this app.
BIBLE = [
('Gen','Genesis Ge Gen','تك التكوين'),('Exod','Exodus Ex Exod','خر الخروج'),('Lev','Leviticus Lev','لا اللاويين'),('Num','Numbers Num Nm','عد العدد'),('Deut','Deuteronomy Deut Dt','تث التثنية'),('Josh','Joshua Josh','يش يشوع'),('Judg','Judges Judg','قض القضاة'),('Ruth','Ruth Ru','را راعوث'),('1Sam','1 Samuel 1 Sam 1Sam','1صم ١صم'),('2Sam','2 Samuel 2 Sam 2Sam','2صم ٢صم'),('1Kgs','1 Kings 1 Kgs 1Kg','1مل ١مل'),('2Kgs','2 Kings 2 Kgs 2Kg','2مل ٢مل'),('1Chr','1 Chronicles 1 Chr','1أخ ١أخ'),('2Chr','2 Chronicles 2 Chr','2أخ ٢أخ'),('Ezra','Ezra Ezr','عز عزرا'),('Neh','Nehemiah Neh','نح نحميا'),('Esth','Esther Esth','اس أستير'),('Job','Job Jb','أي ايوب'),('Ps','Psalms Psalm Ps Pss','مز المزامير'),('Prov','Proverbs Prov Prv','أم امثال'),('Eccl','Ecclesiastes Eccl','جا الجامعة'),('Song','Song of Solomon Song Cant','نش النشيد'),('Isa','Isaiah Isa Is','إش اش اشعياء'),('Jer','Jeremiah Jer','إر ار ارميا'),('Lam','Lamentations Lam','مرا مراثي'),('Ezek','Ezekiel Ezek Ez','حز حزقيال'),('Dan','Daniel Dan Dn','دا دانيال'),('Hos','Hosea Hos','هو هوشع'),('Joel','Joel Jl','يؤ يوئيل'),('Amos','Amos Am','عا عاموس'),('Obad','Obadiah Obad','عو عوبديا'),('Jonah','Jonah Jon','يون يونان'),('Mic','Micah Mic','مي ميخا'),('Nah','Nahum Nah','نا ناحوم'),('Hab','Habakkuk Hab','حب حبقوق'),('Zeph','Zephaniah Zeph','صف صفنيا'),('Hag','Haggai Hag','حج حجي'),('Zech','Zechariah Zech','زك زكريا'),('Mal','Malachi Mal','مل ملاخي'),('Matt','Matthew Matt Mt','مت متى'),('Mark','Mark Mk','مر مرقس'),('Luke','Luke Lk','لو لوقا'),('John','John Jn','يو يوحنا'),('Acts','Acts Ac','أع اع اعمال'),('Rom','Romans Rom Rm','رو رومية'),('1Cor','1 Corinthians 1 Cor 1Cor','1كو ١كو'),('2Cor','2 Corinthians 2 Cor 2Cor','2كو ٢كو'),('Gal','Galatians Gal','غل غلاطية'),('Eph','Ephesians Eph','أف اف افسس'),('Phil','Philippians Phil','في فى فيل فيلبي'),('Col','Colossians Col','كو كولوسي'),('1Thess','1 Thessalonians 1 Thess 1Thess','1تس ١تس'),('2Thess','2 Thessalonians 2 Thess 2Thess','2تس ٢تس'),('1Tim','1 Timothy 1 Tim 1Tim','1تي ١تي'),('2Tim','2 Timothy 2 Tim 2Tim','2تي ٢تي'),('Titus','Titus Tit','تي تيطس'),('Phlm','Philemon Phlm Philem','فل فليمون'),('Heb','Hebrews Heb','عب عبرانيين'),('Jas','James Jas Jam','يع يعقوب'),('1Pet','1 Peter 1 Pet 1Pt','1بط ١بط'),('2Pet','2 Peter 2 Pet 2Pt','2بط ٢بط'),('1John','1 John 1 Jn 1Jn','1يو ١يو'),('2John','2 John 2 Jn 2Jn','2يو ٢يو'),('3John','3 John 3 Jn 3Jn','3يو ٣يو'),('Jude','Jude Jud','يه يهوذا'),('Rev','Revelation Rev Rv','رؤ رؤيا')]
# Explicit English aliases avoid treating words from long book names as separate books.
EN_ALIASES = {'Gen':['Genesis','Gen','Ge'],'Exod':['Exodus','Exod','Ex'],'Lev':['Leviticus','Lev'],'Num':['Numbers','Num','Nm'],'Deut':['Deuteronomy','Deut','Dt'],'Josh':['Joshua','Josh'],'Judg':['Judges','Judg'],'Ruth':['Ruth','Ru'],'1Sam':['1 Samuel','1 Sam'],'2Sam':['2 Samuel','2 Sam'],'1Kgs':['1 Kings','1 Kgs'],'2Kgs':['2 Kings','2 Kgs'],'1Chr':['1 Chronicles','1 Chr'],'2Chr':['2 Chronicles','2 Chr'],'Song':['Song of Solomon','Song','Cant']}
CHAPTER_COUNTS=[50,40,27,36,34,24,21,4,31,24,22,25,29,36,10,13,10,42,150,31,12,8,66,52,5,48,12,14,3,9,1,4,7,3,3,3,2,14,4,28,16,24,21,28,16,16,13,6,6,4,4,5,3,6,4,3,1,13,5,5,3,5,1,1,1,22]
PATTERNS={}
for language in ['en','ar']:
    aliases={}
    for (code,en,ar),count in zip(BIBLE,CHAPTER_COUNTS):
        names=EN_ALIASES.get(code,en.split()) if language=='en' else ar.split()
        if language=='en' and code[0].isdigit() and code not in EN_ALIASES:
            names=[en,code] # expanded below
            parts=en.split(); names=[' '.join(parts[:2]),' '.join(parts[2:4]),code,parts[-1]]
        for alias in names: aliases[alias.replace(' ','').lower()]=(code,count)
    options='|'.join(re.escape(x) for x in sorted(aliases,key=len,reverse=True))
    PATTERNS[language]=(re.compile(r'(?<![\w])('+options+r')\.?\s*(\d{1,3})\s*[:.]\s*(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?',re.I),aliases)

def references(db,pid,text,language):
    # Strip Arabic directional controls and spaces inside numbered book abbreviations.
    # Keep the original spelling of scripture citations.
    text=re.sub(r'[\u200e\u200f\u202a-\u202e]','',text)
    text=re.sub(r'([1-3١-٣])\s+(?=[a-z\u0600-\u06ff])',r'\1',text,flags=re.I)
    pattern,aliases=PATTERNS[language]
    for m in pattern.finditer(text):
        code,max_chapter=aliases[m[1].lower()];a,b=int(m[2]),int(m[3]); end=int(m[4]) if m[4] else None
        chapter,verse=(b,a) if language=='ar' else (a,b)
        status='candidate' if 1<=chapter<=max_chapter and 1<=verse<=176 and (end is None or verse<=end<=176) else 'needs_review'
        if language=='ar':
            reverse_valid=1<=b<=max_chapter and 1<=a<=176
            direct_valid=1<=a<=max_chapter and 1<=b<=176
            if direct_valid and not reverse_valid:
                chapter,verse=a,b
                status='candidate' if end is None or verse<=end<=176 else 'needs_review'
            elif direct_valid and reverse_valid and a!=b:status='needs_review'
            if end is not None:status='needs_review'
        db.execute('INSERT INTO bible_references(passage_id,raw_reference,book_code,chapter,verse_start,verse_end,translation,status,notation) VALUES(?,?,?,?,?,?,?,?,?)',(pid,m[0],code,chapter,verse,end,'NKJV' if language=='en' else 'AVD',status,'verse:chapter' if language=='ar' else 'chapter:verse'))

def build(xapk,epub):
    target=ROOT/'data/library.sqlite3';temp=target.with_suffix('.tmp');temp.unlink(missing_ok=True)
    db=sqlite3.connect(temp);db.executescript(SCHEMA)
    db.execute('INSERT INTO books VALUES(?,?,?,?)',('orthodox-prayer-life','Orthodox Prayer Life: The Interior Way','حياة الصلاة الأرثوذكسية','Matthew the Poor / الأب متى المسكين'))
    for lang,path,fmt in [('ar',xapk,'XAPK / Windows-1256 HTML'),('en',epub,'EPUB converted from supplied Kindle ebook')]:
        db.execute('INSERT INTO editions VALUES(?,?,?,?,?,?,?)',(lang,'orthodox-prayer-life',lang,'حياة الصلاة الأرثوذكسية' if lang=='ar' else 'Orthodox Prayer Life: The Interior Way',path.name,digest(path.read_bytes()),fmt))
    def section(sid,lang,parent,pos,title,kind,locator):
        db.execute('INSERT INTO sections VALUES(?,?,?,?,?,?,?)',(sid,lang,parent,pos,title,kind,locator))
    def blocks(sid,lang,soup):
        for node in soup.select('script,style,head'):node.decompose()
        nodes=[n for n in soup.find_all(['h1','h2','h3','h4','h5','h6','p','li','td']) if not n.find(['p','li','h1','h2','h3','h4','h5','h6','td'])]
        active=None;parts=[];qids=[];qnum=None;attribution=None;in_sayings=False;last_heading=''
        def flush():
            if active:
                db.execute('INSERT INTO quotes VALUES(?,?,?,?,?,?)',(active,sid,qnum,attribution,'candidate' if attribution else 'unresolved','\n\n'.join(parts)))
                db.executemany('INSERT INTO quote_passages VALUES(?,?)',[(active,p) for p in qids])
        for n in nodes:
            text=clean(n.get_text(' ',strip=True))
            if not text:continue
            heading=n.name.startswith('h')
            if heading:
                last_heading=text
                flush();active=None;parts=[];qids=[]
                in_sayings=bool(re.search('Sayings of the Fathers',text,re.I))
            elif lang=='ar' and ('أقوال' in text and 'الآباء' in text and len(text)<150):in_sayings=True
            match=re.match(r'^[\s\u200e\u200f]*(\d{1,4})\s*[.\-–ـ]\s*',text)
            is_quote=match and ((lang=='en' and titles[sid].startswith('Chapter ') and not (last_heading.lower()=='notes')) or in_sayings or (lang=='ar' and ('أقوال' in titles[sid] or int(match[1])>20)))
            pid=f'{sid}:p{len_passages[sid]+1:04d}'; len_passages[sid]+=1
            db.execute('INSERT INTO passages VALUES(?,?,?,?,?,?)',(pid,sid,len_passages[sid],'heading' if heading else 'paragraph',text,n.get('id')))
            db.execute('INSERT INTO search_index VALUES(?,?,?,?,?)',(pid,lang,sid,text,normalize(text)))
            references(db,pid,text,lang)
            if is_quote:
                flush();active=f'{sid}:q{len_quotes[sid]+1:04d}';len_quotes[sid]+=1;qnum=int(match[1]);parts=[];qids=[];attribution=None
            if active:
                parts.append(text);qids.append(pid)
                # Preserve attribution as a candidate, never invent author metadata.
                tail=re.search(r'\(([^()]{3,300})\)\s*$',text)
                if tail and re.search(r'St |Abba |Father|Macarius|Cassian|Isaac|John|Gregory|Augustine',tail[1]):attribution=tail[1]
        flush()
    from collections import defaultdict
    len_passages=defaultdict(int);len_quotes=defaultdict(int);titles={}
    ar_titles=['طبيعة الصلاة','نواحي النشاط الداخلي للصلاة','معوقات الصلاة','نواحي النشاط الخارجي للصلاة','شخصيات الآباء','مقتطفات وملخصات']
    ar_ranges={1:[(3,10,1),(11,17,2),(18,26,3)],2:[(2,4,4),(5,7,5),(8,10,6),(11,14,7),(15,18,8),(19,21,9),(22,23,10),(24,28,11),(29,31,12),(32,34,13)],3:[(1,1,14),(2,6,15),(7,8,16)]}
    z=zipfile.ZipFile(xapk); apk_name=next(n for n in z.namelist() if n.startswith('com.') and n.endswith('.apk'));apk=zipfile.ZipFile(io.BytesIO(z.read(apk_name)))
    arabic_files=sorted([n for n in apk.namelist() if re.fullmatch(r'assets/hayat_\d+/\d+\.html',n)],key=lambda n:tuple(map(int,re.findall(r'\d+',n))))
    for g,title in enumerate(ar_titles,1):section(f'ar:part{g}','ar',None,g,title,'part' if g<=4 else 'supplement',f'{apk_name}!assets/hayat_{g}/')
    for reading_position,name in enumerate(arabic_files):
        group,num=map(int,re.findall(r'\d+',name));sid=f'ar:{group}:{num:03d}'
        soup=BeautifulSoup(apk.read(name).decode('cp1256'),'html.parser')
        ps=[clean(p.get_text(' ',strip=True)) for p in soup.find_all(['p','h1','h2','h3']) if p.get_text(strip=True)]
        title=ps[0] if ps else name
        if ('الفصل' in title or title.startswith('الباب')) and len(ps)>1:title+=' — '+ps[1]
        if group==1 and num==0:title='مقدمة الطبعة الثانية'
        title=title[:250]; titles[sid]=title
        section(sid,'ar',f'ar:part{group}',num,title,'section',f'{apk_name}!{name}');blocks(sid,'ar',soup)
        db.execute('INSERT INTO reading_order VALUES(?,?,?)',(sid,'ar',reading_position))
        for lo,hi,ch in ar_ranges.get(group,[]):
            if lo<=num<=hi: arabic_by_chapter[ch].append(sid)
    chapter_ranges={**ar_ranges,4:[(1,2,1),(3,7,2),(8,10,3),(11,13,4),(14,16,5),(17,19,6),(20,21,7)]}
    chapter_ranges[1]=chapter_ranges[1]+[(27,28,4),(29,33,5)]
    for group,ranges in chapter_ranges.items():
        for index,(lo,hi,ch) in enumerate(ranges):
            chapter_id=f'ar:part{group}:chapter{index+1}'
            first=f'ar:{group}:{lo:03d}'
            section(chapter_id,'ar',f'ar:part{group}',lo,titles[first],'chapter',f'assets/hayat_{group}/{lo}.html')
            for num in range(lo,hi+1):db.execute('UPDATE sections SET parent_id=? WHERE id=?',(chapter_id,f'ar:{group}:{num:03d}'))
    z=zipfile.ZipFile(epub);container=ET.fromstring(z.read('META-INF/container.xml'));opf=container.find('.//{*}rootfile').get('full-path');base=str(Path(opf).parent);base='' if base=='.' else base+'/'
    package=ET.fromstring(z.read(opf));manifest={x.get('id'):x for x in package.findall('.//{*}manifest/{*}item')};ncx=next(x for x in manifest.values() if x.get('media-type')=='application/x-dtbncx+xml');toc=ET.fromstring(z.read(base+ncx.get('href')))
    nav_for_file=defaultdict(list)
    for nav in toc.findall('.//{*}navPoint'):
        src=nav.find('{*}content').get('src');label=nav.find('{*}navLabel/{*}text').text;nav_for_file[src.split('#')[0]].append(label)
    english_chapters={};seen_files=set()
    for pos,item in enumerate(package.findall('.//{*}spine/{*}itemref')):
        file=manifest[item.get('idref')].get('href');seen_files.add(file);soup=BeautifulSoup(z.read(base+file),'html.parser')
        labels=nav_for_file[file];title=labels[0] if labels else clean(soup.title.get_text()) if soup.title else Path(file).stem
        sid=f'en:{Path(file).stem}';titles[sid]=title
        ch=re.match(r'Chapter (\d+):',title)
        kind='chapter' if ch else 'part' if title.startswith('Part ') else 'front_or_back_matter'
        section(sid,'en',None,pos,title,kind,file);blocks(sid,'en',soup)
        db.execute('INSERT INTO reading_order VALUES(?,?,?)',(sid,'en',pos))
        if ch:english_chapters[int(ch[1])]=sid
    # TOC preserved independently with hierarchical relationships and source anchors.
    def nav_entries(parent_node,parent_sid=None):
        for index,nav in enumerate(parent_node.findall('{*}navPoint')):
            sid='en:nav:'+nav.get('id');title=nav.find('{*}navLabel/{*}text').text;src=nav.find('{*}content').get('src')
            section(sid,'en',parent_sid,index,title,'navigation',src);nav_entries(nav,sid)
    nav_entries(toc.find('{*}navMap'))
    for ch,en_sid in english_chapters.items():
        for ar_sid in arabic_by_chapter[ch]:db.execute('INSERT INTO alignments(english_section_id,arabic_section_id,level,status,note) VALUES(?,?,?,?,?)',(en_sid,ar_sid,'chapter','structural_match','Matched by chapter topic; editions differ. Not a paragraph or quote translation guarantee.'))
    report={'arabic_html_files':len(arabic_files),'english_spine_files':len(seen_files),'english_chapters':len(english_chapters),'edition_differences':['Arabic part 1 chapters 4–5 are absent from the English contents.','Arabic part 4 and supplements have no complete English counterpart.','Chapter links are structural; paragraph and quote alignment needs bilingual review.'],'bible_text_status':'Run Bible import after rebuilding. NKJV requires a licensed source.','quote_status':'Numbered quote candidates, preserving source text; attributions and sentence alignments need editorial review.','bible_reference_status':'Candidates require validation against supplied Bible data; Arabic ranges require review.'}
    for table in ['sections','passages','quotes','bible_references','alignments']:report[table]=db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
    db.execute('INSERT INTO metadata VALUES(?,?)',('extraction_report',json.dumps(report,ensure_ascii=False)))
    assert not db.execute('PRAGMA foreign_key_check').fetchall();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    (ROOT/'data/schema.sql').write_text(SCHEMA)
    db.commit();db.close();temp.replace(target)
    (ROOT/'data/extraction_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))

from collections import defaultdict
arabic_by_chapter=defaultdict(list)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--xapk',required=True,type=Path);p.add_argument('--epub',type=Path,default=ROOT/'source/english.epub');args=p.parse_args();build(args.xapk,args.epub)
