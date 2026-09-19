# MaxsorLabs Support Decision Assistant

An AI-powered customer support ticket decision system built with FastAPI, Streamlit, SQLite, JWT authentication, RAG, and Claude (Anthropic).

## What it does

A user registers and logs in, submits a customer support ticket, and receives an evidence-backed decision based on company policy documents. The ticket and decision are stored in a database and accessible from the history view.

## Architecture

```
Streamlit frontend
      │ HTTP + JWT
      ▼
FastAPI backend
      │
      ├── SQLite database (users, tickets, decisions)
      ├── RAG pipeline (sentence-transformers + numpy)
      └── Claude API (structured JSON decision)
```

## Tech stack

- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy + SQLite
- JWT authentication (python-jose + passlib bcrypt)
- sentence-transformers (all-MiniLM-L6-v2) for local embeddings
- NumPy cosine similarity for retrieval
- Anthropic Claude API for structured decisions
- Streamlit for the frontend
- pytest for tests

## Setup

1. Clone the repository and enter the project folder:
```
git clone <your-repo-url>
cd maxsorlabs-assignment
```

2. Create and activate a virtual environment:
```
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux
```

3. Install dependencies:
```
pip install -r requirements.txt
```

4. Copy .env.example to .env and fill in your values:
```
cp .env.example .env
```

Edit .env and set:
```
ANTHROPIC_API_KEY=your-anthropic-api-key
JWT_SECRET=any-long-random-string
```

5. Build the embeddings cache (only needed once):
```
python -c "from src.retrieval import build_cache; build_cache()"
```

## Running the application

Start the FastAPI backend in one terminal:
```
uvicorn src.main:app --reload --port 8000
```

Start the Streamlit frontend in a second terminal:
```
streamlit run streamlit_app.py --server.port 8501
```

Open http://localhost:8501 in your browser.

## API endpoints

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | /health | No | Health check |
| POST | /register | No | Create account |
| POST | /login | No | Login and get JWT |
| GET | /me | Yes | Current user info |
| POST | /tickets | Yes | Submit ticket and get decision |
| GET | /tickets | Yes | List your tickets |
| GET | /tickets/{id} | Yes | Get one ticket |

## Running tests

```
python -m pytest tests/ -v
```

All 17 tests run against an isolated SQLite test database and mock the AI call so no API key or quota is needed.

## Running the evaluation

Make sure the FastAPI server is running, then:
```
python evaluate.py
```

This submits the 5 sample test cases and reports accuracy. Requires a live API key with available quota. Expected output:

```
PASS  [S01]  Expected: REQUEST_PHOTOS
PASS  [S02]  Expected: APPROVE_RETURN
PASS  [S03]  Expected: OPEN_SHIPPING_INVESTIGATION
PASS  [S04]  Expected: REPLACE_CORRECT_ITEM
PASS  [S05]  Expected: NEEDS_MORE_INFORMATION
Accuracy: 100%
```

## Database schema

**users** — id, email, password_hash, created_at

**tickets** — id, user_id (FK), message, created_at

**decisions** — id, ticket_id (FK), action, reason, confidence, sources (JSON), created_at

## RAG pipeline

Policy documents in knowledge_base/ are split by heading, embedded with sentence-transformers (all-MiniLM-L6-v2), and stored as numpy vectors in embeddings_cache.npz. Each incoming ticket is embedded and the top 3 most similar policy chunks are retrieved by cosine similarity and passed to the LLM as context.

## Decision actions

The system can return exactly these actions:
APPROVE_REFUND_OR_REPLACEMENT, APPROVE_REPLACEMENT, APPROVE_RETURN, CANCEL_AND_REFUND, CANNOT_CANCEL_AFTER_DISPATCH, NEEDS_MORE_INFORMATION, OFFER_REPLACEMENT_OR_REFUND, OPEN_SHIPPING_INVESTIGATION, REJECT_FOOD_RETURN, REJECT_OPENED_ITEM, REJECT_OUTSIDE_WINDOW, REPLACE_CORRECT_ITEM, REQUEST_DEFECT_EVIDENCE, REQUEST_PHOTOS, WAIT_AND_TRACK

## Known limitations

- The all-MiniLM-L6-v2 model is downloaded on first run (approximately 90MB).
- The embeddings cache must be rebuilt if knowledge_base/ files change.
- Free-tier API keys may have rate limits that cause temporary fallback to NEEDS_MORE_INFORMATION.
