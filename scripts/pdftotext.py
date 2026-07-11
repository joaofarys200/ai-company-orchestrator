import sys
import os

def main():
    if len(sys.argv) < 2:
        print("Usage: python pdftotext.py <PDF-file> [<text-file>]")
        print("If <text-file> is '-' it prints to stdout.")
        sys.exit(1)
        
    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"Error: File '{pdf_path}' not found.", file=sys.stderr)
        sys.exit(1)
        
    # Default output path
    output_path = None
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        # Replace extension with .txt
        base, _ = os.path.splitext(pdf_path)
        output_path = base + ".txt"
        
    try:
        import fitz  # PyMuPDF
    except ImportError:
        try:
            import pdfplumber
            use_pdfplumber = True
        except ImportError:
            print("Error: PyMuPDF (fitz) or pdfplumber is required. Please install PyMuPDF.", file=sys.stderr)
            sys.exit(1)
            
    text = ""
    try:
        # Try to use PyMuPDF first
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
    except Exception as e:
        # Fallback to pdfplumber
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text += (page.extract_text() or "") + "\n"
        except Exception as e2:
            print(f"Error reading PDF: {e} | Fallback error: {e2}", file=sys.stderr)
            sys.exit(1)
            
    if output_path == "-":
        # Print to stdout
        sys.stdout.buffer.write(text.encode('utf-8'))
    else:
        # Write to file
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"Successfully extracted text from '{pdf_path}' to '{output_path}'.")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
