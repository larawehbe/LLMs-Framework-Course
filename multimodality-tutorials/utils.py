import os
from typing import List, Dict
import pymupdf

import requests

def build_pdf_docs(pdf_dir: str) -> List[Dict]:
    """
    Scan a directory and return a list of PDF doc descriptors:
    [{ 'pdf_path': '<full path>', 'doc_id': '<filename-no-ext>', 'metadata': {...} }, ...]
    """
    docs: List[Dict] = []
    for name in os.listdir(pdf_dir):
        if not name.lower().endswith(".pdf"):
            continue
        full_path = os.path.join(pdf_dir, name)
        doc_id = os.path.splitext(name)[0]

        # Minimal, safe metadata. Add more fields if you have them.
        metadata = {
            "source": "pdf",
            "filename": name
        }

        docs.append({
            "pdf_path": full_path,
            "doc_id": doc_id,
            "metadata": metadata,
        })
    return docs


def get_paper():
        # Download the DeepSeek paper
    response = requests.get("https://arxiv.org/pdf/2501.12948")
    if response.status_code != 200:
        raise ValueError(f"Failed to download PDF. Status code: {response.status_code}")
    # Get the content of the response
    pdf_stream = response.content
    # Open the data in `pdf_stream` as a PDF document.
    # HINT: Set the `filetype` argument to "pdf".
    pdf = pymupdf.Document(stream=pdf_stream, filetype="pdf")



def test_pymupdf():
    doc = pymupdf.open("data/2501.12948v1.pdf") # open a document
    for page_index in range(len(doc)): # iterate over pdf pages
        page = doc[page_index] # get the page
        image_list = page.get_images(full=True)

        # print the number of images found on the page
        if image_list:
            print(f"Found {len(image_list)} images on page {page_index}")
        else:
            print("No images found on page", page_index)

        for image_index, img in enumerate(image_list, start=0): # enumerate the image list
            xref = img[0] # get the XREF of the image
            pix = pymupdf.Pixmap(doc, xref) # create a Pixmap

            if pix.n - pix.alpha > 3: # CMYK: convert to RGB first
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)

            pix.save("page_%s-image_%s.png" % (page_index, image_index)) # save the image as png
            pix = None