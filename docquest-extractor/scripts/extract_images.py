#!/usr/bin/env python3
"""
Script to extract images from PDF files
"""
import fitz  # PyMuPDF
import os
import re
from pathlib import Path


def extract_images_from_pdf(pdf_path, output_dir):
    """
    Extract all images from a PDF file and save them to the output directory
    """
    pdf_document = fitz.open(pdf_path)
    image_count = 0
    
    for page_num in range(pdf_document.page_count):
        page = pdf_document[page_num]
        
        # Get list of image rectangles on the page
        image_list = page.get_images()
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            pix = fitz.Pixmap(pdf_document, xref)
            
            # Skip if this is an alpha channel (len(pix) == 1 for grayscale with alpha)
            if pix.n < 4:
                # Create a new pixmap without alpha for saving
                pix = fitz.Pixmap(fitz.csRGB, pix)
            
            # Create filename based on PDF name, page, and image index
            pdf_name = Path(pdf_path).stem
            image_filename = f"{pdf_name}_p{page_num}_{img_index}.png"
            image_path = os.path.join(output_dir, image_filename)
            
            # Save the image
            pix.save(image_path)
            print(f"Saved image: {image_path}")
            
            # Clean up pixmap
            pix = None
            image_count += 1
    
    pdf_document.close()
    print(f"Extraction completed! {image_count} images extracted.")


def main():
    """
    Main function to extract images from PDF
    """
    # Default paths
    input_pdf = os.getenv("INPUT_PDF", "input.pdf")
    output_dir = os.getenv("OUTPUT_DIR", "../data/images")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    if not os.path.exists(input_pdf):
        print(f"Error: Input PDF '{input_pdf}' not found")
        return
    
    print(f"Extracting images from {input_pdf} to {output_dir}")
    extract_images_from_pdf(input_pdf, output_dir)


if __name__ == "__main__":
    main()