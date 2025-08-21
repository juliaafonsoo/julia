import os
import json
import requests
import datetime
from docx import Document

# === CONFIG ===
FOLDER_PATH = "medico"
API_URL = "https://medico-endpoint.com/v1/generate"
# Directory where all_texts.txt and other outputs will be stored (absolute path)
output_dir = os.path.join(os.path.dirname(__file__), "output")

def read_docx(file_path):
    """Extracts text from a .docx file."""
    doc = Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])

# def call_gpt_api(prompt):
#     """Sends a prompt to the GPT API and returns the response."""
#     headers = {
#         "Content-Type": "application/json",
#     }
#     payload = {"prompt": prompt}
    
#     response = requests.post(API_URL, headers=headers, data=json.dumps(payload))
#     response.raise_for_status()
    
#     data = response.json()
#     return data.get("response", "")

def main():
    # ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # master output file path
    master = os.path.join(output_dir, "all_texts.txt")

    # Clear/truncate the master output file before starting
    try:
        with open(master, "w", encoding="utf-8") as mf:
            mf.write("")
        print(f"Cleared master file: {master}")
    except Exception as e:
        print(f"Warning: could not clear master file {master}: {e}")

    # compute absolute folder path for source DOCX files
    source_dir = os.path.join(os.path.dirname(__file__), FOLDER_PATH)

    for filename in os.listdir(source_dir):
        if filename.lower().endswith(".docx"):
            file_path = os.path.join(source_dir, filename)
            print(f"\n--- Processing: {filename} ---")
            
            text = read_docx(file_path)

            if not text.strip():
                print("File is empty or contains no extractable text.")
                continue
            
            # try:
            #     result = call_gpt_api(text)
            #     print("GPT API Response:")
            #     print(result)
            # except Exception as e:
            #     print(f"Error processing {filename}: {e}")
            #     result = f"Error: {e}"

            # gather file metadata
            try:
                file_size = os.path.getsize(file_path)
            except OSError:
                file_size = None

            try:
                mtime_ts = os.path.getmtime(file_path)
                mtime = datetime.datetime.fromtimestamp(mtime_ts, datetime.UTC).isoformat() + "Z"
            except OSError:
                mtime = None

            extraction_time = datetime.datetime.now(datetime.UTC).isoformat() + "Z"
            word_count = len(text.split())

            with open(master, "a", encoding="utf-8") as mf:
                mf.write(f"--- {filename} ---\n")
                # mf.write(f"Source path: {file_path}\n")
                # if file_size is not None:
                #     mf.write(f"File size: {file_size} bytes\n\n")
                # if mtime is not None:
                #     mf.write(f"Last modified (utc): {mtime}\n")
                # mf.write(f"Extracted at (utc): {extraction_time}\n")
                # mf.write(f"Word count: {word_count}\n\n")

                mf.write(text.rstrip() + "\n\n")

                # mf.write("--- GPT API Response ---\n")
                # mf.write(result.rstrip() + "\n\n")

if __name__ == "__main__":
    main()
