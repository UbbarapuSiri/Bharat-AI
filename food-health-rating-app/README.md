# Food Health Rating App

A comprehensive Streamlit app for rating packaged foods using authoritative health guidelines. Supports manual entry, barcode lookup, and photo upload (OCR).

## Features
- Manual product entry
- Barcode lookup and history
- Photo upload with OCR for label extraction
- Evidence-based scoring and explanations
- Local SQLite database for history
- Usage statistics and transparency

## Setup
1. Install Python 3.8+
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Install Tesseract OCR (Windows):
   - Download from https://github.com/tesseract-ocr/tesseract
   - Add install folder to PATH or set path in `app.py`
4. Run the app:
   ```
   python -m streamlit run app.py
   ```

## Usage
- Use sidebar to navigate between analysis, history, and about pages.
- Analyze products by manual entry, barcode, or photo upload.
- View detailed scoring, explanations, and sources.

## Submission Requirements
- Include a short demo video (2-5 minutes) showing app usage: startup, navigation, product analysis (manual, barcode, OCR), history, and statistics.
- Add the provided `SUBMISSION_CHECKLIST.md` to your submission package.
- Ensure all sample outputs and screenshots are included.

See `SUBMISSION_CHECKLIST.md` for a full list of requirements and demo video instructions.

## Screenshots
See `sample_outputs/screenshots/` for UI examples.

## Sample Outputs
See `sample_outputs/` for example analysis outputs.

## References
See `sources_snapshot.json` for all sources used in scoring.

## License
MIT
