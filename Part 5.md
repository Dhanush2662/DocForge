strap in, lord of chaos. here’s **Part 5 — Review Dashboard + DB integration** in clean Markdown with working backend + frontend skeleton and a Neon insert script. copy–paste, run, then bully your team into using it.

---

# 📘 DocQuest Extraction Bible

## **Part 5 — Review & Integration (Review Dashboard + DB Upload)**

> **Goal:** build the human sanity firewall between AI output and your Neon DB.
> Load `classified_output.json` + `question_assets.json` → let humans edit/approve → export `approved_output.json` → insert into **staging** schema on Neon. No touching prod until it’s clean.

---

## 0) Deliverables (what you’ll create now)

```
review_dashboard/
  backend/
    main.py
    models.py
    storage.py
    requirements.txt
  frontend/
    (Vite React app files)

db/
  upload_to_db.py
  .env.example
```

Run order:

1. Start **backend** (FastAPI)
2. Start **frontend** (React)
3. Review → Approve → Export `approved_output.json`
4. Run `db/upload_to_db.py` to insert into Neon **staging** schema

---

## 1) Backend (FastAPI) — serves data + saves edits

### 1.1 Create `review_dashboard/backend/requirements.txt`

```
fastapi
uvicorn
pydantic
python-multipart
```

### 1.2 `review_dashboard/backend/models.py`

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

class Option(BaseModel):
    label: Optional[str] = None
    text: str
    is_correct: Optional[bool] = None

class Asset(BaseModel):
    type: Literal["diagram","table","equation","unknown"] = "unknown"
    page: Optional[int] = None
    bbox: Optional[List[float]] = None
    image_path: Optional[str] = None
    ocr_text: Optional[str] = ""

class SourceRef(BaseModel):
    pdf: str
    pages: List[int] = []

class ReviewItem(BaseModel):
    temp_id: str
    question_text: str
    options: List[Option] = []
    answer_index: Optional[int] = None
    answer_label: Optional[str] = None
    answer_raw: Optional[str] = None
    explanation: Optional[str] = ""
    question_type_hint: Optional[str] = "single_correct"
    difficulty_id: Optional[int] = 1         # reviewer can edit
    question_type_id: Optional[int] = 1      # reviewer can edit
    topic_id: Optional[int] = None           # reviewer can edit
    confidence: float = 0.0
    manual_review: bool = True
    approved: bool = False
    source: SourceRef
    assets: List[Asset] = []

class ExportQuestion(BaseModel):
    question: Dict[str, Any]
    options: List[Dict[str, Any]]
    explanation: Optional[Dict[str, Any]] = None
    assets: Optional[List[Dict[str, Any]]] = []
```

### 1.3 `review_dashboard/backend/storage.py`

```python
import json, os, shutil
from typing import List, Dict, Any

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
CLASSIFIED = os.path.join(DATA_DIR, "classified_output.json")
ASSETS = os.path.join(DATA_DIR, "question_assets.json")
STATE = os.path.join(DATA_DIR, "review_state.json")
APPROVED = os.path.join(DATA_DIR, "approved_output.json")
IMG_DIR = os.path.join(DATA_DIR, "images")

def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _dump_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def ensure_state():
    """On first run, merge classified_output + question_assets into review_state.json"""
    if os.path.exists(STATE):
        return
    if not os.path.exists(CLASSIFIED):
        raise FileNotFoundError(f"Missing {CLASSIFIED}")
    classified = _load_json(CLASSIFIED)
    asset_map = {}
    if os.path.exists(ASSETS):
        for row in _load_json(ASSETS):
            asset_map[row.get("link_key")] = row.get("assets", [])

    # merge
    merged = []
    for it in classified:
        temp_id = it.get("temp_id")
        it["approved"] = False
        it["difficulty_id"] = it.get("difficulty_id") or 1
        it["question_type_id"] = it.get("question_type_id") or 1
        it["topic_id"] = it.get("topic_id") or None
        it["assets"] = asset_map.get(temp_id, [])
        # normalize asset types
        for a in it["assets"]:
            if a.get("type") not in ("diagram","table","equation"):
                a["type"] = "unknown"
        merged.append(it)
    _dump_json(STATE, merged)

def load_state() -> List[Dict[str, Any]]:
    ensure_state()
    return _load_json(STATE)

def save_state(items: List[Dict[str, Any]]):
    _dump_json(STATE, items)

def export_approved() -> int:
    """Create approved_output.json following DB contract"""
    items = load_state()
    out = []
    count = 0
    for it in items:
        if not it.get("approved"):
            continue
        q = {
            "question_text": it.get("question_text","").strip(),
            "difficulty_id": it.get("difficulty_id") or 1,
            "question_type_id": it.get("question_type_id") or 1,
            "topic_id": it.get("topic_id")
        }
        # options: exactly the text + is_correct
        opts = []
        for idx, o in enumerate(it.get("options", [])):
            opts.append({
                "option_text": o.get("text","").strip(),
                "is_correct": (idx == it.get("answer_index")),
                "option_image": None
            })
        exp = None
        if it.get("explanation"):
            exp = {"explanation_text": it.get("explanation","").strip(), "explanation_image": None}
        assets = []
        for a in it.get("assets", []):
            assets.append({
                "type": a.get("type","unknown"),
                "image_path": a.get("image_path"),
                "ocr_text": a.get("ocr_text","")
            })
        out.append({
            "question": q,
            "options": opts,
            "explanation": exp,
            "assets": assets
        })
        count += 1
    _dump_json(APPROVED, out)
    return count

def replace_asset_file(src_path: str, new_filename: str) -> str:
    os.makedirs(IMG_DIR, exist_ok=True)
    dst = os.path.join(IMG_DIR, new_filename)
    shutil.copy2(src_path, dst)
    return os.path.relpath(dst, start=os.path.join(DATA_DIR))
```

### 1.4 `review_dashboard/backend/main.py`

```python
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from models import ReviewItem, ExportQuestion
import storage, os

app = FastAPI(title="DocQuest Review API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

@app.on_event("startup")
def init():
    storage.ensure_state()

@app.get("/api/stats")
def stats():
    items = storage.load_state()
    total = len(items)
    approved = sum(1 for i in items if i.get("approved"))
    manual = sum(1 for i in items if i.get("manual_review"))
    return {"total": total, "approved": approved, "manual_review": manual}

@app.get("/api/questions")
def list_questions(offset: int=0, limit: int=25, filter: Optional[str]=None, search: Optional[str]=None):
    items = storage.load_state()
    rows = items
    if filter == "manual_review":
        rows = [r for r in rows if r.get("manual_review")]
    if filter == "unapproved":
        rows = [r for r in rows if not r.get("approved")]
    if search:
        s = search.lower()
        rows = [r for r in rows if s in r.get("question_text","").lower()]
    end = min(len(rows), offset+limit)
    return {"items": rows[offset:end], "offset": offset, "limit": limit, "total": len(rows)}

@app.get("/api/questions/{temp_id}")
def get_question(temp_id: str):
    items = storage.load_state()
    for r in items:
        if r.get("temp_id") == temp_id:
            return r
    return {"error": "not_found"}

@app.patch("/api/questions/{temp_id}")
def update_question(temp_id: str, payload: ReviewItem):
    items = storage.load_state()
    for i, r in enumerate(items):
        if r.get("temp_id") == temp_id:
            merged = r.copy()
            merged.update(payload.dict())
            items[i] = merged
            storage.save_state(items)
            return {"ok": True}
    return {"error": "not_found"}

@app.post("/api/questions/{temp_id}/approve")
def approve_question(temp_id: str, approved: bool = Form(...)):
    items = storage.load_state()
    for i, r in enumerate(items):
        if r.get("temp_id") == temp_id:
            r["approved"] = bool(approved)
            items[i] = r
            storage.save_state(items)
            return {"ok": True, "approved": r["approved"]}
    return {"error": "not_found"}

@app.post("/api/upload-asset")
def upload_asset(temp_id: str = Form(...), file: UploadFile = File(...)):
    # save file under data/images
    fname = f"{temp_id}_{file.filename}"
    path_tmp = os.path.join("data", "tmp_upload")
    os.makedirs(path_tmp, exist_ok=True)
    tmp = os.path.join(path_tmp, fname)
    with open(tmp, "wb") as f:
        f.write(file.file.read())
    rel = storage.replace_asset_file(tmp, fname)  # returns relative path under data/
    # attach to item
    items = storage.load_state()
    for i, r in enumerate(items):
        if r.get("temp_id") == temp_id:
            r.setdefault("assets", []).append({
                "type": "diagram",
                "page": None, "bbox": None,
                "image_path": f"data/{rel}",
                "ocr_text": ""
            })
            items[i] = r
            storage.save_state(items)
            return {"ok": True, "image_path": f"data/{rel}"}
    return {"error": "not_found"}

@app.post("/api/export")
def export():
    n = storage.export_approved()
    return {"ok": True, "approved_count": n}
```

**Run backend**

```bash
cd review_dashboard/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

---

## 2) Frontend (React + Vite + Tailwind) — minimal but deadly

### 2.1 Create app

```bash
cd review_dashboard
npm create vite@latest frontend -- --template react-ts
cd frontend
npm i
npm i -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

`tailwind.config.js`

```js
export default { content: ["./index.html","./src/**/*.{ts,tsx}"], theme:{extend:{}}, plugins:[] }
```

`src/index.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

### 2.2 `src/App.tsx` (editor UI)

```tsx
import { useEffect, useMemo, useState } from "react";

type Option = { label?: string; text: string; is_correct?: boolean };
type Asset = { type: string; image_path?: string; ocr_text?: string };
type Item = {
  temp_id: string;
  question_text: string;
  options: Option[];
  answer_index?: number | null;
  explanation?: string;
  difficulty_id?: number | null;
  question_type_id?: number | null;
  topic_id?: number | null;
  confidence?: number;
  manual_review?: boolean;
  approved?: boolean;
  source?: { pdf: string; pages: number[] };
  assets?: Asset[];
};

const API = "http://localhost:8000/api";

export default function App() {
  const [rows, setRows] = useState<Item[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [limit] = useState(20);
  const [filter, setFilter] = useState<"manual_review"|"unapproved"|"" >("manual_review");
  const [search, setSearch] = useState("");
  const [current, setCurrent] = useState<Item | null>(null);
  const [busy, setBusy] = useState(false);
  const pages = useMemo(()=> Math.ceil(total/limit), [total, limit]);

  const load = async (off=0) => {
    const params = new URLSearchParams({ offset: String(off), limit: String(limit) });
    if (filter) params.set("filter", filter);
    if (search) params.set("search", search);
    const res = await fetch(`${API}/questions?${params}`);
    const js = await res.json();
    setRows(js.items || []);
    setTotal(js.total || 0);
    setOffset(js.offset || 0);
    setCurrent((js.items||[])[0] || null);
  };

  useEffect(()=>{ load(0); }, [filter, search]);

  const save = async (item: Item) => {
    setBusy(true);
    const res = await fetch(`${API}/questions/${item.temp_id}`, {
      method: "PATCH",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(item)
    });
    setBusy(false);
    if (!res.ok) alert("save failed");
  };

  const approve = async (id: string, value: boolean) => {
    setBusy(true);
    const form = new FormData();
    form.set("approved", value ? "true" : "false");
    await fetch(`${API}/questions/${id}/approve`, { method:"POST", body: form });
    setBusy(false);
    await load(offset);
  };

  const exportApproved = async () => {
    const r = await fetch(`${API}/export`, { method:"POST" });
    const js = await r.json();
    alert(`Exported ${js.approved_count} approved items to data/approved_output.json`);
  };

  return (
    <div className="min-h-screen grid grid-cols-[320px_1fr] gap-4 p-4">
      {/* Sidebar */}
      <aside className="border rounded-lg p-3 space-y-3">
        <h1 className="text-xl font-bold">DocQuest Review</h1>
        <div className="flex gap-2">
          <input className="border rounded px-2 py-1 w-full" placeholder="search question..."
                 value={search} onChange={e=>setSearch(e.target.value)} />
        </div>
        <div className="flex gap-2">
          <select className="border rounded px-2 py-1 w-full" value={filter} onChange={e=>setFilter(e.target.value as any)}>
            <option value="manual_review">Manual Review</option>
            <option value="unapproved">Unapproved</option>
            <option value="">All</option>
          </select>
        </div>
        <div className="text-sm">Total: {total} | Page {Math.floor(offset/limit)+1} / {pages||1}</div>
        <div className="flex gap-2">
          <button className="border px-2 py-1 rounded w-1/2" disabled={offset===0} onClick={()=>load(Math.max(0, offset-limit))}>Prev</button>
          <button className="border px-2 py-1 rounded w-1/2" disabled={offset+limit>=total} onClick={()=>load(offset+limit)}>Next</button>
        </div>

        <ul className="divide-y max-h-[60vh] overflow-auto">
          {rows.map(r=>(
            <li key={r.temp_id} className={`py-2 px-1 cursor-pointer ${current?.temp_id===r.temp_id?"bg-gray-100":""}`}
                onClick={()=>setCurrent(r)}>
              <div className="text-xs text-gray-500">{r.temp_id}</div>
              <div className="text-sm line-clamp-2">{r.question_text}</div>
              <div className="text-xs">conf: {r.confidence?.toFixed(2)} | {r.manual_review? "🔴 review":"🟢"}</div>
            </li>
          ))}
        </ul>

        <button className="bg-black text-white rounded px-3 py-2 w-full" onClick={exportApproved}>
          Export Approved → approved_output.json
        </button>
      </aside>

      {/* Editor */}
      <main className="border rounded-lg p-4 space-y-4">
        {!current ? <div>no item selected</div> : (
          <>
            <div className="flex justify-between items-center">
              <div className="text-lg font-semibold">{current.temp_id}</div>
              <div className="flex items-center gap-2">
                <span className="text-sm">Approved</span>
                <input type="checkbox" checked={!!current.approved} onChange={e=>approve(current.temp_id, e.target.checked)} />
                <button className="border px-3 py-1 rounded" disabled={busy} onClick={()=>save(current)}>Save</button>
              </div>
            </div>

            <div>
              <label className="text-sm font-medium">Question</label>
              <textarea className="w-full border rounded p-2 h-28"
                        value={current.question_text}
                        onChange={e=>setCurrent({...current, question_text: e.target.value})}/>
              <div className="grid grid-cols-3 gap-2 mt-2">
                <div>
                  <label className="text-xs">Difficulty ID</label>
                  <input className="border rounded p-1 w-full" type="number"
                         value={current.difficulty_id || 1}
                         onChange={e=>setCurrent({...current, difficulty_id: Number(e.target.value)})}/>
                </div>
                <div>
                  <label className="text-xs">Type ID</label>
                  <input className="border rounded p-1 w-full" type="number"
                         value={current.question_type_id || 1}
                         onChange={e=>setCurrent({...current, question_type_id: Number(e.target.value)})}/>
                </div>
                <div>
                  <label className="text-xs">Topic ID</label>
                  <input className="border rounded p-1 w-full" type="number"
                         value={current.topic_id || 0}
                         onChange={e=>setCurrent({...current, topic_id: Number(e.target.value)})}/>
                </div>
              </div>
            </div>

            <div>
              <label className="text-sm font-medium">Options</label>
              <div className="grid grid-cols-2 gap-2">
                {current.options?.map((o, i)=>(
                  <div key={i} className={`border rounded p-2 ${current.answer_index===i?"ring-2 ring-green-500":""}`}>
                    <div className="text-xs mb-1">Label: {o.label || String.fromCharCode(65+i)}</div>
                    <textarea className="w-full border rounded p-2 h-20"
                              value={o.text}
                              onChange={e=>{
                                const opt = [...current.options];
                                opt[i] = {...opt[i], text: e.target.value};
                                setCurrent({...current, options: opt});
                              }}/>
                    <div className="flex items-center gap-2 mt-1">
                      <input type="radio" name="answer" checked={current.answer_index===i}
                             onChange={()=>setCurrent({...current, answer_index: i})}/>
                      <span className="text-xs">Correct</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <label className="text-sm font-medium">Explanation</label>
              <textarea className="w-full border rounded p-2 h-24"
                        value={current.explanation || ""}
                        onChange={e=>setCurrent({...current, explanation: e.target.value})}/>
            </div>

            <div>
              <label className="text-sm font-medium">Assets</label>
              <div className="grid grid-cols-3 gap-3">
                {current.assets?.map((a, i)=>(
                  <div key={i} className="border rounded p-2">
                    {a.image_path ? <img src={a.image_path} className="w-full h-32 object-contain" /> : <div className="h-32 grid place-items-center text-xs">no image</div>}
                    <div className="text-xs mt-1">type: {a.type}</div>
                  </div>
                ))}
              </div>
              <UploadAsset temp_id={current.temp_id} after={async()=>load(offset)} />
            </div>

            <div className="text-xs text-gray-500">
              src: {current.source?.pdf} p.{current.source?.pages?.join(",")}
              {" · "}conf: {current.confidence?.toFixed(2)} {" · "}
              needs review: {current.manual_review ? "yes" : "no"}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function UploadAsset({temp_id, after}:{temp_id:string; after:()=>any}) {
  const [file, setFile] = useState<File|null>(null);
  const upload = async ()=>{
    if (!file) return;
    const fd = new FormData();
    fd.set("temp_id", temp_id);
    fd.set("file", file);
    await fetch("http://localhost:8000/api/upload-asset", { method: "POST", body: fd });
    setFile(null);
    await after();
  };
  return (
    <div className="mt-2 flex gap-2 items-center">
      <input type="file" onChange={e=>setFile(e.target.files?.[0]||null)} />
      <button className="border rounded px-3 py-1" onClick={upload}>Add Asset</button>
    </div>
  );
}
```

**Run frontend**

```bash
npm run dev -- --port 5173
# open http://localhost:5173
```

---

## 3) Export → DB Insertion (Neon, staging schema only)

### 3.1 `db/.env.example`

```
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST/DBNAME
DB_SCHEMA_STAGING=staging_review
```

### 3.2 Install DB deps

```bash
pip install psycopg2-binary python-dotenv
```

### 3.3 `db/upload_to_db.py`

```python
#!/usr/bin/env python3
import os, json, sys
import psycopg2
from dotenv import load_dotenv

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APPROVED = os.path.join(BASE, "data", "approved_output.json")

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)
DATABASE_URL = os.getenv("DATABASE_URL")
SCHEMA = os.getenv("DB_SCHEMA_STAGING", "staging_review")

def load_json(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def connect():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA};")
        # (Assumes tables exist in SCHEMA; if not, create them mirroring prod)

def upsert_batch(rows):
    conn = connect()
    try:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {SCHEMA};")
            inserted = 0
            for row in rows:
                q = row["question"]
                opts = row.get("options", [])
                exp = row.get("explanation")
                assets = row.get("assets", [])

                # Dedup: skip if same question_text + topic_id already exists
                cur.execute("""
                    SELECT question_id FROM questions
                    WHERE lower(question_text) = lower(%s) AND
                          (topic_id IS NOT DISTINCT FROM %s)
                    LIMIT 1;
                """, (q["question_text"], q.get("topic_id")))
                found = cur.fetchone()
                if found:
                    question_id = found[0]
                else:
                    cur.execute("""
                        INSERT INTO questions (topic_id, difficulty_id, question_text, question_image, question_type_id)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING question_id;
                    """, (
                        q.get("topic_id"),
                        q.get("difficulty_id"),
                        q["question_text"],
                        None,
                        q.get("question_type_id")
                    ))
                    question_id = cur.fetchone()[0]

                # options
                for o in opts:
                    cur.execute("""
                        INSERT INTO options (question_id, option_text, is_correct, option_image)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING;
                    """, (question_id, o["option_text"], bool(o.get("is_correct")), o.get("option_image")))

                # explanation
                if exp and exp.get("explanation_text"):
                    cur.execute("""
                        INSERT INTO explanations (question_id, explanation_text, explanation_image)
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING;
                    """, (question_id, exp["explanation_text"], exp.get("explanation_image")))

                # optional: assets table (create in staging if you want)
                # cur.execute("""
                #   INSERT INTO question_assets (question_id, asset_type, asset_image, asset_text)
                #   VALUES (%s, %s, %s, %s)
                # """, ...)

                inserted += 1

        conn.commit()
        print(f"[ok] inserted/upserted {inserted} questions into {SCHEMA}")
    except Exception as e:
        conn.rollback()
        print("[err] transaction failed:", e)
        sys.exit(2)
    finally:
        conn.close()

def main():
    if not os.path.exists(APPROVED):
        print(f"[err] missing {APPROVED}. export from review UI first.")
        sys.exit(1)
    rows = load_json(APPROVED)
    if not rows:
        print("[err] approved_output.json is empty.")
        sys.exit(1)
    upsert_batch(rows)

if __name__ == "__main__":
    main()
```

**Run it**

```bash
# copy .env.example -> .env and fill DATABASE_URL
python db/upload_to_db.py
```

> This writes only to **staging schema** (`staging_review`). When you’re happy, migrate to prod with SQL (`INSERT ... SELECT` between schemas) or your usual migration tool. No cowboy writes to prod.

---

## 4) Acceptance Checklist

* Backend boots: `uvicorn main:app --reload` ✅
* Frontend loads list, lets you edit, toggle **Approved**, save ✅
* Export works → `data/approved_output.json` exists ✅
* DB import inserts rows in **staging** schema, foreign keys valid ✅
* Spot-check in Neon: questions + options + explanations align ✅

---

## 5) Troubleshooting (a.k.a. “how not to cry”)

* **CORS?** Frontend can’t call backend → `allow_origins=["*"]` is already set.
* **Images not showing?** Frontend expects paths relative to repo. Use `data/images/...`.
* **DB auth?** Check `DATABASE_URL` in `.env`.
* **FK errors?** Make sure `difficulties`, `question_types`, `topics` rows exist in staging (mirror prod seeds).
* **Review file vanished?** The backend writes `data/review_state.json`. Back it up like your dignity.

---

## 6) QA Gates Before Touching Prod

* ≥100 random items reviewed manually
* No empty `question_text` or zero options
* For “single_correct” type → exactly one `is_correct=true`
* Staging query sanity:

  ```sql
  SELECT COUNT(*) FROM staging_review.questions;
  SELECT COUNT(*) FROM staging_review.options WHERE is_correct=true;
  SELECT q.question_id, q.question_text
  FROM staging_review.questions q
  LEFT JOIN staging_review.options o ON o.question_id=q.question_id
  WHERE o.question_id IS NULL;  -- should be 0
  ```

---

boom. your sanity firewall is online.
want me to bundle a tiny **README.md** for the repo root so your minions can follow steps 1–5 without pinging you every 10 minutes?
