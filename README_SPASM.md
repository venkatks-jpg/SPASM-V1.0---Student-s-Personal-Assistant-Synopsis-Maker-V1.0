Wednesday 01 April 2026 12:42 UTC

# SPASM v2.1 — Student's Personal Assistant Synopsis Maker

> **Student edition — offline, no API key needed, no cost.**

**Author:** Dr. K.S. Venkatesh (CI)
**Assisted by:** Claude (SI) — Claudie instance and Watson filter by ChatGPT
**License:** GNU GPL 3.0 — free for all, profit for none
**Based on:** [Srishti Nested Spherical Shell Database](https://github.com/venkatks-jpg/Srishti_v2.0_Nested_Shells_Spherical_DB)
**φ = 1.6180339887498948482…**

---

## What Is SPASM?

SPASM reads your textbooks and study materials (PDF or TXT) and creates a **Raw Synopsis** — the most important keywords extracted from the book, filtered against a reference vocabulary for your subject domain.

Fast. No internet needed. No API key. No cost. Works on any old machine.

Think of it as: *"Should I read this book?"* answered in 30 seconds.

---

## What You Need

- Python 3.10 or later — check with `python3 --version`
- A terminal (Linux/Mac) or Command Prompt (Windows)
- Any browser (Firefox, Chrome, etc.)
- `pdftotext` — optional but recommended for PDFs
  - Linux: `sudo apt install poppler-utils`
  - Mac: `brew install poppler`
  - Windows: download from https://poppler.freedesktop.org

No other installs. No virtual environments. No nonsense.

---

## Folder Contents

After unzipping SPASM you should have:

```
spasm/
├── spasm_server.py        ← the engine (do not move this)
├── spasm_gui.html         ← the browser interface (do not move this)
├── domain_reference.json  ← domain vocabulary map (from Srishti project)
├── README.md              ← this file
└── reference/             ← put your encyclopedias and dictionaries here
```

All databases (`spasm.db`, `query_synopsis.db`, `spasm_ref.db`) are created automatically inside the spasm/ folder on first run.

**Portable:** Copy the entire spasm/ folder to a pendrive. Run it from there. All files stay together.

---

## First Time Setup

### Step 1 — Add reference material (recommended)

Place PDF or TXT encyclopedias and dictionaries in the `reference/` folder. Examples:

- `Physics Dictionary.pdf`
- `Encyclopedia of Biology.txt`
- `Medical Dictionary.pdf`

Only PDF and TXT formats accepted. Convert other formats first.

### Step 2 — Build the reference database

```bash
python3 spasm_server.py --build-ref
```

Run once. To add more files later:

```bash
python3 spasm_server.py --add-ref /path/to/new_dictionary.pdf
```

### Step 3 — Start SPASM

```bash
python3 spasm_server.py
```

Leave this terminal open.

### Step 4 — Open your browser

Go to: **http://localhost:7520**

Two panels: Parse | Synopsis

---

## How to Use

### Step 1 — Parse (always first)

Click **Parse**. Type the full path to your book.

```
Linux/Mac : /home/student/books/physics_textbook.pdf
Windows   : C:\Users\Student\books\physics_textbook.pdf
```

SPASM reads the first 15% of the file, extracts keywords using the Watson algorithm, and writes `physics_textbook_fullparse.txt` alongside your original. Path is auto-filled in Synopsis panel.

Already parsed files are **not** re-parsed — existing parse is reused instantly.

### Step 2 — Synopsis

Click **Synopsis**. Select domain from dropdown:

- Subject in list → select it. Reference DB vocabulary filters the keywords.
- Subject **not** in list → select **Other (self-filter)**. Book filters against itself.
- **Auto-detect** → SPASM guesses from the keywords.

Select keyword count (50–500). Click **Create Synopsis**.

Writes `physics_textbook_synopsis150.txt` alongside the original. Multiple counts coexist — `synopsis50.txt` and `synopsis200.txt` are independent. Nothing is overwritten.

> **Want the Human Synopsis?** That feature is in **PRISM** — the professional version of this tool.
> A student who wants it can get a free Mistral API key at https://console.mistral.ai and run PRISM.
> This is GPL3 — the code is open. You can figure it out. You are smart enough.

---

## Where Are the Output Files?

All output files written **alongside your original book file**.

```
Original  : /home/student/books/physics_textbook.pdf
Full parse: /home/student/books/physics_textbook_fullparse.txt
Synopsis  : /home/student/books/physics_textbook_synopsis150.txt
```

The databases record only **paths** — not content.
**The database is a map, not a warehouse.**

---

## Using Srishti With SPASM

Use `aria_incremental_rectified.py` from the [Srishti project](https://github.com/venkatks-jpg/Srishti_v2.0_Nested_Shells_Spherical_DB) to add reference files. Then:

```bash
python3 spasm_server.py --add-ref /path/to/new_file.pdf
```

Srishti organises your library. SPASM uses its reference collection. Two projects, one team.

---

## Backup

Back up regularly:

```
spasm/spasm.db
spasm/query_synopsis.db
```

Synopsis text files are safe — they live alongside your books. Only the registry is in the database.

**Linux:** If spasm/ is on a Timeshift partition, you are already covered.

---

## Common Problems

**"File not found"** — Check the full path. Linux is case-sensitive: `Fiction/` ≠ `fiction/`

**"PDF produced no text"** — Scanned PDF. Convert to TXT with an OCR tool first.

**"File not yet parsed. Run Parse first."** — Always Parse before Synopsis.

**Server not responding** — Make sure `python3 spasm_server.py` is running. Use `http://` not `https://`.

**pdftotext not found** — Install poppler-utils. Fallback: `pip install pypdf --break-system-packages`

---

## For Those Who Read Till the End

### Big books — the Feynman method

A book like Feynman's Lectures on Physics is so dense every word matters. Split it into chapters: `chapter_01.txt`, `chapter_02.txt` and so on in one folder. Run SPASM on each chapter separately — parse, synopsis,for human synopsis if you are a student and smart enough you know how!! Collect all the human synopses and you have a digested short version of three volumes.

### Equations

Copy the equation into `eq01.txt`. Copy the surrounding explanation (above, below, beside it in the original) into `eq_exp.txt`. Run `eq_exp.txt` through SPASM. Paste the synopsis back next to your equation. Condensed equation with meaning attached.

### Images

Same principle for any image in any subject. Copy the surrounding explanation text into a txt file, run it through SPASM. The image stays in the original. The meaning comes out as a synopsis.

### Adding new domains

If your subject is not in the dropdown, add a reference file for it to `reference/` and run `--build-ref`. The domain is detected from the filename automatically. **Update your reference DB. Back up all DBs periodically. You lose, you suffer — you are the only one responsible.**

---

## Licence

GNU General Public License v3.0
Free for all. Profit for none.

You may use, modify, and distribute SPASM freely.
Any derivative work must carry the same licence.

*"The intelligence is in the geometry."*

**Dr. K.S. Venkatesh — Chennai, India — 2026**
φ = 1.6180339887498948482…

---
