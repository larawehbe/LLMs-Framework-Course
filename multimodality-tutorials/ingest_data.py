

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
                
                extracted_data = extract_visual_data(image_pil, openai_client)
                print(f"       ✓ Data extracted")
                
                searchable_text = f"""VISUAL: 

                    {extracted_data}

                    Source: {doc_id}, Page {page_num + 1}"""
                
                chunk = {
                    'text': searchable_text,
                    'metadata': {
                        **metadata,
                        'source_type': 'pdf',
                        'content_type': "visual",
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



def extract_visual_data(image_pil: Image.Image, openai_client: OpenAI) -> str:
    """
    Extract structured data from charts using GPT-4 Vision.
    For bar charts, extract actual values. For flowcharts, extract steps.
    """
    buffered = io.BytesIO()
    image_pil.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    
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