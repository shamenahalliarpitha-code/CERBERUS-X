# CERBERUS-X — Local Hackathon Prototype

A beginner-friendly local prototype for multimodal document ingestion, claim extraction, basic contradiction detection, evidence retrieval, and a lightweight knowledge graph.

## Important prototype limitations

This is a functional proof of concept, not a production-grade AI verification system.

- Text extraction: PDF, DOCX, TXT, CSV, XLSX and images (OCR requires the Tesseract application installed separately).
- Fact extraction: rule-based date and selected numeric-claim extraction.
- Contradictions: basic date-category/value comparison. It can miss conflicts and can flag claims that are not truly contradictory.
- Knowledge graph: simple property/value visualization from extracted claims.
- Assistant: keyword-based evidence retrieval, not a generative LLM.
- Source reliability, deepfake/image authenticity detection, robust entity resolution, and general adversarial-content detection are not implemented yet.
- The app does not decide which conflicting source is true.
- Uploaded files are stored locally in `uploads/`; extracted session state is in memory and clears when the server restarts.
- Do not upload sensitive or confidential documents to this prototype.

## Requirements

- Windows 10/11, macOS or Linux
- Python 3.10–3.12 recommended
- VS Code

## Run on Windows

1. Extract the ZIP file.
2. Open the `CERBERUS-X` folder in VS Code.
3. Open Terminal → New Terminal.
4. Create a virtual environment:

   ```powershell
   py -m venv .venv
   ```

5. Activate it:

   ```powershell
   .venv\\Scripts\\activate
   ```

6. Install dependencies:

   ```powershell
   pip install -r backend/requirements.txt
   ```

7. Start the server:

   ```powershell
   cd backend
   python -m uvicorn main:app --reload
   ```

8. Open this address in your browser:

   http://127.0.0.1:8000

Keep the terminal open while using the app. Press `Ctrl + C` to stop the server.

## OCR for images and scanned PDFs

Install the Tesseract OCR desktop application separately and make sure `tesseract.exe` is on your PATH. The Python package alone does not install the OCR executable. Scanned PDF page OCR is not yet implemented; image OCR is supported when Tesseract is configured.

## Quick demo

The `tests/sample_data` folder contains three text files with deliberately conflicting project dates. Upload all three from the Documents page, then open Contradictions.

## Offline operation

The backend dependencies are installed locally. The CSS currently imports Google Fonts from the internet; for a fully air-gapped visual experience, remove the `@import` line at the top of `frontend/style.css` and the system will use local fallback fonts. No cloud AI API is used.

## API docs

When running the server, open:

http://127.0.0.1:8000/docs


## User accounts (added)
- Open the app and choose **Create an account** to register.
- Anyone can register with a name, email address and password (minimum 8 characters).
- Passwords are stored as PBKDF2-HMAC-SHA256 hashes in `cerberus_users.db`, not as plain text.
- The browser receives a signed, HTTP-only session cookie. Logout clears the cookie.
- The SQLite user database is created automatically in the project root.
- The signing secret is created automatically at `backend/.session_secret`; keep it private and do not share it.
- This is a local student-project authentication implementation. Before deploying publicly, use HTTPS, add rate limiting, email verification, password reset and security review.

- Each signed-in account has a separate evidence workspace in the running server process. Evidence uploads are currently held in memory and are cleared when the server restarts; user accounts remain in SQLite.
