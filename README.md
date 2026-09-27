# AI Email Triage & RAG Assistant

An AI-powered email automation system built for the **DevSynt AI Internship – Task 6**.

The workflow monitors a Gmail inbox, normalizes and cleans incoming email content, classifies each message by intent and priority using Gemini, applies deterministic routing rules, reuses the **Task 5 NorthBridge Living RAG backend** for knowledge-grounded answers, routes sensitive or important emails to humans, sends Discord alerts, prevents duplicate processing, marks processed emails as read, and logs outcomes to Google Sheets.

> Core principle: **AI does not answer every email.** Emails that require hiring, managerial, meeting, urgent, complaint, or low-confidence decisions are routed to a human.

---

## Demo

The final demo is split into two parts.

- **Demo Part 1:** https://www.loom.com/share/2ee9ceeaa5be4061933fd0d128022e93
- **Demo Part 2:** https://www.loom.com/share/e14a25c04dd64cc9b4623ec6f1472aff

### Google Sheets Processing Log

- **Live Processing Log:** https://docs.google.com/spreadsheets/d/1k6pDTApmWhj1uVvIwOVUtWFANwfzrPyQHLMsivFQO7Q/edit?usp=sharing

The sheet is used both as an operational processing log and as the source for `message_id` duplicate protection.

---

## Features

### Email Intake

- Gmail polling trigger
- Sender, subject, body, message ID, thread ID and timestamp extraction
- Attachment download support
- Binary attachment preservation through the workflow
- Email body cleanup for URLs, quoted replies and unnecessary text

### AI Classification

Each email is classified into one of:

- `general_query`
- `sales_inquiry`
- `job_application`
- `project_related`
- `internal_communication`
- `meeting_request`
- `urgent_request`
- `complaint`
- `promotional`
- `spam`
- `other`

The classifier also returns:

- priority
- confidence
- `requires_human`
- recommended action
- reason
- RAG query when applicable

### Confidence Guard

Emails with classification confidence below `0.75` are not routed automatically. They are escalated to the manager for human review.

### RAG Responses

General and sales queries are sent to the existing Task 5 FastAPI RAG backend:

```http
POST /api/v1/rag/query
```

n8n calls the backend from Docker using:

```text
http://host.docker.internal:8000/api/v1/rag/query
```

If the answer is grounded, the workflow sends the generated answer as a Gmail reply.

If the knowledge base does not contain sufficient evidence, the workflow:

1. sends a safe acknowledgement to the sender,
2. avoids inventing an answer,
3. sends a human-review alert to Discord.

### Human Routing

- Job application → forward to HR + Discord HR notification
- Project/internal/complaint → forward to Manager + Discord notification
- Meeting request → human review notification
- Urgent request → urgent Discord alert + manager email
- Promotional email → archive
- Spam → move to spam
- Low-confidence classification → human review

### Attachment Forwarding

Job applications preserve Gmail binary attachments and forward them to HR.

### Duplicate Protection

Before classification, the workflow checks Google Sheets for the Gmail `message_id`.

If the message was already processed:

```text
Find Existing Message
        |
        v
Already Processed? = TRUE
        |
        v
       STOP
```

This prevents duplicate AI calls, replies, forwarding and logging.

### Logging

Every processing path that successfully reaches the final logging stage is appended to Google Sheets.

Current log fields:

```text
message_id
thread_id
sender
subject
email_timestamp
processed_at
category
priority
confidence
action
reason
rag_used
response_sent
forwarded_to
status
```

### Inbox State

After the required action succeeds, the original Gmail message is marked as read.

---

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

High-level flow:

```text
Incoming Gmail
      |
      v
Normalize Email
      |
      v
Google Sheets Duplicate Check
      |
      v
Already Processed?
   |              |
  YES            NO
   |              |
   v              v
 STOP      Restore Email Data
                  |
                  v
          Clean Email Body
                  |
                  v
          Gemini Classification
                  |
                  v
          Confidence Guard
                  |
                  v
          Decision / Routing
                  |
      +-----------+-----------+-----------+
      |           |           |           |
      v           v           v           v
     RAG          HR       Manager      Human
      |           |           |           |
      +-----------+-----------+-----------+
                  |
                  v
       Gmail / Discord Action
                  |
                  v
        Mark Original Email Read
                  |
                  v
        Google Sheets Log
```

---

## Tech Stack

### Automation

- n8n
- Docker

### Email

- Gmail Trigger
- Gmail OAuth2
- Gmail reply / send / archive / spam / mark-as-read operations

### AI

- Google Gemini for email intent classification
- Structured Output Parser in n8n

### RAG Backend

Reused from Task 5:

- Python 3.12
- FastAPI
- Gemini LLM and embeddings
- Qdrant
- SQLite
- PyMuPDF
- python-docx

### Integrations

- Discord Webhooks
- Google Sheets
- ngrok for local n8n access during development

---

## Project Structure

Recommended final repository layout:

```text
AI-Email-Triage-RAG-Assistant/
|
├── backend/
│   ├── app/
│   ├── requirements.txt
│   └── .env.example
|
├── knowledge-base/
│   ├── 01_NorthBridge_Company_Profile.pdf
│   ├── 02_NorthBridge_Property_Portfolio_2026.pdf
│   ├── 03_NorthBridge_Services_and_Pricing_Guide.pdf
│   ├── 04_NorthBridge_Customer_FAQ_and_Move_In_Guide.pdf
│   └── 05_NorthBridge_Policies_Terms_and_Escalation_Guide.pdf
|
├── workflows/
│   ├── AI Email Triage & RAG Assistant.json
│   └── task6_test_email_sender.json
|
├── docs/
│   └── ARCHITECTURE.md
|
├── tests/
│   └── TEST_REPORT.md
|
├── .gitignore
└── README.md
```

---

## Prerequisites

Install or prepare:

- Docker Desktop
- n8n
- Python 3.12
- Gmail account with OAuth credentials
- Google Gemini API key
- Google Sheets OAuth credentials
- Discord webhook credentials
- Task 5 RAG backend and indexed NorthBridge knowledge base

---

## Backend Setup

From the Task 6 project backend:

```powershell
cd "backend"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create `.env` from `.env.example`.

Example backend configuration:

```env
APP_NAME=DevSynt AI RAG Assistant
APP_ENV=development
API_V1_PREFIX=/api/v1

DATABASE_URL=sqlite:///./rag_app.db
UPLOAD_DIR=uploads
MAX_UPLOAD_MB=20
CORS_ORIGINS=http://localhost:5173

GEMINI_API_KEY=YOUR_KEY
GEMINI_LLM_MODEL=YOUR_CONFIGURED_MODEL
GEMINI_EMBEDDING_MODEL=YOUR_CONFIGURED_EMBEDDING_MODEL
EMBEDDING_DIMENSION=768

QDRANT_PATH=./qdrant_data
QDRANT_COLLECTION=documents

CHUNK_SIZE=1200
CHUNK_OVERLAP=200
TOP_K=5
MIN_RETRIEVAL_SCORE=0.50
```

Do not commit real API keys.

Start FastAPI so Docker can reach it:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

---

## n8n Setup

### Start Docker n8n

If the existing n8n container already exists:

```powershell
docker start n8n
```

During local development, ngrok may be used:

```powershell
ngrok http --domain=YOUR_DOMAIN.ngrok-free.dev 5678
```

### Import Workflow

Import:

```text
workflows/AI Email Triage & RAG Assistant.json
```

Configure credentials for:

- Gmail
- Google Gemini
- Google Sheets
- Discord

### Gmail Trigger

The Gmail trigger:

- polls for incoming email,
- downloads attachments,
- passes the original Gmail message to the normalization stage.

### Google Sheets

Create a sheet named:

```text
Task6_Email_Logs
```

with a tab such as:

```text
Logs
```

Current columns:

```text
message_id
thread_id
sender
subject
email_timestamp
processed_at
category
priority
confidence
action
reason
rag_used
response_sent
forwarded_to
status
```

Add the shareable sheet URL in the **Google Sheets Processing Log** section near the top of this README.

---

## Classification & Routing Logic

| Category | Action |
|---|---|
| `general_query` | RAG query |
| `sales_inquiry` | RAG query |
| `job_application` | Forward to HR + Discord |
| `project_related` | Forward to Manager + Discord |
| `internal_communication` | Forward to Manager + Discord |
| `complaint` | Forward to Manager + Discord |
| `meeting_request` | Human review |
| `urgent_request` | Urgent escalation |
| `promotional` | Archive |
| `spam` | Mark as spam |
| `other` | Human review |

Low-confidence classifications are also routed for human review.

---

## RAG Implementation

Task 6 does not rebuild the knowledge base.

It reuses the Task 5 NorthBridge Living RAG pipeline and document set:

1. Company Profile
2. Property Portfolio 2026
3. Services and Pricing Guide
4. Customer FAQ and Move-In Guide
5. Policies, Terms and Escalation Guide

Question flow:

```text
Email question
    |
    v
Classifier creates standalone RAG query
    |
    v
FastAPI /api/v1/rag/query
    |
    v
Gemini embedding
    |
    v
Qdrant semantic retrieval
    |
    v
Grounding checks
    |
    v
Gemini generation
    |
    v
Grounded answer + sources
```

Unsupported information returns an ungrounded result instead of a fabricated answer.

---

## Discord Integration

### HR Notifications

Used for job applications.

### Manager Notifications

Used for:

- project emails
- internal communication
- complaints
- meetings
- low-confidence classifications
- unsupported RAG queries requiring human review

### Urgent Notifications

Used for urgent or critical client situations.

Discord alerts include enough context for a human to review the sender, subject, classification, priority and reason.

---

## Testing

A separate n8n helper workflow can be used to send test emails:

```text
workflows/task6_test_email_sender.json
```

The final solution was exercised with known RAG queries, unknown-information queries, job applications with attachments, spam, and human-review scenarios.

Representative Google Sheets log evidence includes test IDs:

```text
01
02
04
09
10
```

Examples observed in the final log include:

- `01` → `sales_inquiry` → `rag_query`
- `04` → `job_application` → `forward_hr`
- `02` → `general_query` → `rag_query`
- `09` → `spam` → `mark_spam`
- `10` → `other` → `human_review`

A completed RAG test successfully returned the **GBP 149** Premium Relocation Support price from the knowledge base and sent it back by email.

A completed job-application test successfully forwarded the application and attachment to HR and triggered the HR notification route.

> The Google Sheets log is appended only after an execution reaches the final logging node. An email attempt that fails earlier, is stopped as a duplicate, or is interrupted by an external-provider error will not create a final log row.

---

## Reliability

The workflow includes:

- message ID duplicate protection
- confidence threshold
- grounded / ungrounded RAG branching
- safe fallback response
- human escalation
- attachment preservation
- Gmail message state update
- processing logs

For production use, enable **Retry On Fail** on temporary external-provider calls where appropriate.

---

## Current Limitations

- Gemini may occasionally return temporary `503 Service Unavailable` errors during periods of high demand.
- The workflow depends on third-party availability for Gmail, Gemini, Discord and Google Sheets.
- Full historical Gmail thread reconstruction is not implemented in the current submitted workflow. Gmail replies remain attached to the original message/thread, but the classifier mainly evaluates the current incoming message.
- The workflow uses Google Sheets as a lightweight processing log rather than a transactional database.
- A log row is created only when the workflow reaches its final logging step.
- Development uses a locally hosted FastAPI RAG backend, so n8n Docker accesses it through `host.docker.internal`.
- HR and manager destinations in the development workflow should be replaced with production addresses before real deployment.
- The workflow is designed for evaluation/demo use and does not include multi-tenant authentication or enterprise monitoring.

---

## Security

- Never commit `.env`
- Never commit API keys
- Do not commit Gmail OAuth tokens/secrets
- Do not expose Discord webhook URLs publicly
- Keep local Qdrant persistence, SQLite files, virtual environments and runtime uploads out of Git

---

## Author

**Muhammad Saleem**
