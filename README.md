# 🧩 DocQuest Extraction Pipeline

> **Goal:** semi-automate the extraction of questions, options, answers, explanations, and diagrams from NEET/JEE-style PDFs → review → insert clean data into Neon Postgres.

---

## ⚙️ SYSTEM OVERVIEW

| Part | Name                                  | Owner          | Purpose                                             |
| ---- | ------------------------------------- | -------------- | --------------------------------------------------- |
| 1️⃣  | **Architecture + Roles + Setup**      | You (Overlord) | Define schema, structure, and plan                  |
| 2️⃣  | **Parser Goblin**                     | Radeon guy     | Extract raw text + bounding boxes from PDFs         |
| 3️⃣  | **Classifier**                        | Iris Xe guy    | Group text → Qu

estion, Options, Answer, Explanation |
| 4️⃣  | **Vision Nerd**                       | Iris Xe #2     | Extract diagrams, tables, and equations with OCR    |
| 5️⃣  | **Review Dashboard + DB Integration** | You + Me       | Human review + export + Neon DB insert              |

---

## 🧱 FOLDER STRUCTURE

```
docquest-extractor/
├─ data/
│  ├─ raw_blocks.json
│  ├─ classified_output.json
│  ├─ question_assets.json
│  ├─ review_state.json
│  ├─ approved_output.json
│  └─ images/
│     └─ <pdf>_p<page>_<n>.png
│
├─ scripts/
│  ├─ parse_pdf.py           # Part 2
│  ├─ classify_text.py       # Part 3
│  └─ extract_images.py      # Part 4
│
├─ review_dashboard/         # Part 5
│  ├─ backend/
│  └─ frontend/
│
└─ db/
   ├─ upload_to_db.py
   └─ .env.example
```

---

## 🧩 PARTS SUMMARY

### 🔹 **Part 2 — Parser Goblin**

Extracts raw lines + coordinates from PDFs.
→ Output: `data/raw_blocks.json`

```bash
python scripts/parse_pdf.py "Book.pdf" --out data/raw_blocks.json --strip-headers --strip-footers
```

---

### 🔹 **Part 3 — Classifier**

Groups lines into structured question sets.
→ Output: `data/classified_output.json`

```bash
python scripts/classify_text.py --in data/raw_blocks.json --out data/classified_output.json
```

---

### 🔹 **Part 4 — Vision Nerd**

Extracts diagrams, tables, and equations, runs OCR, and links assets via `temp_id`.
→ Output: `data/question_assets.json` + cropped images in `data/images/`

```bash
python scripts/extract_images.py \
  --classified data/classified_output.json \
  --pdf-root . \
  --imgdir data/images \
  --out data/question_assets.json
```

---

### 🔹 **Part 5 — Review Dashboard**

Local web app for verifying, editing, and approving extracted data.

#### ▶ Backend

```bash
cd review_dashboard/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

#### ▶ Frontend

```bash
cd review_dashboard/frontend
npm install
npm run dev -- --port 5173
```

UI: [http://localhost:5173](http://localhost:5173)

#### ▶ Export Approved

```bash
# From the Review UI (button) or via API:
curl -X POST http://localhost:8000/api/export
```

→ Exports final clean file:
`data/approved_output.json`

---

### 🔹 **DB Upload**

Imports reviewed questions to **staging schema** in Neon.

1. Copy `.env.example` → `.env` and set:

   ```
   DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST/DB
   DB_SCHEMA_STAGING=staging_review
   ```

2. Run:

   ```bash
   python db/upload_to_db.py
   ```

> Writes to `staging_review.questions`, `staging_review.options`, and `staging_review.explanations`.

---

## ✅ REVIEWER CHECKLIST

Before marking **Approved**:

* [ ] `question_text` makes sense
* [ ] ≥2 options exist
* [ ] exactly 1 marked correct (if single_correct)
* [ ] explanation non-empty if available
* [ ] image assets match question
* [ ] difficulty/type/topic IDs set
* [ ] `approved=true`

---

## 🧠 TIPS + TRICKS

* Always back up `data/review_state.json` before major edits.
* If OCR fails, upload a replacement image in the UI.
* Keep PDFs and generated JSONs **in sync** by naming properly.
* Avoid editing JSONs manually unless you enjoy debugging nightmares.

---

## ⚠️ COMMON SCREWUPS

| Problem                      | Cause                            | Fix                                                 |
| ---------------------------- | -------------------------------- | --------------------------------------------------- |
| `no questions detected`      | Parser Goblin misaligned columns | adjust `--strip-headers`/`--strip-footers`          |
| `garbage OCR text`           | low-res image                    | increase scale in `extract_images.py` (Matrix(3,3)) |
| `DB foreign key errors`      | missing lookup rows in Neon      | seed `difficulties`, `question_types`, etc          |
| `UI not loading`             | wrong backend port               | set CORS + check 8000                               |
| `approved_output.json empty` | nobody clicked approve           | go bully the team                                   |

---

## 🧩 PIPELINE SUMMARY (1-line TL;DR)

```
PDF → raw_blocks.json → classified_output.json → question_assets.json
→ review_state.json → approved_output.json → Neon staging schema
```

---

## 🧑‍💻 LICENSE / CREDITS

Built by **The Overlord (You)**
with assistance from **RoastGPT**, the sleepless sarcastic AI project manager.

---

## 🧩 CODE CHANGE

git add .
git commit -m "Describe the change"
git branch -M main
git remote add origin <https://github.com/your-user/your-repo.git>
git push -u origin main