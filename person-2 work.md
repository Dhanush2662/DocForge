# 📘 DocQuest Extraction Bible

## **Part 3 — Classifier & Structurer (CPU-only ML flow)**

> **Goal:** turn `raw_blocks.json` (lines with bbox + order) into clean **question sets**:
>
> * `question_text`
> * `options` (with labels)
> * `answer` (mapped to option index if possible)
> * `explanation`
> * `confidence` and `manual_review`
>
> Output: `data/classified_output.json`

---

## 0) TL;DR Deliverables

* Script: `scripts/classify_text.py`
* Input: `data/raw_blocks.json` (from Part 2)
* Output: `data/classified_output.json`
* Run:

  ```bash
  python scripts/classify_text.py --in data/raw_blocks.json --out data/classified_output.json
  # (optional) enable tiny embeddings for nicer line-merging:
  python scripts/classify_text.py --in data/raw_blocks.json --out data/classified_output.json --with-embed
  ```

---

## 1) Install (CPU-only)

```bash
# (already have python venv from Part 2)
pip install regex scikit-learn
# optional (only if you want semantic help; otherwise skip)
pip install sentence-transformers
```

> **No internet?** Run without `--with-embed`. The rules engine still works.
> **Weak laptops?** Also skip `--with-embed`. Totally fine.

---

## 2) How it Works (brain, but cheap)

* **State machine over ordered lines**:

  * detect **Question start** → collect lines until **Options** begin
  * detect **Options** (A/B/C/D, 1/2/3/4, I/II/III/IV) → collect each, merge wrapped lines
  * detect **Answer** lines (`Ans: B`, `Key: (2)`, `Correct option: A,D`) → map to options
  * detect **Explanation** → collect until next question

* **Confidence score** (0–1):

  * +0.40 base if we found a question
  * +0.20 if ≥2 options
  * +0.20 if answer parsed and mapped to an option label/index
  * +0.10 if explanation present
  * +0.10 if question length ≥ 20 chars
  * **manual_review = true** if `< 0.75`

* **Embeddings (optional)**:

  * If `--with-embed`, use a tiny sentence-transformer to help stitch “wrapped lines” more safely (cosine similarity with the previous line).
  * If not available, we use simple heuristics (indentation/markers/length).

---

## 3) Output Schema (contract to Part 5)

```json
[
  {
    "temp_id": "p12_q3",
    "question_text": "The histone protein that attaches to DNA between nucleosomes is",
    "options": [
      {"label":"A","text":"H1"},
      {"label":"B","text":"H2A"},
      {"label":"C","text":"H2B"},
      {"label":"D","text":"H3"}
    ],
    "answer_index": 0,
    "answer_label": "A",
    "answer_raw": "Ans: (A)",
    "explanation": "H1 binds linker DNA...",
    "question_type_hint": "single_correct",
    "confidence": 0.86,
    "manual_review": false,
    "source": {"pdf":"YCT NEET Biology Vol-1.pdf","pages":[12]}
  }
]
```

* `temp_id` will later serve as the **link_key** for assets in Part 4.
* `question_type_hint` is a guess; the Review UI can override.

---

## 4) The Script — **`scripts/classify_text.py`**

> paste the whole thing as-is.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Classifier & Structurer — raw_blocks.json -> classified_output.json

CPU-only by default. Optional --with-embed uses a tiny sentence-transformer model
to stitch wrapped lines a bit smarter, but is NOT required.

Input contract (from Part 2):
[
  {
    "page": 12,
    "bbox": [72.0, 101.2, 521.6, 136.4],
    "text": "...",
    "line_idx": 1452,
    "col": 0,
    "source_pdf": "book.pdf"
  },
  ...
]
"""

import argparse
import json
import math
import os
import re
from typing import List, Dict, Any, Optional, Tuple

# Optional embedding backend (fail-soft)
EMBED_OK = False
MODEL = None
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    EMBED_OK = True
except Exception:
    EMBED_OK = False
    MODEL = None


def safe_load_json(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_dump_json(path: str, data: Any):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ----------------------------
# regex patterns (tunable)
# ----------------------------
Q_START_RE = re.compile(
    r"""^\s*(?:Q(?:uestion)?\s*[-:.]?\s*)?    # optional 'Q' or 'Question'
         (\d{1,4})?                          # optional explicit number
         [\).:]?\s*                          # ) or . or : after number
         (.*)$                               # the rest
     """,
    re.IGNORECASE | re.VERBOSE,
)

# option markers: A) / (A) / a. / 1) / (1) / I) / (i)
OPT_RE = re.compile(
    r"""^\s*
        (?:\(?\s*([A-Da-d])\s*\)?|           # letter A-D
           \(?\s*([1-9])\s*\)?|              # number 1-9
           \(?\s*((?:i|v|x|I|V|X)+)\s*\)?)   # roman
        [\).\:\-]?\s+(.+)$                   # then text
    """,
    re.VERBOSE,
)

ANS_RE = re.compile(
    r"""^\s*(?:Ans(?:wer)?|Key|Correct\s*(?:Option|Answer))\s*[:.\-–]\s*(.+)$""",
    re.IGNORECASE,
)

EXP_RE = re.compile(
    r"""^\s*(?:Exp(?:lanation)?|Sol(?:ution)?)\s*[:.\-–]?\s*(.*)$""",
    re.IGNORECASE,
)

# helpful signals
QUESTION_LURE = re.compile(r"(which of the following|choose the|correct statement|match the|assertion|reason)", re.IGNORECASE)


def normalize(s: str) -> str:
    s = s.replace("\u00ad", "")  # soft hyphen
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_option(line: str) -> Optional[Tuple[str, str]]:
    m = OPT_RE.match(line)
    if not m:
        return None
    label = m.group(1) or m.group(2) or m.group(3)
    text = m.group(4) if m.lastindex >= 4 else ""
    if not text:
        return None
    # normalize label letter/numeric/roman to uppercase letter if possible
    lab = str(label).strip()
    if lab.isalpha():
        lab = lab.upper()
    return lab, normalize(text)


def parse_answer_labels(s: str) -> List[str]:
    """
    Extract possible answer labels from a string, e.g.:
    '(A)', 'A,D', '2 & 4', 'I, II', 'B and D'
    Returns labels as strings, normalized where possible: letters uppercase, numbers as digits, roman as uppercase.
    """
    s = s.strip()
    # remove surrounding parentheses
    s = re.sub(r"^\((.+)\)$", r"\1", s)

    # split by common separators
    parts = re.split(r"[,\s;/&]+|and", s, flags=re.IGNORECASE)
    parts = [p for p in parts if p]

    out = []
    for p in parts:
        p = p.strip()
        # strip parens like (A)
        p = re.sub(r"^\((.+)\)$", r"\1", p)

        # try letter
        if re.fullmatch(r"[A-Da-d]", p):
            out.append(p.upper())
            continue
        # try number
        if re.fullmatch(r"\d{1,2}", p):
            out.append(p)
            continue
        # try roman
        if re.fullmatch(r"(?:i|v|x|I|V|X)+", p):
            out.append(p.upper())
            continue
    return out


def label_to_index(labels: List[str], lab: str) -> Optional[int]:
    """
    Given option objects with .label ("A","B","1","I" etc), map an answer label to index.
    """
    if lab in labels:
        return labels.index(lab)
    # map letters like 'A'->0, numbers '1'->0
    if re.fullmatch(r"[A-D]", lab) and len(labels) <= 6:
        try:
            return ord(lab) - ord('A')
        except Exception:
            return None
    if re.fullmatch(r"\d{1,2}", lab):
        idx = int(lab) - 1
        if 0 <= idx < len(labels):
            return idx
    # roman fallback: map I->0, II->1, ...
    roman_map = {"I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,"VII":7,"VIII":8,"IX":9}
    if lab in roman_map:
        idx = roman_map[lab] - 1
        if 0 <= idx < len(labels):
            return idx
    return None


def embed_model():
    global MODEL
    if MODEL is None:
        # deliberately small model; downloads once, then cached
        MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return MODEL


def similar(a: str, b: str) -> float:
    if not EMBED_OK:
        return 0.0
    m = embed_model()
    em = m.encode([a, b])
    sim = float(cosine_similarity([em[0]], [em[1]])[0][0])
    return sim


def stitch_wrap(prev: str, cur: str, use_embed: bool) -> Optional[str]:
    """
    Try to join 'cur' to 'prev' when it's probably a wrapped continuation.
    Heuristics first; embeddings optional.
    """
    if not prev:
        return None
    if re.match(r"^\(?[A-Da-d1-9IVXivx]\)?[\).\:\-]\s", cur):
        return None  # starts like an option → don't merge
    if re.match(r"^\s*(Ans|Key|Correct)", cur, re.IGNORECASE):
        return None
    if re.match(r"^\s*(Exp|Sol)", cur, re.IGNORECASE):
        return None

    # if cur starts lowercase and prev doesn't end with punctuation → likely continuation
    if cur[:1].islower() and not re.search(r"[.:;!?]\s*$", prev):
        return prev + " " + cur

    # embed help (optional)
    if use_embed:
        try:
            if similar(prev[-120:], cur[:120]) > 0.65 and len(cur.split()) < 12:
                return prev + " " + cur
        except Exception:
            pass

    # fallback: if cur is short and doesn't look like a new block, merge
    if len(cur) < 40 and not re.match(r"^\s*\d+[\).\s]", cur):
        return prev + " " + cur

    return None


def classify_blocks(blocks: List[Dict[str, Any]], use_embed: bool) -> List[Dict[str, Any]]:
    """
    Walk through raw lines and build question groups.
    """
    results = []
    cur = None
    q_seq_on_page: Dict[int, int] = {}

    def new_temp_id(page: int) -> str:
        k = q_seq_on_page.get(page, 0) + 1
        q_seq_on_page[page] = k
        return f"p{page}_q{k}"

    def finalize_current():
        nonlocal cur
        if not cur:
            return
        # confidence
        conf = 0.0
        if cur.get("question_text"):
            conf += 0.40
        if len(cur.get("options", [])) >= 2:
            conf += 0.20
        if cur.get("answer_index") is not None:
            conf += 0.20
        if cur.get("explanation"):
            conf += 0.10
        if len(cur.get("question_text","")) >= 20:
            conf += 0.10
        cur["confidence"] = round(min(conf, 1.0), 2)
        cur["manual_review"] = (cur["confidence"] < 0.75)

        # type hint
        qt = "single_correct"
        if re.search(r"(select.*correct.*statements|more than one|multiple)", cur.get("question_text",""), re.IGNORECASE):
            qt = "multiple_correct"
        if re.search(r"(assertion.*reason|A\)|R\))", cur.get("question_text",""), re.IGNORECASE):
            qt = "assertion_reason"
        if re.search(r"(integer\s*type|numerical\s*value)", cur.get("question_text",""), re.IGNORECASE):
            qt = "integer"
        cur["question_type_hint"] = qt

        results.append(cur)
        cur = None

    # iterate ordered
    for b in blocks:
        page = int(b.get("page", 0) or 0)
        text = normalize(b.get("text",""))
        if not text:
            continue

        # maybe extend current section if continuation
        if cur:
            # extend last option if wrapping
            if cur.get("options"):
                last = cur["options"][-1]["text"] if cur["options"] else ""
                merged = stitch_wrap(last, text, use_embed)
                if merged:
                    cur["options"][-1]["text"] = normalize(merged)
                    cur["pages"].add(page)
                    continue

            # extend explanation if wrapping
            if cur.get("explanation"):
                merged = stitch_wrap(cur["explanation"], text, use_embed)
                if merged:
                    cur["explanation"] = normalize(merged)
                    cur["pages"].add(page)
                    continue

            # extend question if wrapping and we didn't start options yet
            if not cur.get("options"):
                merged = stitch_wrap(cur.get("question_text",""), text, use_embed)
                if merged:
                    cur["question_text"] = normalize(merged)
                    cur["pages"].add(page)
                    continue

        # detect switches
        # 1) Answer line?
        m_ans = ANS_RE.match(text)
        if cur and m_ans:
            cur["answer_raw"] = normalize(m_ans.group(1))
            # parse potential labels from answer_raw
            labels = [opt["label"] for opt in cur.get("options", [])]
            found = parse_answer_labels(cur["answer_raw"])
            ans_idx = None
            ans_lab = None
            for lab in found:
                idx = label_to_index(labels, lab)
                if idx is not None:
                    ans_idx = idx
                    ans_lab = labels[idx]
                    break
            cur["answer_index"] = ans_idx
            cur["answer_label"] = ans_lab
            cur["pages"].add(page)
            continue

        # 2) Explanation start?
        m_exp = EXP_RE.match(text)
        if cur and m_exp:
            seed = normalize(m_exp.group(1) or "")
            # if explanation already exists, append
            if cur.get("explanation"):
                cur["explanation"] = normalize(cur["explanation"] + (" " + seed if seed else ""))
            else:
                cur["explanation"] = seed
            cur["pages"].add(page)
            continue

        # 3) Option line?
        m_opt = parse_option(text)
        if cur and m_opt:
            lab, opt_text = m_opt
            cur.setdefault("options", []).append({"label": lab, "text": opt_text})
            cur["pages"].add(page)
            continue

        # 4) New Question?
        # trigger if looks like numbered line OR heuristic keywords
        m_q = Q_START_RE.match(text)
        looks_like_q = False
        body = ""
        if m_q:
            num = m_q.group(1)
            body = normalize(m_q.group(2) or "")
            # treat as question if it starts with a number OR contains typical question cues
            looks_like_q = bool(num) or bool(QUESTION_LURE.search(text)) or text.strip().endswith("?")

        if looks_like_q:
            # finalize previous one
            finalize_current()
            cur = {
                "temp_id": new_temp_id(page),
                "question_text": body if body else text,
                "options": [],
                "answer_index": None,
                "answer_label": None,
                "answer_raw": None,
                "explanation": "",
                "confidence": 0.0,
                "manual_review": True,
                "question_type_hint": "single_correct",
                "source": {"pdf": b.get("source_pdf","unknown"), "pages": []},
                "pages": set()
            }
            cur["pages"].add(page)
            continue

        # 5) If inside a question but none of the above matched → treat as continuation to question text
        if cur:
            cur["question_text"] = normalize((cur.get("question_text","") + " " + text).strip())
            cur["pages"].add(page)
            continue

        # 6) Otherwise ignore line (front-matter, headers, junk)
        # pass

    # finalize last
    finalize_current()

    # normalize pages set -> list
    for r in results:
        r["source"]["pages"] = sorted(list(r.pop("pages", set())))

    return results


def main():
    ap = argparse.ArgumentParser(description="Classifier & Structurer — raw_blocks.json -> classified_output.json")
    ap.add_argument("--in", dest="inp", required=True, help="Input raw_blocks.json")
    ap.add_argument("--out", dest="out", default="data/classified_output.json", help="Output JSON path")
    ap.add_argument("--with-embed", action="store_true", help="Use tiny embeddings to help stitch wrapped lines (optional)")
    args = ap.parse_args()

    use_embed = bool(args.with_embed and EMBED_OK)

    if args.with_embed and not EMBED_OK:
        print("[warn] --with-embed requested but sentence-transformers not available; continuing without embeddings.")

    blocks = safe_load_json(args.inp)
    # sort by global order just in case
    blocks.sort(key=lambda b: (int(b.get("page",0)), int(b.get("col",0)), int(b.get("line_idx",0))))

    results = classify_blocks(blocks, use_embed=use_embed)

    # post-pass: if a result has options but no answer, set manual_review true
    for r in results:
        if r.get("options") and r.get("answer_index") is None:
            r["manual_review"] = True

    safe_dump_json(args.out, results)
    print(f"[ok] wrote {len(results)} grouped question sets -> {args.out}")


if __name__ == "__main__":
    main()
```

---

## 5) Usage & Performance Tips

```bash
# default rules-only (fastest, fully offline)
python scripts/classify_text.py --in data/raw_blocks.json --out data/classified_output.json

# with tiny embeddings (optional, a bit slower; downloads once)
python scripts/classify_text.py --in data/raw_blocks.json --out data/classified_output.json --with-embed
```

* Run **per 100–200 pages** if laptops cry.
* If options/explanations spill into next pages — that’s normal. The script groups across pages.

---

## 6) Acceptance Tests

1. `data/classified_output.json` exists and is valid JSON.
2. Each object has: `temp_id`, `question_text`, `options` (0–6), `answer_*`, `explanation`, `confidence`, `manual_review`, `source`.
3. For classic MCQs, you see ≥2 options and **exactly one** `answer_index` (or flagged manual_review).
4. Spot-check a page: question order matches the PDF visually.
5. Low-confidence or weird formats are **flagged**, not hallucinated.

---

## 7) Troubleshooting

* **No questions detected**: your Part-2 parser didn’t pass lines correctly; check `raw_blocks.json` order and content.
* **Options not grouped**: ensure option markers are present (A/B/C/D, 1/2/3/4). If the book uses weird bullets, add to `OPT_RE`.
* **Answers at end-of-book**: you’ll see `answer_index = null`. That’s expected → **manual_review**. (We can add an “answer-keys merger” later.)
* **Everything flagged manual_review**: your PDF is chaos or headers weren’t stripped; tune Part-2 flags and try again.

---

## 8) Handoff Contract to Part 4 & 5

* **Part 4 (Vision Nerd)** will produce `question_assets.json` using the **same `temp_id`** (`p{page}_q{n}`) to link diagrams/tables back here.
* **Part 5 (Review UI)** will load `classified_output.json` + `question_assets.json`, let humans fix anything dumb, and export `approved_output.json` for DB insert.
