#!/usr/bin/env python3
"""
Production FastAPI & Uvicorn Web Server for StatementFlow Extractor.
Optimized for local execution and cloud deployment on Render, Fly.io, or Railway.
"""
import os
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from extractor import parse_statement_pdf, to_csv

DIRECTORY = os.path.dirname(os.path.abspath(__file__))

def load_dotenv():
    env_file = os.path.join(DIRECTORY, '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and v and k not in os.environ:
                        os.environ[k] = v

load_dotenv()

app = FastAPI(title="StatementFlow Extractor API")
application = app

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def health_check():
    """Endpoint for Render health checks"""
    return {"status": "ok", "service": "statement-extractor"}

@app.get("/api/status")
def get_status():
    env_key = os.environ.get('ANTHROPIC_API_KEY')
    has_key = bool(env_key and env_key.strip().startswith('sk-ant-'))
    return {
        'has_server_key': has_key,
        'default_model': 'claude-haiku-4-5-20251001',
        'models': [
            {'id': 'claude-haiku-4-5-20251001', 'name': 'Claude Haiku 4.5'},
            {'id': 'claude-sonnet-4-5-20250929', 'name': 'Claude Sonnet 4.5'},
            {'id': 'claude-opus-4-5-20251101', 'name': 'Claude Opus 4.5'}
        ]
    }

@app.post("/api/test-key")
async def test_key(request: Request, x_anthropic_api_key: Optional[str] = Header(None)):
    try:
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        api_key = body.get('api_key') or x_anthropic_api_key or os.environ.get('ANTHROPIC_API_KEY')
        if not api_key or not api_key.strip().startswith('sk-ant-'):
            raise HTTPException(status_code=400, detail="Invalid key format. Anthropic API keys start with sk-ant-")

        import anthropic
        client = anthropic.Anthropic(api_key=api_key.strip())
        client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=10,
            messages=[{'role': 'user', 'content': 'hi'}]
        )
        return {'success': True, 'message': 'API key connected successfully.'}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Key verification failed: {str(e)}")

@app.post("/api/parse")
async def parse_endpoint(
    file: UploadFile = File(...),
    x_anthropic_api_key: Optional[str] = Header(None),
    x_anthropic_model: Optional[str] = Header(None)
):
    try:
        pdf_bytes = await file.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="No file content received")

        if not pdf_bytes.startswith(b'%PDF'):
            pdf_idx = pdf_bytes.find(b'%PDF')
            if pdf_idx != -1:
                pdf_bytes = pdf_bytes[pdf_idx:]
            else:
                raise HTTPException(status_code=400, detail="Uploaded file does not appear to be a valid PDF format.")

        api_key = x_anthropic_api_key or os.environ.get('ANTHROPIC_API_KEY')
        model = x_anthropic_model or 'claude-haiku-4-5-20251001'

        result = parse_statement_pdf(pdf_bytes, api_key=api_key, model=model)
        transactions = result['transactions']
        validation = result['validation']
        csv_output = to_csv(transactions)

        return {
            'success': True,
            'engine': validation.get('engine', 'Unknown'),
            'count': len(transactions),
            'overall_confidence': validation.get('overall_confidence', 90),
            'needs_review_count': validation.get('needs_review_count', 0),
            'transactions': transactions,
            'validation': validation,
            'metadata': result.get('metadata', {}),
            'csv': csv_output
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

# Serve static web frontend
app.mount("/", StaticFiles(directory=DIRECTORY, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    print(f"Statement Extractor Server starting on http://0.0.0.0:{port}", flush=True)
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
