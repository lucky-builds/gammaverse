# unlock_pdf.py

from pypdf import PdfReader, PdfWriter
import argparse

def unlock_pdf(input_pdf_path, output_pdf_path, password):
    try:
        reader = PdfReader(input_pdf_path)

        if reader.is_encrypted:
            if reader.decrypt(password):
                writer = PdfWriter()
                for page in reader.pages:
                    writer.add_page(page)

                with open(output_pdf_path, "wb") as output_file:
                    writer.write(output_file)
                return True, f"Successfully unlocked '{input_pdf_path}' to '{output_pdf_path}'"
            else:
                return False, f"Error: Could not decrypt '{input_pdf_path}'. Incorrect password."
        else:
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)

            with open(output_pdf_path, "wb") as output_file:
                writer.write(output_file)
            return True, f"'{input_pdf_path}' is not password protected. Copying to '{output_pdf_path}'."

    except FileNotFoundError:
        return False, f"Error: Input file '{input_pdf_path}' not found."
    except Exception as e:
        return False, f"An unexpected error occurred: {e}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unlock a password-protected PDF file.")
    parser.add_argument("input_pdf", help="Path to the encrypted input PDF file.")
    parser.add_argument("output_pdf", help="Path for the decrypted output PDF file.")
    parser.add_argument("password", help="Password to decrypt the PDF file.")

    args = parser.parse_args()

    success, message = unlock_pdf(args.input_pdf, args.output_pdf, args.password)
    print(message)
