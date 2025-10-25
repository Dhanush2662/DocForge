# 📘 DocQuest Extraction Bible

## **Part 4 — Vision Nerd: Diagrams / Tables / Equations (OCR flow)**

> **Goal:** find & crop images from PDF pages (diagrams, tables, equations), OCR them, and map them back to their questions via the `temp_id` originating from `classified_output.json`.

---

## 0) Deliverables

* Script: `scripts/extract_images.py`
* Input:

  * `data/classified_output.json` (from Part 3 — has `temp_id`, `source.pdf`, `source.pages`)
  * source PDFs (same folder name as `source.pdf`)
* Output:

  * Crops: `data/images/<pdf>_p<page>_<n>.png`
  * Metadata: `data/question_assets.json` (per `temp_id`)
  * Logs: `logs/ocr_failures.txt`

---

## 1) Install

```bash
# (reuse the venv)
pip install pymupdf paddleocr opencv-python
# (PaddleOCR will also require paddlepaddle; if it errors, do)
# pip install "paddlepaddle==2.5.0" --index-url https://mirror.baidu.com/pypi/simple
```

**Enforce CPU-mode OCR** (we do it in code with `use_gpu=False`).
**No internet required** after first install.

---

## 2) What This Produces

`data/question_assets.json`:

```json
[
  {
    "link_key": "p12_q3",
    "question_id": null,
    "assets": [
      {
        "type": "diagram",
        "page": 12,
        "bbox": [72.1, 320.0, 310.5, 540.2],
        "image_path": "data/images/YCT_NEET_p12_0.png",
        "ocr_text": ""
      },
      {
        "type": "table",
        "page": 12,
        "bbox": [320.3, 330.0, 550.0, 560.0],
        "image_path": "data/images/YCT_NEET_p12_1.png",
        "ocr_text": "Name, Value\nDNA, Double Strand\nRNA, Single Strand"
      }
    ]
  }
]
```

> **type** ∈ `diagram | table | equation` (best-effort heuristic; the Review UI can override).
> **bbox** coordinates are page space `[x0,y0,x1,y1]` (float).

---

## 3) How It Works (simple but mean)

* **Locate image regions** on a page using PyMuPDF layout (`page.get_text("dict")` → blocks with `type==1`).
* **Crop** each region using `page.get_pixmap(clip=Rect(bbox))` → save PNG.
* **Classify** the crop:

  * `table` if we detect many horizontal & vertical lines (OpenCV HoughLinesP heuristic) *or* OCR looks tabular (commas/newlines in regular grid).
  * `equation` if OCR text contains math-y tokens (`=, ≈, ∑, √, ^, _, ( ), /` density).
  * else `diagram`.
* **OCR** each crop with PaddleOCR (CPU).
* **Link to question**:

  * Try to find the question anchor on the page: `page.search_for(first ~40 chars of question_text)`.
  * If found, associate nearby images whose center Y is within `[anchorY - 300, anchorY + 600]`.
  * If not found, attach all page images to that question (the Review UI will fix).

---

## 4) The Script — **`scripts/extract_images.py`**

> paste this whole thing.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Vision Nerd — extract diagrams/tables/equations as images and OCR them
Links assets back to questions via temp_id, using page proximity.

Inputs:
  - data/classified_output.json  (from Part 3)
  - PDFs referenced by entry["source"]["pdf"]
Outputs:
  - data/images/<pdf>_p<page>_<i>.png
  - data/question_assets.json
  - logs/ocr_failures.txt
"""

import argparse
import json
import os
import re
from typing import Any, Dict, List, Tuple

import fitz  # PyMuPDF
import cv2
import numpy as np

from paddleocr import PaddleOCR

# -----------------------
# Utils
# -----------------------

def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def load_json(p: str):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def dump_json(p: str, data: Any):
    ensure_dir(os.path.dirname(p))
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def append_log(p: str, line: str):
    ensure_dir(os.path.dirname(p))
    with open(p, "a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")

def norm(s: str) -> str:
    s = s.replace("\u00ad", "").replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def pdf_basename(pdf_path: str) -> str:
    base = os.path.basename(pdf_path)
    base = re.sub(r"\.pdf$", "", base, flags=re.IGNORECASE)
    base = re.sub(r"[^\w\-]+", "_", base)
    return base

# -----------------------
# Simple heuristics
# -----------------------

MATH_TOKENS = set(list("=+−-*/^_()[]{}√≈≃≤≥∑∏∞πθλμΔ∂"))

def classify_crop_kind(img_path: str, ocr_text: str) -> str:
    """
    Heuristic: detect table/equation/diagram
    - table: many straight lines (Hough) or OCR with repeated separators like ',' and aligned rows
    - equation: high density of math symbols
    - else: diagram
    """
    kind = "diagram"
    try:
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return kind

        h, w = img.shape[:2]
        # skip tiny icons
        if h * w < 40_000:  # ~200x200
            return kind

        # Edge + Hough lines
        edges = cv2.Canny(img, 80, 160)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=80, minLineLength=40, maxLineGap=6)
        line_count = 0 if lines is None else len(lines)

        # crude horizontal/vertical split
        hv_lines = 0
        if lines is not None:
            for l in lines:
                x1, y1, x2, y2 = l[0]
                dx, dy = abs(x2 - x1), abs(y2 - y1)
                if dx < 5 or dy < 5:
                    hv_lines += 1

        # Table hint if many hv lines
        if hv_lines >= 10:
            return "table"

        # Table also if OCR looks grid-ish (many commas/newlines)
        if ocr_text:
            commas = ocr_text.count(",")
            newlines = ocr_text.count("\n")
            if commas + newlines >= 6:
                return "table"

        # Equation hint if many math tokens
        if ocr_text:
            math_hits = sum(1 for ch in ocr_text if ch in MATH_TOKENS)
            if math_hits >= max(5, int(0.02 * len(ocr_text))):
                return "equation"

    except Exception:
        pass

    return kind

# -----------------------
# OCR
# -----------------------

def make_ocr() -> PaddleOCR:
    # CPU mode only
    return PaddleOCR(use_angle_cls=True, lang="en", use_gpu=False)

def ocr_image(ocr: PaddleOCR, img_path: str) -> str:
    try:
        res = ocr.ocr(img_path, cls=True)
        # res is list per image; each item -> list of [box, (text, conf)]
        lines = []
        if isinstance(res, list):
            for item in res:
                if not item:
                    continue
                for det in item:
                    text = det[1][0]
                    lines.append(text)
        return "\n".join(lines).strip()
    except Exception as e:
        append_log("logs/ocr_failures.txt", f"{img_path}: {e}")
        return ""

# -----------------------
# Image extraction helpers
# -----------------------

def extract_image_blocks(page: fitz.Page) -> List[Tuple[fitz.Rect, int]]:
    """
    Return list of (bbox, idx) for image-like blocks.
    Uses page.get_text('dict') blocks with type==1 for images.
    If none found, return [].
    """
    out = []
    try:
        d = page.get_text("dict")
        idx = 0
        W, H = page.rect.width, page.rect.height
        for blk in d.get("blocks", []):
            if blk.get("type") == 1:  # image block
                bbox = blk.get("bbox")
                if not bbox: 
                    continue
                rect = fitz.Rect(bbox)
                # skip minuscule decorations
                if rect.width * rect.height < 20_000:
                    continue
                # skip out-of-bound weirdos
                if rect.x0 < 0 or rect.y0 < 0 or rect.x1 > W+5 or rect.y1 > H+5:
                    continue
                out.append((rect, idx))
                idx += 1
    except Exception:
        pass
    return out

def crop_save(page: fitz.Page, rect: fitz.Rect, out_path: str):
    # upscale a bit for better OCR
    mat = fitz.Matrix(2, 2)
    pix = page.get_pixmap(matrix=mat, clip=rect, alpha=False)
    ensure_dir(os.path.dirname(out_path))
    pix.save(out_path)

# -----------------------
# Anchor mapping (question → nearby images)
# -----------------------

def find_question_anchor(page: fitz.Page, qtext: str) -> List[fitz.Rect]:
    """
    Try to locate the question on the page using first ~40 chars.
    Return list of rectangles (there can be multiple hits).
    """
    snippet = norm(qtext)[:40]
    if len(snippet) < 8:
        return []
    try:
        rects = page.search_for(snippet, quads=False)
        return rects or []
    except Exception:
        return []

def assign_assets_to_questions(pdf_path: str,
                               entries: List[Dict[str, Any]],
                               img_dir: str) -> List[Dict[str, Any]]:
    """
    For each (temp_id, pages) group in `entries`, collect image blocks on those pages,
    crop & OCR them, classify type, and link back to temp_id based on vertical proximity
    to the question anchor.
    """
    doc = fitz.open(pdf_path)
    ocr = make_ocr()
    pdf_key = pdf_basename(pdf_path)

    # build page->image crops cache so we don't render same image twice
    page_cache: Dict[int, List[Dict[str, Any]]] = {}

    def get_page_assets(pno: int) -> List[Dict[str, Any]]:
        if pno in page_cache:
            return page_cache[pno]

        page = doc.load_page(pno - 1)
        blocks = extract_image_blocks(page)

        assets = []
        for i, (rect, idx) in enumerate(blocks):
            img_path = os.path.join(img_dir, f"{pdf_key}_p{pno}_{i}.png")
            crop_save(page, rect, img_path)
            # OCR
            text = ocr_image(ocr, img_path)
            assets.append({
                "page": pno,
                "bbox": [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)],
                "image_path": img_path.replace("\\", "/"),
                "ocr_text": text,
                "type": None  # fill after classify
            })

        # classify kinds
        for a in assets:
            a["type"] = classify_crop_kind(a["image_path"], a.get("ocr_text",""))

        page_cache[pno] = assets
        return assets

    # map entries
    output = []
    for ent in entries:
        link_key = ent.get("temp_id")
        qtext = ent.get("question_text","")
        pages = ent.get("source", {}).get("pages", [])

        assets_for_q: List[Dict[str, Any]] = []
        for pno in pages:
            page = doc.load_page(pno - 1)
            anchors = find_question_anchor(page, qtext)  # list[Rect]
            page_assets = get_page_assets(pno)

            if anchors:
                # associate images near the first anchor
                # take median anchor center Y
                ys = [ (r.y0 + r.y1) / 2.0 for r in anchors ]
                anchor_y = sorted(ys)[len(ys)//2]
                for a in page_assets:
                    ax0, ay0, ax1, ay1 = a["bbox"]
                    cy = (ay0 + ay1) / 2.0
                    if (cy >= anchor_y - 300) and (cy <= anchor_y + 600):
                        assets_for_q.append(a)
            else:
                # no anchor -> attach all page images (UI will correct)
                assets_for_q.extend(page_assets)

        # dedupe by image_path
        seen = set()
        dedup_assets = []
        for a in assets_for_q:
            k = a["image_path"]
            if k in seen:
                continue
            seen.add(k)
            dedup_assets.append(a)

        output.append({
            "link_key": link_key,      # equals temp_id in classified_output.json
            "question_id": None,       # will be set after DB insert if you want reverse mapping
            "assets": dedup_assets
        })

    doc.close()
    return output

# -----------------------
# main
# -----------------------

def main():
    ap = argparse.ArgumentParser(description="Extract OCR assets (diagrams/tables/equations) and link to questions")
    ap.add_argument("--classified", required=True, help="Path to data/classified_output.json")
    ap.add_argument("--pdf-root", default=".", help="Root folder where source PDFs live")
    ap.add_argument("--out", default="data/question_assets.json", help="Output JSON path")
    ap.add_argument("--imgdir", default="data/images", help="Directory to save cropped images")
    args = ap.parse_args()

    ensure_dir(args.imgdir)
    ensure_dir("logs")

    classified = load_json(args.classified)

    # Group entries by source PDF
    by_pdf: Dict[str, List[Dict[str, Any]]] = {}
    for ent in classified:
        src = ent.get("source", {}).get("pdf")
        if not src:
            append_log("logs/ocr_failures.txt", f"missing source.pdf for temp_id={ent.get('temp_id')}")
            continue
        by_pdf.setdefault(src, []).append(ent)

    all_out: List[Dict[str, Any]] = []
    for pdf_name, entries in by_pdf.items():
        pdf_path = os.path.join(args.pdf_root, pdf_name)
        if not os.path.exists(pdf_path):
            append_log("logs/ocr_failures.txt", f"PDF not found: {pdf_path}")
            # still create empty mappings, so downstream code doesn't crash
            for ent in entries:
                all_out.append({"link_key": ent.get("temp_id"), "question_id": None, "assets": []})
            continue

        mapped = assign_assets_to_questions(pdf_path, entries, args.imgdir)
        all_out.extend(mapped)

    dump_json(args.out, all_out)
    print(f"[ok] wrote {len(all_out)} question asset mappings -> {args.out}")

if __name__ == "__main__":
    main()
```

---

## 5) Usage

```bash
# standard run
python scripts/extract_images.py \
  --classified data/classified_output.json \
  --pdf-root . \
  --imgdir data/images \
  --out data/question_assets.json
```

**Where are the PDFs?**
Place them in `--pdf-root` (default: repo root). The script expects file names to match `source.pdf` in your `classified_output.json`.

---

## 6) Acceptance Tests

1. `data/question_assets.json` exists; it has one entry per `temp_id`.
2. `data/images/...png` files are created for pages with images.
3. A few images get **type** = `table` when they clearly have grids; mathy shots get `equation`.
4. At least some crops near the question text are attached (you’ll refine in Review UI anyway).
5. `logs/ocr_failures.txt` exists and is short (no spammy errors).

---

## 7) Troubleshooting (aka “don’t panic”)

* **No images found but page obviously has a scan**
  Some scans embed as a single background image that still appears as `type==1` blocks. If a specific PDF is weird, fallback: change `extract_image_blocks()` to render a full-page crop when none are detected.

* **Crops are tiny/useless**
  Adjust the minimum area filter (`20_000`) or the upscaling factor (`Matrix(2,2)`).

* **OCR gibberish**
  It’s OCR. The Review UI is your sanity layer. You can re-upload a cleaner crop later.

* **Everything tagged `diagram`**
  The heuristics are conservative. The reviewer can flip the type in UI. Or increase Hough thresholds for more `table` hits.

---

## 8) Handoff Contract to Part 5 (Review & Integration)

* This script **does not write to DB**.
* It only creates:

  * `data/question_assets.json` (assets per `temp_id`)
  * crops in `data/images/`
* The Review UI will:

  * show each question with its attached assets,
  * allow re-tagging (diagram/table/equation),
  * allow **replacing** image files,
  * and finally export **`approved_output.json`** (merged with text from Part 3) for DB insert.

