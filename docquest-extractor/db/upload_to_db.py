#!/usr/bin/env python3
"""
Script to upload processed data to database
"""
import json
import os
import sqlite3
from pathlib import Path


def create_database_schema(conn):
    """
    Create the necessary tables in the database
    """
    # Create blocks table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS blocks (
            id TEXT PRIMARY KEY,
            page INTEGER,
            content TEXT,
            type TEXT,
            position INTEGER,
            document_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create documents table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            filename TEXT,
            original_path TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create QA pairs table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS qa_pairs (
            id TEXT PRIMARY KEY,
            question TEXT,
            answer TEXT,
            document_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()


def upload_blocks_to_db(blocks, db_path, document_id):
    """
    Upload blocks to the database
    """
    conn = sqlite3.connect(db_path)
    create_database_schema(conn)
    
    for block in blocks:
        conn.execute(
            'INSERT OR REPLACE INTO blocks (id, page, content, type, position, document_id) VALUES (?, ?, ?, ?, ?, ?)',
            (
                block.get("id", ""),
                block.get("page", 0),
                block.get("content", ""),
                block.get("type", "paragraph"),
                block.get("position", 0),
                document_id
            )
        )
    
    conn.commit()
    conn.close()
    print(f"Uploaded {len(blocks)} blocks to database")


def upload_qa_pairs_to_db(qa_pairs, db_path, document_id):
    """
    Upload QA pairs to the database
    """
    conn = sqlite3.connect(db_path)
    create_database_schema(conn)
    
    for i, pair in enumerate(qa_pairs):
        qa_id = f"qa_{document_id}_{i}"
        conn.execute(
            'INSERT OR REPLACE INTO qa_pairs (id, question, answer, document_id) VALUES (?, ?, ?, ?)',
            (
                qa_id,
                pair.get("question", ""),
                pair.get("answer", ""),
                document_id
            )
        )
    
    conn.commit()
    conn.close()
    print(f"Uploaded {len(qa_pairs)} QA pairs to database")


def main():
    """
    Main function to upload data to database
    """
    # Default paths
    input_json = os.getenv("INPUT_JSON", "../data/classified_output.json")
    qa_json = os.getenv("QA_JSON", "../data/question_assets.json")
    db_path = os.getenv("DB_PATH", "docquest.db")
    document_id = os.getenv("DOCUMENT_ID", "default_doc")
    
    if not os.path.exists(input_json):
        print(f"Error: Input JSON '{input_json}' not found")
        return
    
    # Upload classified blocks
    with open(input_json, 'r', encoding='utf-8') as file:
        blocks = json.load(file)
    
    upload_blocks_to_db(blocks, db_path, document_id)
    
    # Upload QA pairs if the file exists
    if os.path.exists(qa_json):
        with open(qa_json, 'r', encoding='utf-8') as file:
            qa_pairs = json.load(file)
        
        upload_qa_pairs_to_db(qa_pairs, db_path, document_id)
    
    print(f"Data upload completed successfully to {db_path}!")


if __name__ == "__main__":
    main()