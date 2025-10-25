| Day   | Section      | Owner              | Deliverable                       |
| ----- | ------------ | ------------------ | --------------------------------- |
| 1–2   | Part 1 Draft | You + Me           | Architecture + Roles + Setup      |
| 3–5   | Part 2 Draft | Me + Parser Goblin | Code + Walkthrough                |
| 6–8   | Part 3 Draft | Me + Classifier    | CPU ML flow                       |
| 9–11  | Part 4 Draft | Me + Vision Nerd   | OCR flow                          |
| 12–14 | Part 5 Draft | Me + You           | Review Dashboard + DB integration |
| 15    | Final        | You + Team         | QA + Git push + Celebrate         |


alright captain chaos, here’s **Part 1 — Architecture + Roles + Setup** in clean Markdown. paste this into `DOCQUEST_HANDBOOK.md` (or `PART-1.md`). no fluff, all signal.

---

# 🧠📘 DocQuest Extraction Bible — **Part 1: Architecture, Roles & Setup**

> **Goal:** define the mission, lock the pipeline, assign roles based on real hardware, and set the rules so nobody derails this into “we made a website” again.

---

## 1) Mission & Scope

**Mission:** semi-automate extraction of **Questions + Options + Correct Answer + Explanation + Assets (diagrams/tables/equations)** from chaotic PDFs into structured JSON, review it in a dashboard, then insert into **Neon Postgres**.

**Scope (what we actually do):**

* Parse multi-column and mixed-layout PDFs.
* Classify text blocks into Q / options / answer / explanation.
* Extract images (diagrams, tables, equations) + OCR when needed.
* Human review & correction page **before** DB insert.
* Output matches production schema (questions/options/explanation/etc.).
  (Key table fields: `questions.question_id, question_text, difficulty_id, question_type_id`; `options.option_id, question_id, option_text, is_correct`; `explanation.explanation_id, question_id, explanation_text`.) 

**Non-goals (don’t even try):**

* 100% fully automatic perfection. We target **~85% auto + 15% manual review**.
* Fancy model training. We’re **offline + CPU-friendly** first.

---

## 2) System Architecture (High-Level)

```
        ┌──────────────┐
PDFs →  │  Parser      │  PyMuPDF/pdfplumber → layout blocks (+ bbox)
        │  (Part 2)    │  regex for Q, options, etc.
        └──────┬───────┘
               │ raw_blocks.json
               ▼
        ┌──────────────┐
        │ Classifier   │  CPU embeddings + rules → group Q/Opt/Ans/Exp
        │  (Part 3)    │  confidence + manual_review flag
        └──────┬───────┘
               │ classified_output.json
               ▼
        ┌──────────────┐
        │  Vision      │  images (diagrams/tables/equations) + OCR
        │  (Part 4)    │  link assets to question_id
        └──────┬───────┘
               │ question_assets.json
               ▼
        ┌──────────────┐
        │ Review UI    │  human edits/approves, fixes assets/answers
        │ (Part 5)     │  approved_output.json
        └──────┬───────┘
               │
               ▼
          Neon Postgres  ← insert script (validates schema):contentReference[oaicite:1]{index=1}
```

**Core DB entities we write to:**
`questions`, `options`, `explanation`, plus references like `difficulties`, `question_types`, `topics`. (See consolidated schema dump for exact columns/keys.)

---

## 3) Roles & Hardware (Reality-Based)

### Team hardware you gave:

* **Member A (Parser Goblin):** Radeon **RX 6550M (4 GB VRAM)** + 8 GB RAM — can handle heavier parsing + occasional OCR.
* **Member B (Classifier):** **Intel Iris Xe (integrated)**, **16 GB system RAM**, DirectX 12, WDDM 3.1; VRAM 128 MB, ~8 GB shared — perfect for **CPU embeddings + clustering**.
* **Member C (Vision Nerd):** Intel Iris Xe (integrated), **6–8 GB RAM** — **CPU-only OCR**, process page-by-page, no big models.

### Responsibilities (own your lane):

* **A — Parser Goblin (Part 2):**
  PyMuPDF/pdfplumber to extract blocks (text + bbox), detect columns, regex for numbering, dump `raw_blocks.json`.
* **B — Classifier (Part 3):**
  Local embeddings (MiniLM/DistilBERT CPU) + rules to group Q/Options/Answer/Explanation, add confidence + `manual_review`. Output `classified_output.json`.
* **C — Vision Nerd (Part 4):**
  Extract diagrams/tables/equations, run PaddleOCR (CPU), map assets to `question_id`. Output `question_assets.json`.
* **You — Overlord (Part 5 + Governance):**
  Build review dashboard (FastAPI + React), approve → `approved_output.json`, insert into Neon, verify against schema (`questions`, `options`, `explanation`, refs).

**Handoffs (don’t break contracts):**

* Part 2 → Part 3: `raw_blocks.json`
* Part 3 → Part 4/5: `classified_output.json`
* Part 4 → Part 5: `question_assets.json`
* Part 5 → DB: `approved_output.json` → Neon

---

## 4) Environments & Tooling

**Language:** Python 3.11+
**Parsing:** `pymupdf`, `pdfplumber`
**ML (CPU-only):** `sentence-transformers`, `scikit-learn`, `nltk`
**Vision/OCR:** `opencv-python`, `paddleocr` (CPU mode)
**Backend (review API):** FastAPI
**Frontend (review UI):** React + Vite + Tailwind
**DB:** Neon Postgres (prod), plus **staging schema** for safe imports

**Install snippets (baseline):**

```bash
# global
python -m venv .venv && source .venv/bin/activate
pip install pymupdf pdfplumber rich
pip install sentence-transformers scikit-learn nltk
pip install opencv-python paddleocr
pip install fastapi uvicorn pydantic

# frontend (later in Part 5)
npm create vite@latest review_dashboard -- --template react-ts
cd review_dashboard && npm i && npm i -D tailwindcss postcss autoprefixer
```

**Run OCR strictly CPU:**

```python
from paddleocr import PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False)
```

---

## 5) Repos, Folders & Naming

**Mono-repo layout:**

```
docquest-extractor/
├─ data/
│  ├─ raw_blocks.json
│  ├─ classified_output.json
│  ├─ question_assets.json
│  └─ approved_output.json
├─ scripts/
│  ├─ parse_pdf.py          # Part 2
│  ├─ classify_text.py      # Part 3
│  ├─ extract_images.py     # Part 4
│  └─ upload_to_db.py       # Part 5
├─ review_dashboard/
│  ├─ backend/              # FastAPI
│  └─ frontend/             # React + Tailwind
├─ db/
│  ├─ schema.sql            # reference of production schema
│  └─ staging_migrations/   # staging schema for import safety
├─ docs/
│  ├─ PART-1.md (this)
│  ├─ PART-2.md
│  ├─ PART-3.md
│  ├─ PART-4.md
│  └─ PART-5.md
└─ logs/
   ├─ run_log.txt
   └─ ocr_failures.txt
```

**JSON naming:** `snake_case`, deterministic IDs, store relative paths for images: `data/images/q_{question_id}_1.png`.

---

## 6) Data Contracts (what each part must output)

### 6.1 `raw_blocks.json` (Part 2 → Part 3)

```json
[
  {
    "page": 12,
    "bbox": [72, 101, 520, 168],
    "text": "12. The histone protein that ...",
    "line_idx": 234
  }
]
```

### 6.2 `classified_output.json` (Part 3 → Part 5)

```json
[
  {
    "temp_id": "p12_q12",
    "question_text": "The histone protein ...",
    "options": [
      {"text": "H1"}, {"text": "H2A"}, {"text": "H2B"}, {"text": "H3"}
    ],
    "answer_index": 0,
    "explanation": "H1 binds linker DNA ...",
    "confidence": 0.78,
    "manual_review": false,
    "source": {"pdf":"file.pdf","page":12}
  }
]
```

### 6.3 `question_assets.json` (Part 4 → Part 5)

```json
[
  {
    "link_key": "p12_q12",
    "question_id": null,
    "assets": [
      {"type":"diagram","image_path":"data/images/p12_q12_1.png","ocr_text":""},
      {"type":"table","image_path":"data/images/p12_q12_tbl.png","ocr_text":"A,B,C"}
    ]
  }
]
```

### 6.4 `approved_output.json` (Part 5 → DB)

```json
[
  {
    "question": {
      "question_text": "The histone protein ...",
      "difficulty_id": 2,
      "question_type_id": 1,
      "topic_id": 124
    },
    "options": [
      {"option_text":"H1","is_correct":true},
      {"option_text":"H2A","is_correct":false},
      {"option_text":"H2B","is_correct":false},
      {"option_text":"H3","is_correct":false}
    ],
    "explanation": {"explanation_text":"H1 binds linker DNA..."},
    "assets": [
      {"type":"diagram","image_path":"data/images/p12_q12_1.png","ocr_text":""}
    ]
  }
]
```

**Why those fields?** They map straight to production tables **`questions`, `options`, `explanation`** (and ref tables like `difficulties`, `question_types`, `topics`). Validate against the consolidated schema before insert. 

---

## 7) DB Strategy (don’t nuke prod)

* **Never write to prod directly.** Create a **staging schema** (e.g., `staging_review`) mirroring the production tables.
* Validate foreign keys:

  * `questions.difficulty_id` → `difficulties.difficulty_id`
  * `questions.question_type_id` → `question_types.question_type_id`
  * `questions.topic_id` → `topics.topic_id`
  * `options.question_id` → `questions.question_id`
  * `explanation.question_id` → `questions.question_id` 
* Only after **reviewed batch passes** → copy/migrate from staging to prod.

---

## 8) Success Criteria & QA Gates

* **Parsing:** ≥90% of Q lines detected on “clean” PDFs; ≥60% on “chaotic” PDFs.
* **Classification:** ≥80% correct grouping (Q ↔ options ↔ answer ↔ explanation).
* **Assets:** ≥70% of required images/tables/equations linked.
* **Review:** zero empty `question_text`, options ≥2, exactly one `is_correct=true` for single-correct types.
* **DB Insert:** all FKs valid; no orphan `options`/`explanation`.

---

## 9) Daily Reporting (copy this to a Google Sheet)

Columns:

```
date | member | part | tasks_done | sample_output_link | blockers | next_steps
```

If someone writes “researching approach” after Day 2, they owe biryani.

---

## 10) Kickoff Checklist (tick these now)

* [ ] Roles confirmed (A/B/C/You).
* [ ] Everyone can run Python 3.11 + pip env.
* [ ] Repo scaffold created (folders above).
* [ ] A picks 2 sample PDFs; B & C get them too.
* [ ] Staging schema ready on Neon (no writes to prod).
* [ ] This document read end-to-end without crying.

---

## 11) Quick Schema Reference (for mapping)

* **questions**: `question_id (PK)`, `topic_id (FK)`, `difficulty_id (FK)`, `question_text`, `question_image`, `question_type_id (FK)`
* **options**: `option_id (PK)`, `question_id (FK)`, `option_text`, `is_correct`, `option_image`
* **explanation**: `explanation_id (PK)`, `question_id (FK)`, `explanation_text`, `explanation_image`
* **refs**: `difficulties (difficulty_id, difficulty_level, difficulty_type)`, `question_types (question_type_id, question_type)`, `topics (topic_id, chapter_id, topic_name)`

---

### Final note

if it isn’t logged, it didn’t happen. if it isn’t in JSON, it doesn’t exist. if someone says “but I thought…”, they run the OCR again.

---

want me to roll straight into **Part 2 — Parser Goblin** next with runnable starter code + test plan?
