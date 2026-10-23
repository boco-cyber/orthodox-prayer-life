
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
