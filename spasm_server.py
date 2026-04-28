#!/usr/bin/env python3
"""
spasm_server.py — SPASM v2.1
Student's Personal Assistant Synopsis Maker

Based on Srishti Nested Spherical Shell Database geometry.
Input  : PDF or TXT files only.
Output : abc_fullparse.txt  — full parse alongside original file
         abc_synopsis[N].txt — raw synopsis at N words alongside original

Author  : Venkatesh (CI)
with assistance from Claudie (Claude SI — Drama Queen instance)
License : GNU GPL 3.0 — free for all, profit for none
phi     : 1.6180339887498948482...

FOLDER STRUCTURE (portable — runs from pendrive or any folder):
    spasm/
    ├── spasm_server.py        this file
    ├── spasm_gui.html         browser interface
    ├── domain_reference.json  domain vocabulary (from Srishti project)
    ├── spasm.db               main registry
    ├── query_synopsis.db      domain classification index
    ├── spasm_ref.db           reference vocabulary DB
    └── reference/             place encyclopedias and dictionaries here

STARTUP:
    python3 spasm_server.py

BUILD REFERENCE DB:
    python3 spasm_server.py --build-ref

ADD ONE FILE TO REFERENCE DB (Srishti incremental style):
    python3 spasm_server.py --add-ref /path/to/file.pdf

BROWSER:
    http://localhost:7520
"""

import json
import math
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from math import log
from pathlib import Path
from socketserver import ThreadingMixIn

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


# =============================================================================
#  CONFIG — all paths relative to script folder (portable)
# =============================================================================

HOST      = "127.0.0.1"
PORT      = 7520
PHI       = (1 + math.sqrt(5)) / 2

SPASM_DIR  = Path(__file__).parent
SPASM_DB   = str(SPASM_DIR / "spasm.db")
QUERY_DB   = str(SPASM_DIR / "query_synopsis.db")
REF_DB     = str(SPASM_DIR / "spasm_ref.db")
REF_FOLDER = str(SPASM_DIR / "reference")
KEY_FILE   = str(SPASM_DIR / "spasm.key")
JSON_FILE  = str(SPASM_DIR / "domain_reference.json")

WORDS_PER_KB = 143
PARSE_RATIO  = 0.15


# =============================================================================
#  DOMAINS — loaded from domain_reference.json
# =============================================================================

def load_domains_from_json():
    try:
        p = Path(JSON_FILE)
        if not p.exists():
            return _builtin_domains()
        content = p.read_text(encoding="utf-8")
        content = content.replace(
            '    ]\n     },\n   ]\n  }\n}',
            '    ]\n     }\n   ]\n  }\n}')
        data = json.loads(content)
        domains_raw = data.get("production_domains", {}).get("domains", [])
        domains = []
        domain_hints = {}
        for d in domains_raw:
            name = d.get("domain", "")
            if name and name != "program_db":
                domains.append(name)
                domain_hints[name] = d.get("subdomains_theta", [])
        print(f"  [SPASM] Loaded {len(domains)} domains from domain_reference.json")
        return domains, domain_hints
    except Exception as e:
        print(f"  [SPASM] JSON load warning: {e} — using built-in domains")
        return _builtin_domains()

def _builtin_domains():
    domains = [
        "physics","chemistry","biology","mathematics",
        "medicine","computer_science","electronics","engineering_technology"
    ]
    return domains, {d: [] for d in domains}

DOMAINS, DOMAIN_HINTS = load_domains_from_json()

STOP = {
    "the","and","for","are","you","can","show","what","how","have","this","that",
    "with","from","all","any","about","tell","some","when","where","was","who",
    "will","been","they","their","also","more","then","than","into","your","our",
    "its","but","not","had","has","did","does","her","him","his","she","were",
    "would","could","should","may","might","here","there","just","very","which",
    "while","over","under","these","those","such","only","after","before","since",
    "even","most","other","same","each","both","many","much","well","still",
    "page","pages","chapter","section","table","figure","appendix","index",
    "introduction","conclusion","references","bibliography","abstract","contents",
}
WATSON_STOP = {
    "this","that","with","from","have","were","been","they","their","there",
    "about","which","when","what","where","while","would","could","should",
    "into","than","then","them","also","some","such","only","very","more",
    "most","other","over","under","again","further","these","those",
}


# =============================================================================
#  PDF CONVERSION
# =============================================================================

def pdf_to_text(filepath):
    try:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = tmp.name
        subprocess.run(["pdftotext", "-layout", str(filepath), tmp_path],
                       capture_output=True, timeout=120)
        if Path(tmp_path).exists():
            content = Path(tmp_path).read_text(encoding="utf-8", errors="ignore")
            Path(tmp_path).unlink()
            if content.strip():
                return content
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"  [SPASM] pdftotext warning: {e}")
    try:
        import pypdf
        reader = pypdf.PdfReader(str(filepath))
        return "".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        print(f"  [SPASM] pypdf warning: {e}")
    return ""

def read_file(filepath):
    """
    Read any text-based file or PDF.
    PDF  → pdftotext / pypdf
    Everything else → read as plain text with UTF-8 fallback.
    Students converting books get .TXT .txt .text .rst .epub text exports
    and all manner of variants — we accept all of them.
    Only hard reject: binary formats we cannot read (images, zips, executables).
    """
    p = Path(filepath)
    if not p.exists():
        return "", f"File not found: {filepath}"
    ext = p.suffix.lower()

    # Binary formats we cannot extract text from — reject clearly
    BINARY_EXT = {
        ".jpg",".jpeg",".png",".gif",".bmp",".tiff",".tif",".webp",
        ".svg",".ico",".raw",".cr2",".nef",".heic",".heif",
        ".zip",".rar",".7z",".tar",".gz",".bz2",".xz",
        ".mp3",".wav",".flac",".ogg",".m4a",".aac",
        ".mp4",".mkv",".avi",".mov",".wmv",".webm",
        ".exe",".dll",".so",".bin",".pyc",".class",
        ".db",".sqlite",".db3",
        ".doc",".docx",".odt",".xls",".xlsx",".ppt",".pptx",
    }

    if ext == ".pdf":
        text = pdf_to_text(filepath)
        if not text.strip():
            return "", (
                "PDF produced no text — file may be a scanned image. "
                "OCR is not supported. Convert to TXT first."
            )
        return text, ""

    if ext in BINARY_EXT:
        return "", (
            f"Cannot read binary file ({ext}). "
            "Convert your document to PDF or TXT first."
        )

    # Everything else — try to read as text
    # This covers: .txt .TXT .text .md .rst .epub .fb2 .lit .mobi (text exports)
    # .log .csv .tsv and any other text-based format
    try:
        return p.read_text(encoding="utf-8", errors="ignore"), ""
    except Exception as e:
        # Last resort — try latin-1
        try:
            return p.read_text(encoding="latin-1", errors="ignore"), ""
        except Exception:
            return "", f"Could not read file: {e}"


# =============================================================================
#  PARSE LIMIT
# =============================================================================

def calc_parse_limit(filepath):
    try:
        size_kb = Path(filepath).stat().st_size / 1024
    except Exception:
        size_kb = 100
    return max(int(PARSE_RATIO * WORDS_PER_KB * size_kb), 500)


# =============================================================================
#  WATSON KEYWORD SELECTOR
# =============================================================================

def watson_keyword_selector(text, top_k=100, domain=None):
    """
    Frequency (0.5) + Rarity (0.3) + Co-occurrence graph (0.2).
    Domain hints boost 1.3x. Diversity bias prevents clustering.
    Venkatesh (CI) + Watson (ChatGPT) — March 2026
    """
    all_stop = STOP | WATSON_STOP
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    words = [w for w in words if w not in all_stop]
    if not words:
        return []

    total = len(words)
    freq  = Counter(words)
    score_freq = {w: freq[w] / total for w in freq}
    score_rare = {w: 1.0 / (1.0 + log(1 + freq[w])) for w in freq}

    graph = defaultdict(set)
    for i, w in enumerate(words):
        for j in range(i + 1, min(i + 5, len(words))):
            w2 = words[j]
            if w != w2:
                graph[w].add(w2)
                graph[w2].add(w)

    score_graph = {w: len(graph[w]) for w in freq}
    max_g = max(score_graph.values()) if score_graph else 1
    score_graph = {w: score_graph[w] / max_g for w in score_graph}

    scores = {
        w: (0.5 * score_freq.get(w, 0) +
            0.3 * score_rare.get(w, 0) +
            0.2 * score_graph.get(w, 0))
        for w in freq
    }

    if domain and domain in DOMAIN_HINTS:
        hints = set(DOMAIN_HINTS[domain])
        for w in scores:
            if w in hints:
                scores[w] *= 1.3

    top_words = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    selected = []
    for w, _ in top_words:
        if len(selected) >= top_k:
            break
        if not any(w in graph[s] for s in selected):
            selected.append(w)
    for w, _ in top_words:
        if len(selected) >= top_k:
            break
        if w not in selected:
            selected.append(w)
    return selected


# =============================================================================
#  SELF-REFERENCE FILTER (for "other" domain)
# =============================================================================

def self_reference_filter(raw_keywords, full_text, top_k=None):
    """
    When no reference DB available — filter by self-comparison.
    Score = frequency in full text x co-occurrence with other keywords.
    The book defines its own vocabulary.
    """
    if not raw_keywords or not full_text:
        return raw_keywords

    words_in_text = re.findall(r"[a-zA-Z]{4,}", full_text.lower())
    words_in_text = [w for w in words_in_text if w not in (STOP | WATSON_STOP)]
    freq  = Counter(words_in_text)
    total = len(words_in_text) or 1

    graph = defaultdict(set)
    for i, w in enumerate(words_in_text):
        for j in range(i + 1, min(i + 10, len(words_in_text))):
            w2 = words_in_text[j]
            if w != w2:
                graph[w].add(w2)
                graph[w2].add(w)

    kw_set = set(raw_keywords)
    scored = {}
    for w in kw_set:
        f = freq.get(w, 0) / total
        c = len(graph.get(w, set()) & kw_set) / max(len(kw_set), 1)
        scored[w] = 0.6 * f + 0.4 * c

    ranked = [w for w, _ in sorted(scored.items(), key=lambda x: x[1], reverse=True)]
    return ranked[:top_k] if top_k else ranked


# =============================================================================
#  DOMAIN DETECTION
# =============================================================================

def detect_domain(keywords):
    if not keywords:
        return "other"
    kw_set = set(keywords)
    scores = {d: len(kw_set & set(hints)) for d, hints in DOMAIN_HINTS.items()}
    if not scores:
        return "other"
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "other"


# =============================================================================
#  REFERENCE DB FILTER
# =============================================================================

def get_domain_vocab(domain, limit=2000):
    if domain == "other":
        return set()
    vocab = set()
    try:
        if not Path(REF_DB).exists():
            raise FileNotFoundError
        conn = sqlite3.connect(REF_DB)
        rows = conn.execute(
            "SELECT filepath FROM spasm_ref WHERE domain=? OR domain='general' LIMIT 5",
            (domain,)
        ).fetchall()
        conn.close()
        for (fpath,) in rows:
            if not Path(fpath).exists():
                continue
            ext = Path(fpath).suffix.lower()
            try:
                if ext == ".pdf":
                    content = pdf_to_text(fpath)
                elif ext in (".txt", ".text", ".md"):
                    content = Path(fpath).read_text(
                        encoding="utf-8", errors="ignore")[:200000]
                else:
                    continue
                for w in re.findall(r"[a-zA-Z]{4,}", content.lower()):
                    if w not in STOP and len(w) > 3:
                        vocab.add(w)
                    if len(vocab) >= limit:
                        break
            except Exception:
                pass
    except Exception:
        pass
    if len(vocab) < 20 and domain in DOMAIN_HINTS:
        vocab.update(DOMAIN_HINTS[domain])
    return vocab

def filter_to_meaningful(raw_keywords, domain, full_text=""):
    if not raw_keywords:
        return []
    if domain == "other":
        return self_reference_filter(raw_keywords, full_text)
    vocab = get_domain_vocab(domain)
    if len(vocab) < 20:
        return self_reference_filter(raw_keywords, full_text)
    meaningful = [w for w in raw_keywords if w in vocab]
    if len(meaningful) < 5:
        extras = [w for w in raw_keywords if w not in meaningful and len(w) >= 5]
        meaningful = meaningful + extras[:20]
    return meaningful


# =============================================================================
#  DATABASE SETUP
# =============================================================================

def ensure_dbs():
    conn = sqlite3.connect(SPASM_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS spasm_registry (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        original_path TEXT NOT NULL UNIQUE,
        fullparse_path TEXT DEFAULT '',
        domain        TEXT DEFAULT '',
        parse_status  INTEGER DEFAULT 0,
        added_ts      INTEGER NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS spasm_synopses (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        registry_id INTEGER NOT NULL,
        word_count  INTEGER NOT NULL,
        synopsis_path TEXT NOT NULL,
        is_human    INTEGER DEFAULT 0,
        created_ts  INTEGER NOT NULL,
        UNIQUE(registry_id, word_count, is_human))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS spasm_identity (
        key TEXT PRIMARY KEY, value TEXT, ts INTEGER)""")
    now = int(time.time())
    for k, v in [("name","SPASM"),("version","2.1"),("born",str(now)),
                 ("author","Venkatesh (CI)"),
                 ("architecture","Srishti Spherical Nested Shell"),
                 ("license","GPL3 — free for all, profit for none")]:
        conn.execute("INSERT OR IGNORE INTO spasm_identity (key,value,ts) VALUES (?,?,?)",
                     (k, v, now))
    conn.commit()
    conn.close()

    conn = sqlite3.connect(QUERY_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS query_index (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        original_path TEXT NOT NULL UNIQUE,
        domain        TEXT DEFAULT '',
        classified_ts INTEGER NOT NULL)""")
    conn.commit()
    conn.close()
    print(f"  [SPASM] spasm.db          : {SPASM_DB}")
    print(f"  [SPASM] query_synopsis.db : {QUERY_DB}")


# =============================================================================
#  REFERENCE DB BUILDER
# =============================================================================

def build_ref_db(single_file=None):
    ref_folder = Path(REF_FOLDER)
    if not ref_folder.exists():
        ref_folder.mkdir(parents=True, exist_ok=True)
        print(f"  [SPASM] Created: {REF_FOLDER}")
        print(f"  [SPASM] Place PDF/TXT files there and run --build-ref again.")
        return

    conn = sqlite3.connect(REF_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS spasm_ref (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filepath TEXT NOT NULL UNIQUE,
        filename TEXT NOT NULL,
        domain   TEXT DEFAULT 'general',
        added_ts INTEGER NOT NULL)""")
    conn.commit()

    if single_file:
        files = [Path(single_file)]
    else:
        files = (list(ref_folder.rglob("*.pdf")) + list(ref_folder.rglob("*.txt")) +
                 list(ref_folder.rglob("*.PDF")) + list(ref_folder.rglob("*.TXT")))

    added = 0
    for fpath in files:
        if not fpath.exists():
            continue
        fname_lower = fpath.stem.lower().replace("_"," ").replace("-"," ")
        domain = "general"
        for d, hints in DOMAIN_HINTS.items():
            if d.replace("_"," ") in fname_lower:
                domain = d; break
            if any(h.replace("_"," ") in fname_lower for h in hints[:20]):
                domain = d; break
        try:
            conn.execute(
                "INSERT OR IGNORE INTO spasm_ref (filepath,filename,domain,added_ts) "
                "VALUES (?,?,?,?)",
                (str(fpath), fpath.name, domain, int(time.time())))
            added += 1
            print(f"  [Ref] {fpath.name[:50]:<50} domain: {domain}")
        except Exception as e:
            print(f"  [Ref] Warning: {e}")

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM spasm_ref").fetchone()[0]
    conn.close()
    print(f"\n  [SPASM] Reference DB: {total} files total, {added} added this run.")


# =============================================================================
#  PARSE ENGINE
# =============================================================================

def do_fullparse(filepath):
    fpath = Path(filepath)
    if not fpath.exists():
        return "", "", [], f"File not found: {filepath}"

    expected_parse = fpath.parent / (fpath.stem + "_fullparse.txt")
    if expected_parse.exists():
        existing = expected_parse.read_text(encoding="utf-8", errors="ignore")
        keywords = [w.strip() for w in existing.split(",") if w.strip()]
        domain = ""
        try:
            conn = sqlite3.connect(SPASM_DB)
            row  = conn.execute(
                "SELECT domain FROM spasm_registry WHERE original_path=?",
                (str(fpath),)).fetchone()
            conn.close()
            if row and row[0]: domain = row[0]
        except Exception: pass
        if not domain: domain = detect_domain(keywords)
        print(f"  [SPASM] Already parsed: {str(expected_parse)[-60:]}")
        return str(expected_parse), domain, keywords, ""

    text, err = read_file(str(fpath))
    if err: return "", "", [], err

    parse_limit = calc_parse_limit(str(fpath))
    words_list  = text.split()
    if len(words_list) > parse_limit:
        text = " ".join(words_list[:parse_limit])

    keywords = watson_keyword_selector(text, top_k=500)
    if not keywords:
        return "", "", [], "No keywords extracted — file may be empty or unreadable."

    domain = detect_domain(keywords)

    try:
        expected_parse.write_text(", ".join(keywords), encoding="utf-8")
    except Exception as e:
        return "", "", [], f"Could not write fullparse file: {e}"

    now = int(time.time())
    conn = sqlite3.connect(SPASM_DB)
    conn.execute("""
        INSERT INTO spasm_registry
        (original_path, fullparse_path, domain, parse_status, added_ts)
        VALUES (?,?,?,1,?)
        ON CONFLICT(original_path) DO UPDATE SET
            fullparse_path=excluded.fullparse_path,
            domain=excluded.domain, parse_status=1
    """, (str(fpath), str(expected_parse), domain, now))
    conn.commit(); conn.close()

    conn = sqlite3.connect(QUERY_DB)
    conn.execute("""
        INSERT INTO query_index (original_path, domain, classified_ts) VALUES (?,?,?)
        ON CONFLICT(original_path) DO UPDATE SET
            domain=excluded.domain, classified_ts=excluded.classified_ts
    """, (str(fpath), domain, now))
    conn.commit(); conn.close()

    print(f"  [SPASM] Parsed: {str(expected_parse)[-60:]}")
    return str(expected_parse), domain, keywords, ""


# =============================================================================
#  SYNOPSIS ENGINE
# =============================================================================

def do_synopsis(original_path, word_count, user_domain=""):
    fpath = Path(original_path)
    synopsis_path = fpath.parent / (fpath.stem + f"_synopsis{word_count}.txt")
    if synopsis_path.exists():
        return str(synopsis_path), [], "", "already_exists"

    expected_parse = fpath.parent / (fpath.stem + "_fullparse.txt")
    if not expected_parse.exists():
        return "", [], "", "File not yet parsed. Run Parse first."

    domain = user_domain.strip() if user_domain.strip() not in ("", "auto") else ""
    if not domain:
        try:
            conn = sqlite3.connect(SPASM_DB)
            row  = conn.execute(
                "SELECT domain FROM spasm_registry WHERE original_path=?",
                (str(fpath),)).fetchone()
            conn.close()
            if row and row[0]: domain = row[0]
        except Exception: pass

    raw_text     = expected_parse.read_text(encoding="utf-8", errors="ignore")
    raw_keywords = [w.strip() for w in raw_text.split(",") if w.strip()]
    if not domain: domain = detect_domain(raw_keywords)

    full_text = ""
    if domain == "other":
        full_text, _ = read_file(str(fpath))

    filtered       = filter_to_meaningful(raw_keywords, domain, full_text)
    final_keywords = filtered[:word_count] or raw_keywords[:word_count]

    filter_note = "self-reference filter" if domain == "other" else "reference DB filter"
    now_str     = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = (
        f"SPASM Synopsis — {word_count} keywords\n"
        f"{'='*50}\n"
        f"Source  : {fpath.name}\n"
        f"Domain  : {domain}\n"
        f"Filter  : {filter_note}\n"
        f"Date    : {now_str}\n"
        f"{'='*50}\n\n"
        + ", ".join(final_keywords)
        + "\n\n[Generated by SPASM v2.1 — GPL3 — free for all, profit for none]\n"
    )

    try:
        synopsis_path.write_text(content, encoding="utf-8")
    except Exception as e:
        return "", [], "", f"Could not write synopsis: {e}"

    conn = sqlite3.connect(SPASM_DB)
    reg  = conn.execute(
        "SELECT id FROM spasm_registry WHERE original_path=?", (str(fpath),)).fetchone()
    if reg:
        conn.execute("""
            INSERT OR IGNORE INTO spasm_synopses
            (registry_id, word_count, synopsis_path, is_human, created_ts)
            VALUES (?,?,?,0,?)
        """, (reg[0], word_count, str(synopsis_path), int(time.time())))
        conn.commit()
    conn.close()

    print(f"  [SPASM] Synopsis: {str(synopsis_path)[-60:]}")
    return str(synopsis_path), final_keywords, domain, ""



# =============================================================================
#  STATS
# =============================================================================

def get_stats():
    s = {"total":0,"parsed":0,"synopses":0}
    try:
        conn = sqlite3.connect(SPASM_DB)
        s["total"]    = conn.execute("SELECT COUNT(*) FROM spasm_registry").fetchone()[0]
        s["parsed"]   = conn.execute(
            "SELECT COUNT(*) FROM spasm_registry WHERE parse_status=1").fetchone()[0]
        s["synopses"] = conn.execute(
            "SELECT COUNT(*) FROM spasm_synopses WHERE is_human=0").fetchone()[0]
        conn.close()
    except Exception: pass
    return s


# =============================================================================
#  HTTP SERVER
# =============================================================================

class SPASMHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  [SPASM:{datetime.now().strftime('%H:%M:%S')}] {fmt % args}")

    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200); self.send_cors(); self.end_headers()

    def _send_json(self, obj, status=200):
        r = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status); self.send_cors()
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(r)))
        self.end_headers(); self.wfile.write(r)

    def _send_html(self, html):
        r = html.encode("utf-8")
        self.send_response(200); self.send_cors()
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Content-Length",str(len(r)))
        self.end_headers(); self.wfile.write(r)

    def _read_body(self):
        length = int(self.headers.get("Content-Length",0))
        body   = self.rfile.read(length)
        try: return json.loads(body.decode("utf-8"))
        except Exception: return {}

    def do_GET(self):
        if self.path in ("/","/index.html"):
            gui_path = Path(__file__).parent / "spasm_gui.html"
            if gui_path.exists():
                self._send_html(gui_path.read_text(encoding="utf-8"))
            else:
                self._send_html("<h1>spasm_gui.html not found</h1>")
        elif self.path == "/health":
            self._send_json({
                "status":     "SPASM v2.1",
                "phi":        PHI,
                "spasm_dir":  str(SPASM_DIR),
                "ref_db":     "present" if Path(REF_DB).exists() else "not built",
                "stats":      get_stats(),
            })
        elif self.path == "/domains":
            self._send_json(DOMAINS + ["other"])
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path == "/parse":
            data = self._read_body()
            fp   = data.get("filepath","").strip()
            if not fp:
                self._send_json({"ok":False,"error":"filepath required."}); return
            fpp, dom, kws, err = do_fullparse(fp)
            if err:
                self._send_json({"ok":False,"error":err}); return
            self._send_json({"ok":True,"fullparse_path":fpp,
                             "domain":dom,"kw_count":len(kws)})

        elif self.path == "/synopsis":
            data  = self._read_body()
            fp    = data.get("filepath","").strip()
            wc    = int(data.get("word_count",150))
            udom  = data.get("domain","").strip()
            if not fp:
                self._send_json({"ok":False,"error":"filepath required."}); return
            sp, kws, dom, err = do_synopsis(fp, wc, udom)
            if err == "already_exists":
                self._send_json({"ok":True,"already_done":True,
                                 "synopsis_path":sp,
                                 "message":f"Already done. File at: {sp}"}); return
            if err:
                self._send_json({"ok":False,"error":err}); return
            self._send_json({"ok":True,"already_done":False,
                             "synopsis_path":sp,"domain":dom,"kw_count":len(kws)})

        else:
            self.send_response(404); self.end_headers()


# =============================================================================
#  MAIN
# =============================================================================

def main():
    if "--build-ref" in sys.argv:
        print("\n" + "="*60)
        print("  SPASM — Building Reference Database")
        print("="*60)
        build_ref_db(); return

    if "--add-ref" in sys.argv:
        idx = sys.argv.index("--add-ref")
        if idx + 1 < len(sys.argv):
            build_ref_db(single_file=sys.argv[idx+1])
        else:
            print("  Usage: python3 spasm_server.py --add-ref /path/to/file.pdf")
        return

    print("\n" + "="*60)
    print("  SPASM v2.1 — Student's Personal Assistant Synopsis Maker")
    print("  Srishti Nested Spherical Shell Architecture")
    print("  Venkatesh (CI) + Claudie (SI) — GPL3")
    print("="*60)
    print(f"  Folder    : {SPASM_DIR}")
    print(f"  spasm.db  : {SPASM_DB}")
    print(f"  query.db  : {QUERY_DB}")
    print(f"  ref.db    : {REF_DB}")
    print(f"  reference : {REF_FOLDER}")
    print(f"  Domains   : {len(DOMAINS)} loaded")
    print(f"  phi       : {PHI:.10f}")
    print("="*60)
    print("  BACKUP spasm.db AND query_synopsis.db REGULARLY")
    print("="*60)

    ensure_dbs()

    if not Path(REF_DB).exists():
        print(f"\n  spasm_ref.db not found — run --build-ref after adding files to reference/")
        print(f"  SPASM works without it — Other domain uses self-filter.\n")

    s = get_stats()
    print(f"\n  Files    : {s['total']}  |  Parsed : {s['parsed']}"
          f"  |  Synopses : {s['synopses']}")
    print(f"\n  Open browser: http://localhost:{PORT}")
    print("  Ctrl+C to stop\n")

    server = ThreadingHTTPServer((HOST, PORT), SPASMHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  [SPASM] Stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
