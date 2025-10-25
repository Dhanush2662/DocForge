# DocQuest Extractor

A document processing pipeline that extracts content from PDFs, classifies text elements, extracts images, and provides a review dashboard interface.

## Project Structure

```
docquest-extractor/
├─ data/
│  ├─ raw_blocks.json           # Raw text blocks extracted from documents
│  ├─ classified_output.json   # Text blocks with classification (question, answer, title, etc.)
│  ├─ question_assets.json     # Extracted Q&A pairs
│  ├─ review_state.json        # Review status tracking for each block
│  ├─ approved_output.json     # Final approved content
│  └─ images/                  # Extracted images from PDFs
├─ scripts/
│  ├─ parse_pdf.py             # Extract text from PDF documents
│  ├─ classify_text.py         # Classify text blocks into types
│  └─ extract_images.py        # Extract images from PDF documents
├─ review_dashboard/
│  ├─ backend/                 # Flask server for the review interface
│  └─ frontend/                # HTML/CSS/JS for the review interface
└─ db/
   ├─ upload_to_db.py          # Upload processed data to database
   └─ .env.example             # Environment variables example
```

## Setup and Installation

1. Install required Python packages:
```bash
pip install PyPDF2 PyMuPDF flask
```

2. Set up environment variables:
```bash
cp db/.env.example .env
# Edit .env with your specific configuration
```

## Usage

### 1. Extract Text from PDF
```bash
cd scripts
python parse_pdf.py
```
This will extract text blocks from `input.pdf` and save them to `../data/raw_blocks.json`.

### 2. Classify Text Blocks
```bash
cd scripts
python classify_text.py
```
This will classify the raw text blocks and save the results to `../data/classified_output.json`.

### 3. Extract Images from PDF
```bash
cd scripts
python extract_images.py
```
This will extract images from `input.pdf` and save them to `../data/images/`.

### 4. Run Review Dashboard
```bash
cd review_dashboard/backend
python app.py
```
Visit `http://localhost:5000` to access the review dashboard where you can review and approve content.

### 5. Upload to Database
```bash
cd db
python upload_to_db.py
```
This will upload the processed data to a SQLite database.

## Configuration

Environment variables can be set in a `.env` file:
- `INPUT_PDF`: Path to the input PDF file
- `OUTPUT_JSON`: Path for output JSON files
- `DB_PATH`: Path to the SQLite database
- `DOCUMENT_ID`: Identifier for the current document being processed

## Data Flow

1. PDF documents are parsed to extract raw text blocks
2. Text blocks are classified into different types (questions, answers, titles, etc.)
3. Images are extracted separately from the PDF
4. A review dashboard allows for manual verification and approval
5. Approved content is stored in the final output files
6. All data can be uploaded to a database for further processing

## Output Formats

The system supports multiple export formats:
- JSON: Structured data with metadata
- Text: Plain text content
- Markdown: Formatted content with basic styling