# Development Notes

## AI coding agent usage

This project was developed using Claude (Anthropic) as a coding agent in a phase-by-phase workflow. Each phase was prompted explicitly with exact file contents and verification steps. The agent produced code, ran commands, and reported results before the next phase was issued.

## Phases completed with agent assistance

**Phase 1 — Project scaffold**
Agent created the full folder structure, all placeholder files, SQLAlchemy models, Pydantic schemas, config, and database setup. Verified with a file-presence script and /health endpoint check.

**Phase 2 — JWT authentication**
Agent implemented /register, /login, and /me endpoints. Two dependency issues were caught during verification: email-validator was missing (required by Pydantic EmailStr), and bcrypt==5.0.0 was incompatible with passlib==1.7.4 due to a strict 72-byte check — pinned to bcrypt==4.0.1.

**Phase 3 — RAG pipeline**
Agent implemented document loading, heading-based chunking, sentence-transformer embeddings, numpy cosine similarity retrieval, and npz cache. All 6 retrieval routing tests passed on first run.

**Phase 4 — Gemini/Claude decision engine**
Agent implemented the structured prompt, JSON extraction with strict=False for occasional unescaped newlines, Pydantic validation, and fallback to NEEDS_MORE_INFORMATION. The project was later migrated from Gemini (which had a 20 requests/day free-tier limit that was exhausted during testing) to the Anthropic Claude API, which resolved all quota issues and achieved 100% eval accuracy.

**Phase 5 — Ticket endpoints**
Agent wired POST /tickets, GET /tickets, and GET /tickets/{id} end-to-end with full RAG and AI integration. Authorization check (ticket.user_id == current_user.id) correctly returns 403. All endpoint tests passed.

**Phase 6 — Streamlit frontend**
Agent implemented the three-page UI: Login/Register, New Decision, History. Login state managed via st.session_state. Decision results color-coded by action category (green for approvals, red for rejections, yellow for needs-more-info, blue for investigations).

**Phase 7 — Tests and evaluation**
Agent wrote 17 pytest tests across test_auth.py, test_tickets.py, and test_authorization.py. Tests use isolated SQLite test databases and mock the AI call so they run without any API key. Evaluation script confirmed 100% accuracy (5/5) on the sample test cases.

**Phase 8 — Documentation and final commit**
README and DEVELOPMENT.md written. Git repository initialized and pushed to GitHub.

## Key engineering decisions

**No LangChain or vector database.** The knowledge base is 6 small markdown files totalling under 5KB. sentence-transformers plus numpy cosine similarity is sufficient and keeps the dependency footprint minimal.

**Heading-based chunking.** Each policy file has one top-level heading, so the splitter produces one chunk per file. Retrieval quality was confirmed at 6/6 on routing queries to the correct source file.

**sources stored as JSON string in SQLite.** SQLite has no native array type. JSON serialization in the decisions.sources column avoids a separate join table for a small field.

**Mock-based tests.** The AI call is mocked in all tests so the suite runs offline, does not consume quota, and is deterministic. 17/17 tests pass.

**Graceful API error fallback.** API errors (rate limits, network failures, invalid JSON responses) are caught and return NEEDS_MORE_INFORMATION with a clean 201 instead of crashing with a 500.

**bcrypt pinned to 4.0.1.** passlib 1.7.4 is incompatible with bcrypt 5.0.0. Pinned for compatibility.

**Switched from Gemini to Claude API.** Gemini free tier has a 20 requests/day limit which was exhausted during development testing. Switched to Anthropic Claude API which resolved quota issues and achieved 100% accuracy on all evaluation cases.

## What I would improve with more time

- Add retry with exponential backoff for API quota errors
- Add pagination to GET /tickets for large histories
- Store retrieved policy chunks alongside the decision so the UI can show the exact grounding text
- Add structured logging instead of relying on uvicorn default output
- Rebuild embeddings cache automatically when knowledge_base/ files change
- Add input validation on ticket message length
