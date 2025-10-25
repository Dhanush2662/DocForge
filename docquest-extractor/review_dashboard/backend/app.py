#!/usr/bin/env python3
"""
Backend server for the review dashboard
"""
from flask import Flask, request, jsonify, render_template
import json
import os
from pathlib import Path


app = Flask(__name__, template_folder='templates', static_folder='static')

# Default data paths
DATA_DIR = os.getenv("DATA_DIR", "../../data")
RAW_BLOCKS_PATH = os.path.join(DATA_DIR, "raw_blocks.json")
CLASSIFIED_OUTPUT_PATH = os.path.join(DATA_DIR, "classified_output.json")
REVIEW_STATE_PATH = os.path.join(DATA_DIR, "review_state.json")
APPROVED_OUTPUT_PATH = os.path.join(DATA_DIR, "approved_output.json")


def load_json_file(filepath):
    """Load JSON file, return empty dict/list if file doesn't exist"""
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as file:
            return json.load(file)
    else:
        # Return appropriate empty structure based on filename
        if "blocks" in filepath or "output" in filepath:
            return []
        else:
            return {}


def save_json_file(filepath, data):
    """Save data to JSON file"""
    with open(filepath, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/blocks', methods=['GET'])
def get_blocks():
    """Get all text blocks with their current review status"""
    raw_blocks = load_json_file(RAW_BLOCKS_PATH)
    classified_blocks = load_json_file(CLASSIFIED_OUTPUT_PATH)
    review_state = load_json_file(REVIEW_STATE_PATH)
    
    # Combine raw and classified blocks with review status
    for block in classified_blocks:
        block_id = block.get('id')
        if block_id and review_state.get(block_id):
            block['review_status'] = review_state[block_id].get('status', 'pending')
            block['reviewer'] = review_state[block_id].get('reviewer', '')
            block['notes'] = review_state[block_id].get('notes', '')
        else:
            block['review_status'] = 'pending'
            block['reviewer'] = ''
            block['notes'] = ''
    
    return jsonify(classified_blocks)


@app.route('/api/blocks/<block_id>', methods=['PUT'])
def update_block(block_id):
    """Update the review status of a specific block"""
    data = request.json
    review_status = data.get('review_status')
    reviewer = data.get('reviewer', '')
    notes = data.get('notes', '')
    
    # Load current review state
    review_state = load_json_file(REVIEW_STATE_PATH)
    
    # Update the specific block's review state
    review_state[block_id] = {
        'status': review_status,
        'reviewer': reviewer,
        'notes': notes,
        'updated_at': data.get('updated_at')
    }
    
    # Save updated review state
    save_json_file(REVIEW_STATE_PATH, review_state)
    
    # If approved, add to approved output
    if review_status == 'approved':
        classified_blocks = load_json_file(CLASSIFIED_OUTPUT_PATH)
        approved_blocks = load_json_file(APPROVED_OUTPUT_PATH)
        
        # Find the block to approve
        block_to_approve = next((b for b in classified_blocks if b['id'] == block_id), None)
        if block_to_approve and not any(b['id'] == block_id for b in approved_blocks):
            approved_blocks.append(block_to_approve)
            save_json_file(APPROVED_OUTPUT_PATH, approved_blocks)
    
    return jsonify({'status': 'success'})


@app.route('/api/export', methods=['POST'])
def export_approved():
    """Export approved content to various formats"""
    data = request.json
    format_type = data.get('format', 'json')
    approved_blocks = load_json_file(APPROVED_OUTPUT_PATH)
    
    if format_type == 'json':
        return jsonify(approved_blocks)
    elif format_type == 'text':
        text_content = "\\n\\n".join([block.get('content', '') for block in approved_blocks])
        return text_content
    elif format_type == 'markdown':
        md_content = "\\n\\n".join([
            f"## {block.get('content', '')}" if block.get('type') == 'title' 
            else block.get('content', '') 
            for block in approved_blocks
        ])
        return md_content
    else:
        return jsonify({'error': 'Unsupported format'}), 400


if __name__ == '__main__':
    # Create data directory if it doesn't exist
    os.makedirs(DATA_DIR, exist_ok=True)
    
    app.run(debug=True, host='0.0.0.0', port=5000)