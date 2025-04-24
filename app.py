from flask import Flask, request, render_template_string, jsonify, send_file
import os
import PyPDF2 # For PDF extraction
# from werkzeug.utils import secure_filename # Commented out for now
# from dotenv import load_dotenv # Optional: Use python-dotenv
import sys # Import sys to exit if API key is missing
from gtts import gTTS # For Text-to-Speech
import time # Import time for unique filenames
import google.generativeai as genai # For Gemini AI
import docx # Import the python-docx library
# import tempfile # Import tempfile for creating temporary files (optional, using uploads for now)

# --- Removed Imports for Tesseract/Pillow ---
# import pytesseract
# from PIL import Image
# -------------------------------------------


# --- Optional: Load environment variables from a .env file ---
# If you create a file named .env in your project folder and put
# GOOGLE_API_KEY=YOUR_ACTUAL_API_KEY
# in it (and `py -m pip install python-dotenv`), you can uncomment the line below:
# load_dotenv()
# -----------------------------------------------------------


app = Flask(__name__)

# --- Gemini API Configuration ---
# Load the API key from the environment variable
API_KEY = os.environ.get('GOOGLE_API_KEY')

# Check API key *before* configuring genai or running the app
if not API_KEY:
    print("Error: GOOGLE_API_KEY environment variable not set.")
    print("Please set it in your terminal BEFORE running the app:")
    print("On Windows Command Prompt: set GOOGLE_API_KEY=YOUR_ACTUAL_API_KEY")
    print("On Windows PowerShell: $env:GOOGLE_API_KEY='YOUR_ACTUAL_API_KEY'")
    print("On macOS/Linux: export GOOGLE_API_KEY=YOUR_ACTUAL_API_KEY")
    sys.exit(1) # Exit the application as it cannot function without the key


try:
    # Configure the generativeai library with the API key
    genai.configure(api_key=API_KEY)
    # Initialize the model *once* when the app starts
    # Choose a multi-modal model (gemini-1.5-flash or gemini-1.5-pro) for image support
    MODEL_NAME = "gemini-1.5-flash" # This model supports images and text
    # MODEL_NAME = "gemini-1.5-pro" # Also supports images and text, potentially higher quality
    model = genai.GenerativeModel(MODEL_NAME) # Ensure the model supports multi-modality
    print(f"Successfully loaded Gemini model: {MODEL_NAME}")
except Exception as e:
    print(f"Error configuring Gemini API or loading model {MODEL_NAME}: {e}")
    print("Please double-check your API key, internet connection, and model name.")
    print("Note: If using a model like gemini-pro, it may not support images.")
    # Exit if the model cannot be loaded or doesn't support required features
    sys.exit(1)

# --- Removed Tesseract OCR Configuration ---
# pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# ------------------------------------------


# --- Configuration ---
# Using uploads folder for temporary files (original files, audio, etc.)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# TEMP_DIR = tempfile.gettempdir() # Get system's temporary directory (optional)
# ----------------------

# --- Helper to load HTML ---
# Function to read index.html content
def get_index_html():
    try:
        # Assumes index.html is in the same directory as app.py
        with open('index.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "<p>Error: index.html not found. Make sure it's in the same folder as app.py.</p>"
    except Exception as e:
        return f"<p>Error reading index.html: {e}</p>"
# --------------------------

# --- Text Extraction Function (Includes Gemini OCR) ---
def extract_text_from_file(filepath):
    """
    Extracts text content from supported file types.
    Supports .txt, .pdf, .docx (using libraries) and .jpg, .jpeg, .png (using Gemini OCR).
    """
    extracted_text = ""
    file_extension = os.path.splitext(filepath)[1].lower()

    try:
        if file_extension == '.txt':
            with open(filepath, 'r', encoding='utf-8') as f:
                extracted_text = f.read()
            print(f"Extracted text from TXT file: {os.path.basename(filepath)} - {len(extracted_text)} chars")

        elif file_extension == '.pdf':
            with open(filepath, 'rb') as f: # Open PDF in binary mode 'rb'
                reader = PyPDF2.PdfReader(f)
                if reader.is_encrypted:
                     try:
                         reader.decrypt('')
                         print("Decrypted PDF (no password needed).")
                     except PyPDF2.errors.FileEncryptedError:
                          print(f"Error: PDF file is encrypted and requires a password: {filepath}")
                          return "Error: Encrypted PDF requires a password."
                     except Exception as e:
                          print(f"Error decrypting PDF: {e}")
                          return f"Error decrypting PDF: {e}"

                num_pages = len(reader.pages)
                print(f"Extracting text from PDF: {os.path.basename(filepath)} ({num_pages} pages)")
                for page_num in range(num_pages):
                    page = reader.pages[page_num]
                    try:
                         page_text = page.extract_text()
                         if page_text: # Check for None or empty string
                             extracted_text += page_text + "\n"
                    except Exception as page_extract_error:
                         print(f"Warning: Could not extract text from page {page_num} of {filepath}: {page_extract_error}")
                         extracted_text += f"\n[Could not extract text from page {page_num}]\n"

                print(f"Finished extracting text from PDF. Total length: {len(extracted_text)}")

        # --- Handle DOCX files ---
        elif file_extension == '.docx':
            try:
                doc = docx.Document(filepath)
                print(f"Extracting text from DOCX file: {os.path.basename(filepath)}")
                for para in doc.paragraphs:
                    extracted_text += para.text + "\n" # Add newline between paragraphs
                print(f"Finished extracting text from DOCX. Total length: {len(extracted_text)}")
            except Exception as docx_error:
                print(f"Error extracting text from DOCX file {filepath}: {docx_error}")
                return f"Error extracting text from DOCX file: {docx_error}"

        # --- Handle Image files (JPG, PNG) using Gemini OCR ---
        elif file_extension in ['.jpg', '.jpeg', '.png']:
            try:
                print(f"Extracting text from image file using Gemini OCR: {os.path.basename(filepath)}")

                # Determine the mime type based on file extension
                if file_extension in ['.jpg', '.jpeg']:
                    mime_type = 'image/jpeg'
                elif file_extension == '.png':
                    mime_type = 'image/png'
                else:
                    print(f"Unsupported image file type for Gemini OCR: {file_extension}")
                    return f"Error: Unsupported image file type '{file_extension}' for Gemini OCR."

                # Read the image file content in binary mode
                with open(filepath, 'rb') as f:
                    image_bytes = f.read()

                # Prepare the image content part for the Gemini API
                image_part = genai.types.Part.from_bytes(image_bytes, mime_type=mime_type)

                # Define the text prompt to ask Gemini to extract text
                text_part = genai.types.Part.from_text("Extract all text from this image. Respond only with the extracted text.") # Refined prompt

                # Call the Gemini model with the image and text prompt
                response = model.generate_content([text_part, image_part])

                # Get the extracted text from the response
                extracted_text = response.text
                print(f"Finished extracting text from image using Gemini. Total length: {len(extracted_text)}")

            except Exception as gemini_ocr_error:
                 print(f"Error extracting text from image file using Gemini OCR: {gemini_ocr_error}")
                 return f"Error extracting text from image file using Gemini OCR: {gemini_ocr_error}"


        else:
            print(f"Unsupported file type for extraction: {file_extension}")
            return f"Error: Unsupported file type '{file_extension}' for text extraction."

    except FileNotFoundError:
        print(f"Error: File not found during extraction attempt: {filepath}")
        return "Error: File not found."
    except Exception as e:
        print(f"An unexpected error occurred during text extraction setup for {filepath}: {e}")
        return f"Error during text extraction setup: {e}"

    return extracted_text # Return the extracted text
# ---------------------------------------


# --- Routes ---

@app.route('/')
def index():
    return render_template_string(get_index_html())

# Route to handle file uploads and return processed text using Gemini
@app.route('/upload', methods=['POST'])
def upload_file():
    action = request.form.get('action')
    print(f"\n--- Received action: {action} ---")

    if 'document' not in request.files:
        print("No 'document' file part in the request")
        return jsonify({'success': False, 'error': 'No file part in the request'}), 400

    file = request.files['document']

    if file.filename == '':
        print("No selected file")
        return jsonify({'success': False, 'error': 'No selected file'}), 400

    if file:
        filename = file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        try:
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                 os.makedirs(app.config['UPLOAD_FOLDER'])

            file.save(filepath)
            print(f"File saved successfully: {filepath}")

            # --- Call text extraction (from file or Gemini OCR) ---
            print("\n--- Starting Text Extraction ---")
            extracted_text = extract_text_from_file(filepath)
            print("--- End of Text Extraction ---")

            # --- Handle cases where extraction failed or returned empty ---
            if extracted_text.startswith("Error:") or not extracted_text.strip():
                 print("Extracted text is an error message or is empty, skipping AI/TTS/Save processing.")
                 return jsonify({
                     'success': True,
                     'filename': filename,
                     'extracted_text': extracted_text if extracted_text.startswith("Error:") else "No readable text found in the file."
                 })


            # --- Call Gemini API based on Action (Text Processing) ---
            processed_text = extracted_text # Default

            # Define specific prompts for Gemini Text Processing
            simplify_prompt = "Please simplify the following text, making it easier to understand. Respond only with the simplified text, no extra explanations or formatting:\n\n" + extracted_text
            summarize_prompt = "Please summarize the following text concisely. Respond only with the summary, no extra explanations or formatting:\n\n" + extracted_text
            extract_instructions_prompt = "From the following text, extract and list all step-by-step instructions, commands, or procedures. Present them clearly, perhaps using bullet points or numbered steps. Respond only with the extracted instructions:\n\n" + extracted_text
            # --- New Prompt for Analyze File (New!) ---
            analyze_prompt = "Analyze the following text and provide a brief overview, identifying the main topics and key points. Respond only with the analysis:\n\n" + extracted_text


            try:
                # Only call Gemini text processing if an AI text action is requested
                if action in ['summarize', 'simplify', 'extract-instructions', 'analyze']:

                    if action == 'simplify':
                         print("Action: Calling Gemini for simplification (text processing)...")
                         response = model.generate_content(simplify_prompt)
                         processed_text = response.text if hasattr(response, 'text') else "Gemini returned no text for simplification."
                         print("Gemini simplification finished.")

                    elif action == 'summarize':
                         print("Action: Calling Gemini for summarization (text processing)...")
                         response = model.generate_content(summarize_prompt)
                         processed_text = response.text if hasattr(response, 'text') else "Gemini returned no text for summarization."
                         print("Gemini summarization finished.")

                    elif action == 'extract-instructions':
                         print("Action: Calling Gemini to extract instructions (text processing)...")
                         response = model.generate_content(extract_instructions_prompt)
                         processed_text = response.text if hasattr(response, 'text') else "Gemini returned no instructions."
                         print("Gemini instruction extraction finished.")

                    # --- New: Handle Analyze File Action (New!) ---
                    elif action == 'analyze':
                         print("Action: Calling Gemini to analyze text (text processing)...")
                         response = model.generate_content(analyze_prompt)
                         processed_text = response.text if hasattr(response, 'text') else "Gemini returned no analysis."
                         print("Gemini text analysis finished.")


                    # Handle actions that are NOT AI text actions (e.g., a future 'View Raw Text' action?)
                    else: # This branch should ideally not be hit if frontend buttons match these actions
                         print(f"Action: Unhandled AI text action received: {action}. Returning raw extracted text after extraction.")
                         processed_text = extracted_text # Return the text extracted by libraries or Gemini OCR


                else: # Handle actions that are NOT AI text actions (e.g., a future 'View Raw Text' action?)
                     print(f"Action: Non-AI text processing action received: {action}. Returning raw extracted text after extraction.")
                     processed_text = extracted_text


                # Final check if processed text is empty after attempting AI text call
                if action in ['summarize', 'simplify', 'extract-instructions', 'analyze'] and (not processed_text or processed_text.strip() == ""):
                     processed_text = f"AI text processing for '{action}' returned empty response. Original extracted text length: {len(extracted_text)}"


            except Exception as api_error:
                 print(f"Error during Gemini text processing for action '{action}': {api_error}")
                 processed_text = f"Error: Could not get AI response for '{action}'. AI Text Processing Error: {api_error}"


            # --- Return the final processed text as JSON ---
            return jsonify({
                'success': True,
                'filename': filename,
                'extracted_text': processed_text # Return the final processed text (from AI or just extraction)
            })

        except Exception as e:
            print(f"An unexpected error occurred during file processing: {e}")
            return jsonify({'success': False, 'error': f'An unexpected error occurred during file processing: {e}'}), 500


# --- Route for Text-to-Speech (TTS) ---
@app.route('/read_aloud', methods=['POST'])
def read_aloud():
    data = request.get_json()
    text_to_read = data.get('text')

    if not text_to_read or text_to_read.strip() == "" or text_to_read.startswith("Error:"):
        print("No valid text provided for TTS.")
        return jsonify({'success': False, 'error': 'No valid text provided for read aloud'}), 400


    print(f"\n--- Received text for TTS (first 50 chars): {text_to_read[:50]} ---")

    try:
        tts = gTTS(text=text_to_read, lang='en', slow=False)

        timestamp = int(time.time() * 1000)
        audio_filename = f"audio_{timestamp}.mp3"
        audio_filepath = os.path.join(app.config['UPLOAD_FOLDER'], audio_filename)

        tts.save(audio_filepath)
        print(f"Audio file saved successfully: {audio_filepath}")

        return send_file(audio_filepath, mimetype='audio/mp3', as_attachment=False)

    except Exception as e:
        print(f"Error during TTS generation: {e}")
        return jsonify({'success': False, 'error': f'Error generating audio: {e}'}), 500

# ---------------------------------------

# --- Route for Saving Text as File ---
@app.route('/save_text', methods=['POST'])
def save_text():
    data = request.get_json()
    text_to_save = data.get('text')

    if not text_to_save or text_to_save.strip() == "" or text_to_save.startswith("Error:"):
        print("No valid text provided for saving.")
        return jsonify({'success': False, 'error': 'No valid text provided for saving'}), 400

    print(f"\n--- Received text for saving (first 50 chars): {text_to_save[:50]} ---")

    try:
        timestamp = int(time.time() * 1000)
        save_filename = f"clarityassist_output_{timestamp}.txt"
        save_filepath = os.path.join(app.config['UPLOAD_FOLDER'], save_filename)

        with open(save_filepath, 'w', encoding='utf-8') as f:
            f.write(text_to_save)
        print(f"Text file saved successfully temporarily: {save_filepath}")

        return send_file(save_filepath,
                         mimetype='text/plain',
                         as_attachment=True,
                         download_name=save_filename)

    except Exception as e:
        print(f"Error during text file saving: {e}")
        return jsonify({'success': False, 'error': f'Error saving text file: {e}'}), 500

# ---------------------------------------


# --- Run the App ---
if __name__ == '__main__':
    if not API_KEY:
        print("\nServer will not start because GOOGLE_API_KEY is not set.")
    else:
        print("\nStarting Flask server...")
        app.run(debug=True)