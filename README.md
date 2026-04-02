# 🧠 AI Document Analyzer

> Hackathon-winning document intelligence system — upload a PDF, DOCX, or image and instantly receive an AI-generated **summary**, **named entities**, and **sentiment analysis**.

---

## 🗂 Project Structure

```
doc-analyzer/
├── src/
│   └── main.py          # FastAPI backend
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── uploads/             # Auto-created at runtime
├── .env                 # Your secrets (copy from .env.example)
├── .env.example
└── requirements.txt
```

---

## ⚙️ Setup

### 1 · Clone & create `.env`

```powershell
cd d:\doc-analyzer
copy .env.example .env
# Edit .env with your values
```

### 2 · Install Tesseract OCR (Windows — for image support)

Download installer from: <https://github.com/UB-Mannheim/tesseract/wiki>  
Install to the **default path**: `C:\Program Files\Tesseract-OCR\`

### 3 · Install Python dependencies

```powershell
pip install -r requirements.txt
```

> ⚠️ PyTorch is ~2 GB. Ensure a fast connection.

### 4 · Download spaCy model

```powershell
python -m spacy download en_core_web_sm
```

### 5 · Start the backend

```powershell
uvicorn src.main:app --reload --host 0.0.0.0 --port 8003
```

AI models load on the **first request** (~30–60 s). Subsequent calls are fast.

### 6 · Open the frontend

Open `frontend/index.html` in a browser, or serve it:

```powershell
# To run frontend properly:
cd frontend
python -m http.server 5500
# Then open:
# http://localhost:5500
```

---

## 🔌 API Reference

### `POST /api/document-analyze`

**Headers:**
| Header | Value |
|---|---|
| `Content-Type` | `application/json` |
| `X-API-Key` | Your API key (if set in `.env`) |

**Request body:**
```json
{
  "fileName": "report.pdf",
  "fileType": "pdf",
  "fileBase64": "<base64-encoded file>"
}
```

`fileType` must be one of: `pdf` · `docx` · `image`

**Response:**
```json
{
  "status": "success",
  "fileName": "report.pdf",
  "summary": "The report covers quarterly revenue growth...",
  "entities": {
    "names":         ["Alice Smith", "John Doe"],
    "dates":         ["Q1 2024", "January 15"],
    "organizations": ["Acme Corp", "OpenAI"],
    "locations":     ["New York", "San Francisco"],
    "amounts":       ["$5,000", "2.3 million"]
  },
  "sentiment": "Positive"
}
```

### `GET /health`

Returns `{"status": "ok", "version": "2.0.0"}`

---

## 🚀 Deployment

### Backend → Render

1. Push your project to GitHub.
2. On [render.com](https://render.com) → **New → Web Service** → connect your repo.
3. Set:
   - **Build Command:** `pip install -r requirements.txt && python -m spacy download en_core_web_sm`
   - **Start Command:** `uvicorn src.main:app --host 0.0.0.0 --port 10000`
4. Add environment variables from `.env.example` in the Render dashboard.

> ⚠️ Tesseract OCR is **not available** on Render's free tier. Image support requires a custom Docker deployment.

### Frontend → Netlify

1. Drag-and-drop the `frontend/` folder to [app.netlify.com/drop](https://app.netlify.com/drop).
2. Update `API_BASE` in `app.js` to your Render backend URL.

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI |
| PDF extraction | pdfplumber |
| DOCX extraction | python-docx |
| Image OCR | pytesseract + Pillow |
| Summarization | facebook/bart-large-cnn |
| Named entity recognition | spaCy en_core_web_sm |
| Sentiment analysis | distilbert-base-uncased-finetuned-sst-2-english |
| Frontend | Vanilla HTML · CSS · JS |
