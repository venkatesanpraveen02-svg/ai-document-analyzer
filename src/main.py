import os
import sys
import base64
import re

# OCR + entity cleanup helpers live below
import subprocess
import socket
import requests
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# --------------------------------------------------
# Environment
# --------------------------------------------------
load_dotenv()
API_KEY = os.getenv("API_KEY", "").strip()   # empty = open/demo mode

# --------------------------------------------------
# AI Model singletons  (loaded once on first use)
# --------------------------------------------------
_summarizer         = None
_sentiment_pipeline = None
_nlp                = None


def get_summarizer():
    global _summarizer
    if _summarizer is None:
        from transformers import pipeline
        print("[INIT] Loading BART summarization model...", flush=True)
        _summarizer = pipeline(
            "summarization",
            model="sshleifer/distilbart-cnn-6-6",
            device=-1,
        )
        print("[INIT] BART model ready. OK", flush=True)
    return _summarizer


def get_sentiment():
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        from transformers import pipeline
        print("[INIT] Loading distilBERT sentiment model...", flush=True)
        _sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            device=-1,
        )
        print("[INIT] distilBERT model ready. OK", flush=True)
    return _sentiment_pipeline


def get_nlp():
    global _nlp
    if _nlp is None:
        import spacy
        print("[INIT] Loading spaCy en_core_web_sm...", flush=True)
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("[INIT] en_core_web_sm not found. Downloading now...", flush=True)
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install",
                     "https://github.com/explosion/spacy-models/releases/download/"
                     "en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl"],
                    check=True, capture_output=True,
                )
                _nlp = spacy.load("en_core_web_sm")
            except Exception as exc:
                print(f"[INIT] spaCy download failed: {exc}. NER will be skipped.", flush=True)
                _nlp = None
        if _nlp:
            print("[INIT] spaCy ready. OK", flush=True)
    return _nlp


# --------------------------------------------------
# FastAPI app
# --------------------------------------------------
app = FastAPI(title="AI Document Analyzer", version="2.0.0")

app.mount("/", StaticFiles(directory="src/static", html=True), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ai-document-analyzer-hdwv2cbcs.vercel.app"
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

MAX_TEXT_CHARS  = 3000
SUMMARY_MAX_LEN = 150
SUMMARY_MIN_LEN = 40


# --------------------------------------------------
# Startup  -- pre-warm spaCy (fast; avoids first-request lag)
# --------------------------------------------------
@app.on_event("startup")
def on_startup():
    print("\n" + "="*50, flush=True)
    print("  AI Document Analyzer  v2.0.0", flush=True)
    print("  Auth mode: " + ("KEY REQUIRED" if API_KEY else "OPEN (demo)"), flush=True)
    print("="*50, flush=True)
    get_nlp()   # spaCy is tiny -- pre-warm it now
    print("[READY] Server started successfully.\n", flush=True)


# --------------------------------------------------
# Pydantic schemas
# --------------------------------------------------


class EntitiesOut(BaseModel):
    names:         list[str]
    dates:         list[str]
    organizations: list[str]
    locations:     list[str]
    amounts:       list[str]


class AnalysisResponse(BaseModel):
    status:    str
    fileName:  str
    summary:   str
    entities:  EntitiesOut
    sentiment: str


# --------------------------------------------------
# Text extraction helpers
# --------------------------------------------------
def extract_pdf(path: str) -> str:
    import pdfplumber
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text.strip()


def extract_docx(path: str) -> str:
    from docx import Document
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_image(path: str) -> str:
    import pytesseract
    from PIL import Image
    pytesseract.pytesseract.tesseract_cmd = os.getenv(
        "TESSERACT_CMD",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )
    text = pytesseract.image_to_string(Image.open(path)).strip()
    return text or "[OCR returned no readable text]"

def extract_text_from_image(file_bytes):
    import pytesseract
    from PIL import Image, ImageEnhance
    import io
    try:
        import numpy as np
    except Exception:
        np = None

    try:
        import cv2
    except Exception:
        cv2 = None

    # FORCE PATH
    import os
    tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    print(f"[OCR] Using tesseract_cmd: {tesseract_cmd}", flush=True)
    print(f"[OCR] tesseract.exe exists: {os.path.exists(tesseract_cmd)}", flush=True)
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    try:
        print("\n[OCR] Starting image processing...", flush=True)

        # Load image
        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        print("[OCR] Image loaded", flush=True)

        # -------- TEST TESSERACT --------
        try:
            version = pytesseract.get_tesseract_version()
            print(f"[OCR] Tesseract version: {version}", flush=True)
        except Exception as e:
            print("[ERROR] Tesseract NOT working:", e, flush=True)
            return ""

        # -------- METHOD 1: SIMPLE OCR --------
        text_simple = pytesseract.image_to_string(image)
        print("[OCR] Simple OCR length:", len(text_simple), flush=True)

        # -------- METHOD 2: GRAYSCALE --------
        gray = image.convert("L")
        text_gray = pytesseract.image_to_string(gray)
        print("[OCR] Gray OCR length:", len(text_gray), flush=True)

        # -------- METHOD 3: OPENCV --------
        text_cv = ""
        if cv2 is not None and np is not None:
            img = np.array(image)
            gray_cv = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

            thresh = cv2.adaptiveThreshold(
                gray_cv, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11, 2
            )

            thresh = cv2.resize(thresh, None, fx=2, fy=2)
            text_cv = pytesseract.image_to_string(thresh)
        else:
            print("[OCR] OpenCV not available (cv2/numpy missing) - skipping method 3.", flush=True)

        print("[OCR] OpenCV OCR length:", len(text_cv), flush=True)

        # -------- METHOD 4: CONTRAST BOOST --------
        enhancer = ImageEnhance.Contrast(image)
        enhanced = enhancer.enhance(3.0)
        text_enhanced = pytesseract.image_to_string(enhanced)
        print("[OCR] Enhanced OCR length:", len(text_enhanced), flush=True)

        # -------- PICK BEST --------
        texts = [text_simple, text_gray, text_cv, text_enhanced]
        best_text = max(texts, key=len).strip()

        print("[OCR] BEST TEXT LENGTH:", len(best_text), flush=True)

        if len(best_text) < 30:
            print("[OCR] FAILED - TEXT TOO SHORT", flush=True)
            return "Could not extract text from this document."

        print("[OCR] SUCCESS", flush=True)
        return best_text

    except Exception as e:
        print("[OCR ERROR]", e, flush=True)
        return "Could not extract text from this document."


# --------------------------------------------------
# AI pipeline helpers (all wrapped in try/except)
# --------------------------------------------------
def generate_summary(text):
    text = (text or "").strip()
    summarizer = get_summarizer()
    summary = summarizer(
        text[:1000],
        max_length=120,
        min_length=40,
        do_sample=False
    )[0]["summary_text"]
    if not summary:
        summary = text[:200]
    return summary


def clean_text(text: str) -> str:
    # 1. Split merged words (camel case / missing spaces)
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text or "")

    # 2. Fix missing spaces after punctuation
    text = re.sub(r"([.,])([A-Za-z])", r"\1 \2", text)

    # 3. Remove duplicate spaces
    text = re.sub(r"\s+", " ", text)

    # 4. Fix common OCR issues
    text = text.replace("NYCArt", "NYC Art")
    text = text.replace("NewYork", "New York")

    return text.strip()


def extract_entities(text: str) -> dict:
    empty = dict(names=[], dates=[], organizations=[], locations=[], amounts=[])
    nlp = get_nlp()
    if not nlp:
        return empty
    try:
        text = clean_text(text)
        doc = nlp(text[:MAX_TEXT_CHARS])

        entities: dict[str, set] = {
            "names": set(),
            "organizations": set(),
            "dates": set(),
            "locations": set(),
            "amounts": set(),
        }

        for ent in doc.ents:
            val = clean_text(ent.text)
            val_lower = val.lower()

            if len(val) < 3:
                continue

            # Remove only clear garbage.
            if val_lower in ["annual"]:
                continue

            # Remove small numeric fragments.
            if val.isdigit() and len(val) < 4:
                continue

            if ent.label_ == "PERSON":
                entities["names"].add(val)
            elif ent.label_ == "ORG":
                entities["organizations"].add(val)
            elif ent.label_ == "DATE":
                entities["dates"].add(val)
            elif ent.label_ in ["GPE", "LOC"]:
                entities["locations"].add(val)
            elif ent.label_ == "MONEY":
                if any(char.isdigit() for char in val):
                    entities["amounts"].add(val)

        # FINAL MANUAL CLEANUP (HACKATHON SAFE)

        cleaned = {
            "names": [],
            "organizations": [],
            "dates": [],
            "locations": [],
            "amounts": []
        }

        # 👤 PERSON → only proper names (2 words max)
        for n in entities["names"]:
            if len(n.split()) <= 3 and n.istitle():
                if "Adobe" not in n and "Creative" not in n:
                    cleaned["names"].append(n)

        # 🏢 ORG → remove long phrases
        for o in entities["organizations"]:
            if len(o.split()) <= 4:
                if "Portfolio" not in o and "Campaign" not in o:
                    cleaned["organizations"].append(o)

        # 📍 LOCATION → remove garbage
        for l in entities["locations"]:
            if "Graduated" not in l:
                cleaned["locations"].append(l)

        # 📅 DATE → keep only useful
        for d in entities["dates"]:
            if any(char.isdigit() for char in d):
                cleaned["dates"].append(d)

        # 💰 AMOUNT → ignore small junk
        for a in entities["amounts"]:
            if len(a) > 3:
                cleaned["amounts"].append(a)

        return cleaned
    except Exception as exc:
        print(f"[WARN] Entity extraction failed: {exc}", flush=True)
        return empty


def analyze_sentiment(text: str) -> str:
    text = text[:MAX_TEXT_CHARS].strip()
    if not text:
        return "Neutral"
    try:
        short = " ".join(text.split()[:300])
        result = get_sentiment()(short, truncation=True)[0]
        label = result["label"].upper()
        if label == "POSITIVE":
            return "Positive"
        elif label == "NEGATIVE":
            return "Negative"
        return "Neutral"
    except Exception as exc:
        print(f"[WARN] Sentiment failed: {exc}", flush=True)
        return "Neutral"


# --------------------------------------------------
# Endpoints
# --------------------------------------------------
@app.get("/health")
def health():
    return {
        "status":          "ok",
        "version":         "2.0.0",
        "models_loaded":   _nlp is not None,
        "api_key_required": bool(API_KEY),
    }

from fastapi import Request, UploadFile, File

@app.post("/api/document-analyze")
async def analyze_document(
    file: UploadFile = File(None),
    x_api_key: str = Header(default="")
):
    received_key = (x_api_key or "").strip()

    if API_KEY and received_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized: invalid API key.")

    if file is None:
        return {
            "fileName": "unknown",
            "summary": "No file received.",
            "entities": {
                "names": [],
                "dates": [],
                "organizations": [],
                "locations": [],
                "amounts": []
            },
            "sentiment": "Neutral"
        }

    file_bytes = await file.read()
    file_name = file.filename.lower()

    # Detect file type
    if file_name.endswith(".pdf"):
        file_type = "pdf"
    elif file_name.endswith(".docx"):
        file_type = "docx"
    else:
        file_type = "image"

    # Save file
    file_path = UPLOAD_DIR / file_name
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # Extract text
    text = ""
    try:
        if file_type == "pdf":
            text = extract_pdf(str(file_path))
        elif file_type == "docx":
            text = extract_docx(str(file_path))
        else:
            text = extract_text_from_image(file_bytes)
    except Exception as e:
        print(f"[ERROR] extraction failed: {e}", flush=True)

    # Fail-safe
    if not text:
        return {
            "status": "success",
            "fileName": file_name,
            "summary": "Could not extract text from this document.",
            "entities": {
                "names": [],
                "dates": [],
                "organizations": [],
                "locations": [],
                "amounts": []
            },
            "sentiment": "Neutral"
        }

    # AI processing
    text = clean_text(text)
    summary = generate_summary(text)
    entities = extract_entities(text)
    sentiment = analyze_sentiment(text)

    return {
        "status": "success",
        "fileName": file_name,
        "summary": summary,
        "entities": entities,
        "sentiment": sentiment
    }

@app.post("/proxy-analyze")
async def proxy_analyze(file: UploadFile = File(...)):
    file_bytes = await file.read()

    files = {
        "file": (file.filename, file_bytes)
    }

    response = requests.post(
        "http://localhost:10000/api/document-analyze",
        files=files
    )

    return response.json()

@app.options("/api/document-analyze")
async def options_handler(request: Request):
    return {}