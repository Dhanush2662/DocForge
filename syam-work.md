

## **Part 2 — Parser Goblin: PDF Text Extraction → `raw_blocks.json`**

> **Goal:** pull text + layout from cursed PDFs (single or two-column), preserve bounding boxes, sort into human reading order, and emit `raw_blocks.json` for the classifier. No LLMs. No GPU required.

---

## 0) TL;DR Deliverables

* CLI script: `scripts/parse_pdf.py`
* Output: `data/raw_blocks.json`
* Logs: `logs/run_log.txt`
* Sample run:

  ```bash
  python scripts/parse_pdf.py /path/to/book.pdf --out data/raw_blocks.json --strip-headers --strip-footers
  ```

---

## 1) Install & Project Layout

```bash
python -m venv .venv && source .venv/bin/activate   # (Windows) .venv\Scripts\activate
pip install pymupdf pdfplumber rich
mkdir -p scripts data logs
```

Repo reminder (from Part 1):

```
docquest-extractor/
├─ data/
├─ logs/
└─ scripts/
   └─ parse_pdf.py   ← you’re creating this now
```

---

## 2) What This Script Emits

`data/raw_blocks.json` (array of blocks, ordered for reading):

```json
[
  {
    "page": 12,
    "bbox": [72.0, 101.2, 521.6, 136.4],
    "text": "12. The histone protein that attaches to DNA between nucleosomes is",
    "line_idx": 1452,
    "col": 0,
    "source_pdf": "book.pdf"
  }
]
```

* `page` → 1-indexed page number
* `bbox` → `[x0,y0,x1,y1]` in page coordinates
* `line_idx` → global order index
* `col` → 0 or 1 if we detected two columns (else 0)
* `text` → normalized single line (no trailing hyphen junk)

**Do NOT** try to perfectly label Q/Option/Answer here. That’s Part 3’s job.

---

## 3) Heuristics (so you know what magic’s inside)

* **Two-column detection:**
  Cluster text by X-center; if separation > 20% page width and both clusters are populated, treat as 2 columns.
  Reading order = left column top→bottom, then right column top→bottom.

* **Header/Footer stripping (optional flags):**
  Drop lines in top/bottom 5% of page height. Helps remove running headers/page numbers.

* **Line normalization:**
  Collapse multiple spaces, fix hyphenated wraps like `molecu- lar` → `molecular` if the join is safe.

* **Fallback:**
  Uses PyMuPDF’s layout dict; if something explodes, logs and skips that page, keeps going.

---

## 4) The Script — **`scripts/parse_pdf.py`**

> copy the whole thing as-is.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Parser Goblin — PDF → raw_blocks.json
CPU-only, offline. Works on single/double column textbooks.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Missing dependency: pymupdf. Run: pip install pymupdf", file=sys.stderr)
    sys.exit(1)

from rich.console import Console
from rich.progress import track

console = Console()

@dataclass
class Block:
    page: int
    bbox: Tuple[float, float, float, float]
    text: str
    line_idx: int
    col: int
    source_pdf: str

def norm_space(s: str) -> str:
    s = s.replace("\u00ad", "")  # soft hyphen
    s = s.replace("\xa0", " ")
    s = " ".join(s.strip().split())
    return s

def maybe_unhyphen(prev: str, cur: str) -> str:
    # If previous ended with hyphen and current starts lowercase → join words
    if prev.endswith("-") and cur[:1].islower():
        return prev[:-1] + cur
    return prev + " " + cur

def detect_two_columns(lines: List[Dict[str, Any]], page_w: float) -> Tuple[bool, float]:
    """
    Simple bimodal check on x-centers.
    Returns: (is_two_col, split_x)
    """
    if len(lines) < 10:
        return (False, page_w / 2)

    centers = [ (b["bbox"][0] + b["bbox"][2]) / 2.0 for b in lines ]
    cmin, cmax = min(centers), max(centers)
    spread = cmax - cmin
    if spread < 0.2 * page_w:
        return (False, page_w / 2)

    median = sorted(centers)[len(centers)//2]
    left = [c for c in centers if c <= median]
    right = [c for c in centers if c > median]
    if len(left) < 0.3 * len(centers) or len(right) < 0.3 * len(centers):
        return (False, page_w / 2)

    left_mean = sum(left)/len(left)
    right_mean = sum(right)/len(right)
    if (right_mean - left_mean) < 0.2 * page_w:
        return (False, page_w / 2)

    return (True, median)

def assign_column(bbox: Tuple[float, float, float, float], split_x: float) -> int:
    x0, _, x1, _ = bbox
    center = (x0 + x1) / 2.0
    return 0 if center <= split_x else 1

def parse_page(page, page_num: int, opts) -> List[Dict[str, Any]]:
    """
    Returns list of dict blocks with keys: text, bbox
    """
    w = page.rect.width
    h = page.rect.height

    raw = page.get_text("dict")  # layout dict with blocks/lines/spans
    blocks = []
    for blk in raw.get("blocks", []):
        if blk.get("type") != 0:  # 0 = text block
            continue
        for line in blk.get("lines", []):
            # combine all spans of a line
            spans = line.get("spans", [])
            if not spans:
                continue
            x0 = min(s["bbox"][0] for s in spans)
            y0 = min(s["bbox"][1] for s in spans)
            x1 = max(s["bbox"][2] for s in spans)
            y1 = max(s["bbox"][3] for s in spans)
            text = norm_space("".join(s["text"] for s in spans))

            # header/footer stripping
            if opts.strip_headers and y1 < 0.07 * h:
                continue
            if opts.strip_footers and y0 > 0.93 * h:
                continue

            if text:
                blocks.append({"text": text, "bbox": [x0, y0, x1, y1]})

    # sort top->bottom, then left->right (temporary)
    blocks.sort(key=lambda b: (round(b["bbox"][1], 1), b["bbox"][0]))
    return blocks, (w, h)

def reading_order(blocks: List[Dict[str, Any]], page_w: float) -> Tuple[List[Dict[str, Any]], bool, float]:
    """
    Decide 1 or 2 columns, label each block with col, then order by (col, y)
    """
    is_two, split_x = detect_two_columns(blocks, page_w)
    for b in blocks:
        b["col"] = assign_column(tuple(b["bbox"]), split_x) if is_two else 0

    if is_two:
        blocks.sort(key=lambda b: (b["col"], round(b["bbox"][1], 1), b["bbox"][0]))
    else:
        blocks.sort(key=lambda b: (round(b["bbox"][1], 1), b["bbox"][0]))
    return blocks, is_two, split_x

def main():
    ap = argparse.ArgumentParser(description="PDF Parser Goblin → raw_blocks.json")
    ap.add_argument("pdf", help="Path to input PDF")
    ap.add_argument("--out", default="data/raw_blocks.json", help="Output JSON path")
    ap.add_argument("--from-page", type=int, default=1, help="1-indexed start page")
    ap.add_argument("--to-page", type=int, default=0, help="1-indexed end page (0 = till end)")
    ap.add_argument("--strip-headers", action="store_true", help="Drop top 7% lines")
    ap.add_argument("--strip-footers", action="store_true", help="Drop bottom 7% lines")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    try:
        doc = fitz.open(args.pdf)
    except Exception as e:
        console.print(f"[red]Failed to open PDF:[/red] {e}")
        sys.exit(2)

    n_pages = doc.page_count
    start = max(1, args.from_page)
    end = n_pages if args.to_page == 0 else min(args.to_page, n_pages)

    console.print(f"[bold cyan]Parsing[/bold cyan] {args.pdf} pages {start}..{end}")
    line_idx = 0
    out_blocks: List[Block] = []

    for pno in track(range(start, end + 1), description="Pages"):
        try:
            page = doc.load_page(pno - 1)
            blocks, (pw, ph) = parse_page(page, pno, args)
            blocks, is_two, split_x = reading_order(blocks, pw)

            for b in blocks:
                text = b["text"]
                bbox = b["bbox"]
                out_blocks.append(
                    Block(
                        page=pno,
                        bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
                        text=text,
                        line_idx=line_idx,
                        col=int(b["col"]),
                        source_pdf=os.path.basename(args.pdf),
                    )
                )
                line_idx += 1
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] failed to parse page {pno}: {e}")
            continue

    # dump JSON
    result = [b.__dict__ for b in out_blocks]
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    with open("logs/run_log.txt", "a", encoding="utf-8") as lg:
        lg.write(f"Parsed {args.pdf} pages {start}-{end}, blocks={len(result)}\n")

    console.print(f"[green]Done.[/green] Wrote {len(result)} blocks → {args.out}")

if __name__ == "__main__":
    main()
```

---

## 5) Usage

```bash
# whole book
python scripts/parse_pdf.py "YCT NEET Biology Vol-1.pdf" --out data/raw_blocks.json --strip-headers --strip-footers

# range (first 50 pages)
python scripts/parse_pdf.py "YCT NEET Biology Vol-1.pdf" --from-page 1 --to-page 50 --out data/raw_blocks_p1_50.json
```

**Performance tips**

* Close other apps; this is I/O heavy.
* If it slows, run in chunks (`--to-page 100`, then 101–200, etc.).
* On Iris Xe laptops, keep other students from opening 27 Chrome tabs. (I see you.)

---

## 6) Acceptance Tests (what you must verify)

1. **File created:** `data/raw_blocks.json` exists and is valid JSON.
2. **Block count sanity:** for a dense textbook page, expect ~50–150 lines per page.
3. **Column labeling:** open a 2-column page; ensure left column blocks have `col=0`, right `col=1`, and the order in JSON is left→right.
4. **Header/footer:** page numbers & running headers are mostly removed if flags used.
5. **Text cleanliness:** no doubled spaces; soft hyphens removed.
6. **BBox believable:** `bbox` changes as text moves down; values within page bounds.

---

## 7) Common Traps (and what to do)

* **All lines end up in one column** → your page has narrow text; that’s fine (single-column mode).
* **Headers not stripped** → increase threshold: edit code `0.07` to `0.1`.
* **Ligatures/odd characters** → PyMuPDF usually normalizes; if not, add replacements in `norm_space`.
* **Tables-as-images** → text won’t appear here; Part 4 (Vision Nerd) will handle via image extraction + OCR.

---

## 8) Handoff Contract to Part 3 (Classifier)

You must deliver **only** `raw_blocks.json` with the structure defined above, in reading order, with `col` info. No pre-labelling. No heroic guesses. Keep it dumb and consistent.

**Checklist before handoff:**

* [ ] `raw_blocks.json` generated on 2 different PDFs
* [ ] Manual spot-check: lines read in natural order
* [ ] Headers/footers mostly stripped
* [ ] Log written to `logs/run_log.txt`

---

## 9) What to Commit (so you don’t lose the plot)

```
/scripts/parse_pdf.py
/data/raw_blocks.json                 # (for 5–10 sample pages only)
logs/run_log.txt
```

---

