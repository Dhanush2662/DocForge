#!/usr/bin/env python3
"""
Script to classify text blocks into different categories
"""
import json
import os
import re
from pathlib import Path


def classify_block(block):
    """
    Classify a text block into categories like question, answer, title, paragraph, etc.
    """
    content = block.get("content", "")
    block_type = "paragraph"
    
    # Check for question patterns
    question_patterns = [
        r'\?$',
        r'^(what|who|when|where|why|how|is|are|can|do|does|will|would|could|should)\b',
        r'^\d+\.\s+(?!.*\.)',  # Numbered lists that might be questions
        r'^[A-Z][^\.]*\?$'  # Sentences ending with question mark
    ]
    
    for pattern in question_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            block_type = "question"
            break
    
    # Check for answer patterns
    if block_type == "paragraph":
        answer_patterns = [
            r'^(ans|answer):\s*',
            r'^\s*\d+\.\s*[^\.]*$',  # Numbered answers
        ]
        for pattern in answer_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                block_type = "answer"
                break
    
    # Check for titles/headings
    if block_type == "paragraph":
        title_patterns = [
            r'^\s*[A-Z][A-Z\s&]*$',  # All caps (likely titles)
            r'^\d+\.\s+[A-Z].*$',  # Numbered headings
            r'^[IVX]+\.\s+.*$',  # Roman numeral headings
            r'^#{1,6}\s+',  # Markdown-style headings
        ]
        for pattern in title_patterns:
            if re.search(pattern, content):
                block_type = "title"
                break
    
    # Check for list items
    if block_type == "paragraph":
        list_patterns = [
            r'^\s*[-*]\s+',  # Bullet points
            r'^\s*\d+[\.\)]\s+',  # Numbered lists
            r'^\s*[a-z][\.\)]\s+',  # Lowercase letter lists
        ]
        for pattern in list_patterns:
            if re.search(pattern, content):
                block_type = "list_item"
                break
    
    return block_type


def classify_blocks(input_path, output_path):
    """
    Classify all text blocks from input JSON and save to output JSON
    """
    with open(input_path, 'r', encoding='utf-8') as file:
        blocks = json.load(file)
    
    classified_blocks = []
    
    for block in blocks:
        block_type = classify_block(block)
        classified_block = {**block, "type": block_type}
        classified_blocks.append(classified_block)
    
    with open(output_path, 'w', encoding='utf-8') as file:
        json.dump(classified_blocks, file, indent=2, ensure_ascii=False)
    
    # Count and report classifications
    type_counts = {}
    for block in classified_blocks:
        block_type = block["type"]
        type_counts[block_type] = type_counts.get(block_type, 0) + 1
    
    print("Classification results:")
    for block_type, count in type_counts.items():
        print(f"  {block_type}: {count}")


def main():
    """
    Main function to classify text blocks
    """
    # Default paths
    input_json = os.getenv("INPUT_JSON", "../data/raw_blocks.json")
    output_json = os.getenv("OUTPUT_JSON", "../data/classified_output.json")
    
    if not os.path.exists(input_json):
        print(f"Error: Input JSON '{input_json}' not found")
        return
    
    print(f"Classifying text blocks from {input_json}")
    classify_blocks(input_json, output_json)
    
    print(f"Classification completed successfully! Output saved to {output_json}")


if __name__ == "__main__":
    main()