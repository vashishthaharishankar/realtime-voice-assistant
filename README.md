# Kotak Mahindra Prime — Realtime Voice Assistant

Speech-to-speech customer support agent (Swati) for Kotak Mahindra Prime car finance, with login, KYC-gated account tools, Qdrant knowledge search, and support ticket logging.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY and optional Qdrant/SMTP
```

### Index knowledge base (one time)

```bash
python scripts/build_knowledge_index.py --recreate
```

Requires `QDRANT_URL`, `QDRANT_API_KEY`, and `OPENAI_API_KEY` in `.env`.

### Run

```bash
python run.py
```

Open http://localhost:8000 — log in with a demo customer (password `Kmpl@2024`).

## Demo logins

| User | Email / Mobile | Password |
|------|----------------|----------|
| Priya Nair | `priya.nair@email.com` or `+919930869699` | `Kmpl@2024` |
| Rahul Sharma | `rahul.sharma@email.com` | `Kmpl@2024` |
| Amit Patel | `amit.patel@email.com` | `Kmpl@2024` |

## Data

- `database/` — CSV mock data (customers, loans, transactions, support tickets)
- `knowledge_base/` — PDFs and text for Qdrant indexing

## Features

- Login before voice session; agent only serves logged-in customer
- KYC verification once per call (Aadhaar last 4 → PIN → mobile last 4)
- Account balance & last 3 transactions after KYC
- Email PDF documents (statement, interest certificate, loan certificate, NOC)
- Knowledge base search via Qdrant (no hallucination beyond retrieved text)
- Support ticket CSV on call end
