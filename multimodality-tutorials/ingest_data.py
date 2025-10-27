

import csv
import os
import fitz  # PyMuPDF
import io
from PIL import Image
import base64
from typing import List, Dict
from openai import OpenAI
import imagehash

import PyPDF2
import pdfplumber

def chunk_pdf_text(pdf_path: str, doc_id: str, metadata: Dict,
                   chunk_size: int = 500, overlap: int = 100) -> List[Dict]:
    """
    Extract and chunk text from PDF.
    
    Args:
        pdf_path: Path to PDF file
        doc_id: Document ID (e.g., "PAY-Policy-UAE-5.0")
        metadata: Dict with lang, region, type, version
        chunk_size: Characters per chunk
        overlap: Character overlap between chunks
    
    Returns:
        List of text chunks with metadata
    """
    chunks = []
    
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        
        for page_num, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            
            if not page_text.strip():
                continue
            
            # Chunk this page's text
            start = 0
            chunk_id = 0
            
            while start < len(page_text):
                end = start + chunk_size
                chunk_text = page_text[start:end]
                
                # Break at sentence if possible
                if end < len(page_text):
                    last_period = chunk_text.rfind('.')
                    if last_period > chunk_size * 0.7:
                        end = start + last_period + 1
                        chunk_text = page_text[start:end]
                
                chunks.append({
                    'text': chunk_text.strip(),
                    'metadata': {
                        'source_type': 'pdf',
                        'content_type': 'text',
                        'doc_id': doc_id,
                        'page': page_num + 1,
                        'chunk_id': chunk_id,
                        **metadata  # Add lang, region, type, version
                    }
                })
                
                chunk_id += 1
                start = end - overlap
    
    return chunks

def _table_to_text(table: List[List]) -> str:
    """Convert table to natural language text."""
    if not table or len(table) == 0:
        return ""
    
    text_parts = []
    headers = table[0]
    
    # Add headers
    text_parts.append("Columns: " + " | ".join(str(h) for h in headers))
    
    # Add rows
    for row_idx, row in enumerate(table[1:], 1):
        row_text = " | ".join(str(cell) for cell in row)
        text_parts.append(f"Row {row_idx}: {row_text}")
    
    return "\n".join(text_parts)


def _table_to_markdown(table: List[List]) -> str:
    """Convert table to markdown format."""
    if not table or len(table) == 0:
        return ""
    
    lines = []
    
    # Headers
    headers = table[0]
    lines.append("| " + " | ".join(str(h) for h in headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    
    # Rows
    for row in table[1:]:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    
    return "\n".join(lines)



def detect_visual_type(image_pil: Image.Image, openai_client: OpenAI) -> str:
    """
    Use GPT-4 Vision to classify the visual type.
    
    Returns: 'flowchart', 'bar_chart', 'line_chart', 'pie_chart', 'table', 'diagram', 'other'
    """
    # Convert to base64
    buffered = io.BytesIO()
    image_pil.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()

    
    prompt = """Classify this image into ONE of these categories:
    
    1. flowchart - Process flows, decision trees, workflow diagrams
    2. bar_chart - Bar graphs showing comparisons
    3. line_chart - Line graphs showing trends
    4. pie_chart - Pie or donut charts
    5. table - Structured data in rows and columns
    6. diagram - Technical diagrams, architecture, illustrations
    7. other - Screenshots, photos, or unclear images

    Respond with ONLY the category name, nothing else."""
        
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img_base64}",
                            "detail": "low"  # Faster and cheaper
                        }
                    }
                ]
            }
        ],
        max_tokens=50,
        temperature=0
    )
    
    visual_type = response.choices[0].message.content.strip().lower()
    return visual_type


def chunk_pdf_tables(pdf_path: str, doc_id: str, metadata: Dict, output_dir='temp-images') -> List[Dict]:
    """
    Extract tables from PDF pages.
    Each table becomes one chunk.
    
    Args:
        pdf_path: Path to PDF file
        doc_id: Document ID
        metadata: Dict with lang, region, type, version
    
    Returns:
        List of table chunks with metadata
    """
    chunks = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            
            for table_idx, table in enumerate(tables):
                if not table:
                    continue
                
                print(f"    🗄️  Extracted table on page {page_num + 1}, table {table_idx + 1}")
                # Convert table to text format
                table_text = _table_to_text(table)
                print(f"       Table text preview: {table_text[:100]}...")
                
                # Convert to markdown for LLM consumption
                table_markdown = _table_to_markdown(table)


                 # Save table as CSV
                csv_filename = f"{doc_id}_page{page_num+1}_table{table_idx+1}.csv"
                csv_path = os.path.join(output_dir, csv_filename)
                os.makedirs(output_dir, exist_ok=True)
                
                with open(csv_path, "w", newline='', encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerows(table)
                
                print(f"💾 Saved table to {csv_path}")

                
                print(f"       Table markdown preview:\n{table_markdown[:200]}...\n")
                chunks.append({
                    'text': f"[TABLE]\n{table_text}",
                    "type" : "table",
                    'metadata': {
                        'source_type': 'pdf',
                        'content_type': 'table',
                        'doc_id': doc_id,
                        'page': page_num + 1,
                        'table_id': f"table_{page_num}_{table_idx}",
                        'table_markdown': table_markdown,
                        **metadata
                    }
                })
    
    return chunks

def chunk_pdf_visuals_improved(
    pdf_path: str,
    doc_id: str,
    metadata: Dict,
    openai_client: OpenAI,
    min_image_size: int = 10000,
    output_dir='temp-images'
) -> List[Dict]:
    doc = fitz.open(pdf_path)
    visual_chunks = []
    seen_hashes = {}  # Track unique images
    
    print(f"\n🔍 Analyzing visuals in {doc_id}...")
    print(f"  📄 Total pages: {len(doc)}")
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        print(f"  ➡️  Processing page {page_num + 1}...")
        image_list = page.get_images(full=True)
        
        if not image_list:
            continue
        
        print(f"  📄 Page {page_num + 1}: Found {len(image_list)} image(s)")
        
        for img_index, img in enumerate(image_list):
            try:
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                image_pil = Image.open(io.BytesIO(image_bytes))
                width, height = image_pil.size
                
                if width * height < min_image_size:
                    print(f"    ⏭️  Skipping small image ({width}x{height})")
                    continue
                
                # Check if we've seen this image before
                img_hash = str(imagehash.average_hash(image_pil))
                
                if img_hash in seen_hashes:
                    print(f"    🔄 Duplicate image detected (same as page {seen_hashes[img_hash]})")
                    continue
                
                seen_hashes[img_hash] = page_num + 1
                
                image_filename = f"{doc_id}_page{page_num + 1}_img{img_index}.png"
                image_path =    os.path.join(output_dir, image_filename)
                os.makedirs(output_dir, exist_ok=True)
                image_pil.save(image_path)
                print(f" 💾 Saved image: {image_filename}")
                
                print(f"    🖼️  Analyzing image {img_index + 1} ({width}x{height})...")
                
                visual_type = detect_visual_type(image_pil, openai_client)
                print(f"       Type detected: {visual_type}")
                
                extracted_data = extract_chart_data(image_pil, visual_type, openai_client)
                print(f"       ✓ Data extracted")
                
                searchable_text = f"""[{visual_type.upper().replace('_', ' ')}]

{extracted_data}

Source: {doc_id}, Page {page_num + 1}
Visual Type: {visual_type}"""
                
                chunk = {
                    'text': searchable_text,
                    'type' : visual_type,
                    'metadata': {
                        **metadata,
                        'source_type': 'pdf',
                        'content_type': visual_type,
                        'doc_id': doc_id,
                        'page': page_num + 1,
                        'visual_index': img_index,
                        'dimensions': f"{width}x{height}"
                    }
                }
                
                visual_chunks.append(chunk)
                
            except Exception as e:
                print(f"    ❌ Error processing image {img_index}: {e}")
                continue
    
    print(f"  ✅ Extracted {len(visual_chunks)} visual chunks")
    print(f"     Types: {', '.join(set(c['metadata']['content_type'] for c in visual_chunks))}")
    
    return visual_chunks



def extract_chart_data(image_pil: Image.Image, visual_type: str, openai_client: OpenAI) -> str:
    """
    Extract structured data from charts using GPT-4 Vision.
    For bar charts, extract actual values. For flowcharts, extract steps.
    """
    buffered = io.BytesIO()
    image_pil.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    if visual_type == "bar_chart":
        prompt = """Extract ALL data from this bar chart in this exact format:

Title: [chart title]
X-axis: [what it represents]
Y-axis: [what it represents]

Data points (list ALL bars with their exact values):
- Category1: Value1
- Category2: Value2
...

Key insight: [What comparison or trend does this show?]

Be precise with numbers and include ALL categories shown."""
    
    elif visual_type == "line_chart":
        prompt = """Extract data from this line chart:

Title: [chart title]
X-axis: [time period or categories]
Y-axis: [metric]

Data trend: [describe the trend with key values]
Key points: [notable peaks, valleys, or changes]"""
    
    elif visual_type == "flowchart":
        prompt = """Extract the complete process flow:

Title/Purpose: [what process this shows]

Steps (in order):
1. [First step]
2. [Second step]
...

Decision points: [list any decision branches]
Key outcomes: [final states or results]"""
    
    elif visual_type == "pie_chart":
        prompt = """Extract pie chart data:

Title: [chart title]
Total: [if shown]

Segments (with percentages if visible):
- Segment1: X%
- Segment2: Y%
...

Key insight: [what distribution or comparison this shows]"""
    
    else:  # table, diagram, other
        prompt = """Describe this visual element:

Type: [table/diagram/other]
Purpose: [what information it conveys]
Key information: [main data points or concepts]
Structure: [how information is organized]"""
    
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img_base64}",
                            "detail": "high"  # Need detail for accurate extraction
                        }
                    }
                ]
            }
        ],
        max_tokens=500,
        temperature=0
    )
    
    return response.choices[0].message.content