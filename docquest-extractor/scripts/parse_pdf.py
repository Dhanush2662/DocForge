#!/usr/bin/env python3
"""
Script to parse PDF files and extract raw text blocks with metadata
"""
import json
import PyPDF2
import os
from pathlib import Path


def extract_text_blocks(pdf_path):
    """
    Extract text blocks from a PDF file with page and position metadata
    """
    text_blocks = []
    
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            
            # Split text into blocks (paragraphs)
            paragraphs = text.split('\n\n')
            
            for para_num, paragraph in enumerate(paragraphs):
                if paragraph.strip():
                    block = {
                        "id": f"page_{page_num}_block_{para_num}",
                        "page": page_num,
                        "content": paragraph.strip(),
                        "type": "text",
                        "position": para_num
                    }
                    text_blocks.append(block)
    
    return text_blocks


def save_raw_blocks(blocks, output_path):
    """
    Save extracted text blocks to a JSON file
    """
    with open(output_path, 'w', encoding='utf-8') as file:
        json.dump(blocks, file, indent=2, ensure_ascii=False)


def main():
    """
    Main function to parse PDF and save raw blocks
    """
    # Default paths
    input_pdf = os.getenv("INPUT_PDF", "input.pdf")
    output_json = os.getenv("OUTPUT_JSON", "../data/raw_blocks.json")
    
    if not os.path.exists(input_pdf):
        print(f"Error: Input PDF '{input_pdf}' not found")
        return
    
    print(f"Extracting text blocks from {input_pdf}")
    blocks = extract_text_blocks(input_pdf)
    
    print(f"Saving {len(blocks)} blocks to {output_json}")
    save_raw_blocks(blocks, output_json)
    
    print("PDF parsing completed successfully!")


if __name__ == "__main__":
    main()