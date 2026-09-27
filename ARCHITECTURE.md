# Architecture — AI Email Triage & RAG Assistant

This document describes the final architecture of the DevSynt Task 6 **AI Email Triage & RAG Assistant**.

The system combines **n8n automation**, **Gmail**, **Google Gemini**, the reused **Task 5 FastAPI + Qdrant RAG backend**, **Discord**, and **Google Sheets**.

---

## High-Level Architecture

```text
External Sender
      |
      v
   Gmail Inbox
      |
      v
  Gmail Trigger
      |
      v
 Normalize Email
      |
      v
Google Sheets Duplicate Lookup
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
          +-------+-------+
          |               |
       Low Conf.        Confident
          |               |
          v               v
 Human Review       Decision Engine
                          |
        +-----------------+------------------------------+
        |           |            |           |           |
        v           v            v           v           v
       RAG          HR        Manager      Human    Urgent/Promo/Spam
        |           |            |           |           |
        +-----------+------------+-----------+-----------+
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

## Component Responsibilities

```text
Gmail
  - receives incoming email
  - provides message metadata and attachments
  - sends replies and forwards
  - archives / marks spam
  - marks processed messages read

n8n
  - orchestrates the complete flow
  - normalizes and cleans input
  - checks duplicate message IDs
  - invokes Gemini
  - applies deterministic routing
  - calls the Task 5 RAG API
  - triggers Gmail / Discord actions
  - writes final processing logs

Gemini
  - classifies intent
  - assigns priority
  - provides confidence
  - recommends an allowed action
  - creates a standalone RAG query when needed

FastAPI + Qdrant
  - reuse the Task 5 knowledge base
  - embed the RAG query
  - retrieve supporting evidence
  - generate grounded answers
  - return grounded status and sources

Discord
  - HR notifications
  - manager / human-review notifications
  - urgent alerts

Google Sheets
  - duplicate lookup by message_id
  - final processing log
```

---

## 1. Email Intake

The Gmail Trigger is the system entry point.

```text
Gmail
  |
  +-- message_id
  +-- thread_id
  +-- sender
  +-- subject
  +-- body
  +-- timestamp
  +-- attachments
```

Attachments are downloaded by the Gmail trigger.

The workflow preserves attachment binary data so job application files can later be forwarded to HR.

---

## 2. Normalization

The normalization step converts Gmail output into a stable internal schema:

```json
{
  "message_id": "...",
  "thread_id": "...",
  "sender": "...",
  "Subject": "...",
  "body": "...",
  "timestamp": "...",
  "attachment_count": 0
}
```

Binary attachment data remains attached to the n8n item.

---

## 3. Duplicate Protection

Before using the LLM, the system checks Google Sheets for the incoming `message_id`.

```text
New Gmail message
      |
      v
Find Existing Message
      |
      v
message_id exists?
   |          |
  yes         no
   |          |
   v          v
 STOP      continue
```

This prevents duplicate:

- AI classification
- RAG calls
- customer replies
- forwarding
- Discord alerts
- final processing logs

---

## 4. Email Cleaning

The body-cleaning code reduces noise before classification.

It removes or reduces:

- raw tracking URLs
- bracketed URLs
- quoted `>` lines
- previous quoted reply blocks
- excessive whitespace

This improves intent classification and reduces unnecessary prompt tokens.

---

## 5. AI Classification

The cleaned email is sent to Gemini through the n8n LLM chain.

The model returns structured data:

```json
{
  "category": "sales_inquiry",
  "priority": "normal",
  "confidence": 0.98,
  "requires_human": false,
  "action": "rag_query",
  "reason": "Customer is asking about an existing service.",
  "rag_query": "What does Premium Relocation Support include?"
}
```

A Structured Output Parser keeps downstream fields predictable.

---

## 6. Confidence Guard

```text
confidence >= 0.75
       |
       v
 normal routing

confidence < 0.75
       |
       v
 human review
```

Low-confidence classifications do not trigger an automatic business decision.

---

## 7. Decision Engine

The n8n Switch node routes by `output.action`.

```text
rag_query
forward_hr
forward_manager
human_review
urgent_escalation
archive
mark_spam
```

Routing rules:

| Intent | Action |
|---|---|
| General query | RAG |
| Sales inquiry | RAG |
| Job application | HR |
| Project | Manager |
| Internal | Manager |
| Complaint | Manager |
| Meeting | Human review |
| Urgent | Urgent escalation |
| Promotional | Archive |
| Spam | Mark as spam |
| Other | Human review |

---

## 8. RAG Integration

Task 6 reuses the Task 5 RAG backend rather than rebuilding another knowledge base.

n8n calls:

```http
POST http://host.docker.internal:8000/api/v1/rag/query
Content-Type: application/json
```

Example request:

```json
{
  "question": "How much does Premium Relocation Support cost?"
}
```

RAG flow:

```text
Standalone email question
          |
          v
  Gemini query embedding
          |
          v
   Qdrant semantic search
          |
          v
    Top-K evidence
          |
          v
 Grounded Gemini generation
          |
          v
Answer + grounded + sources
```

---

## 9. RAG Grounding Guard

The RAG API still returns grounding information internally even though that field is not stored as a Google Sheets column.

```text
RAG response
     |
     v
grounded?
  |       |
 yes      no
  |       |
  v       v
Reply   Safe reply
         |
         v
 Human review alert
```

This prevents unsupported facts from being presented as knowledge-base answers.

---

## 10. Job Application Flow

```text
Job Application
      |
      v
Prepare HR Forward
      |
      v
Restore Original Gmail Binary Attachments
      |
      v
Forward Email + CV to HR
      |
      v
Discord HR Notification
      |
      v
Mark Original Message Read
      |
      v
Google Sheets Log
```

The AI only identifies and routes the application. It does not make hiring decisions.

---

## 11. Manager Flow

```text
Project / Internal / Complaint
             |
             v
      Gemini Classification
             |
             v
       forward_manager
             |
             v
       Manager Email
             |
             v
   Discord Manager Alert
             |
             v
       Mark as Read
             |
             v
            Log
```

No business decision is made automatically.

---

## 12. Meeting Flow

Meeting requests are routed for human review.

```text
Meeting Request
      |
      v
human_review
      |
      v
Discord Manager Notification
      |
      v
Mark as Read
      |
      v
Log
```

The workflow does not automatically schedule meetings.

---

## 13. Urgent Flow

```text
Urgent / Critical Email
          |
          v
  urgent_escalation
          |
          v
High-Priority Discord Alert
          |
          v
      Manager Email
          |
          v
      Mark as Read
          |
          v
           Log
```

---

## 14. Promotional and Spam Flow

### Promotional

```text
promotional
    |
    v
remove INBOX label
    |
    v
archive
    |
    v
mark as read
    |
    v
log
```

### Spam

```text
spam
 |
 v
apply SPAM label
 |
 v
mark as read
 |
 v
log
```

These routes are not forwarded to employees.

---

## 15. Mark as Read

All successful terminal paths converge on the Gmail mark-as-read operation.

The original email is marked read only after the required action succeeds.

```text
Successful route action
        |
        v
Mark Original Gmail Message Read
        |
        v
Append Processing Log
```

This avoids hiding a message that failed before its intended action completed.

---

## 16. Google Sheets Logging

Google Sheets serves two purposes:

```text
1. Duplicate lookup using message_id
2. Final operational processing log
```

Current final log columns:

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

A log row is created only when the execution reaches the final append step.

Therefore, an email can be absent from the sheet if:

- the execution failed before final logging,
- Gemini or another external service returned an error,
- a Gmail / Discord action failed,
- the email was stopped as a duplicate,
- the trigger did not process that email during an active polling window.

---

## 17. End-to-End Sequence

```text
Sender
  |
  v
Gmail Inbox
  |
  v
n8n Gmail Trigger
  |
  v
Normalize Email
  |
  v
Google Sheets message_id lookup
  |
  +---- duplicate ----> STOP
  |
  +---- new email
           |
           v
       Clean Body
           |
           v
    Gemini Classifier
           |
           v
    Confidence Guard
           |
           v
     Decision Engine
           |
    +------+------+------+------+------+------+
    |      |      |      |      |      |
   RAG     HR   Manager Human  Urgent Archive/Spam
    |      |      |      |      |      |
    +------+------+------+------+------+
           |
           v
    Gmail / Discord Action
           |
           v
       Mark Read
           |
           v
    Google Sheets Log
```

---

## 18. RAG Backend Boundary

Task 6 treats Task 5 as an external knowledge service.

```text
n8n
 |
 | HTTP POST
 v
FastAPI
 |
 +-- query embedding
 +-- Qdrant retrieval
 +-- evidence thresholding
 +-- Gemini grounded generation
 +-- answer + grounded + sources
```

This keeps email orchestration separate from knowledge retrieval.

---

## 19. Reliability Controls

```text
Duplicate Check
      +
Confidence Guard
      +
RAG Grounding Check
      +
Human Review
      +
Post-action Mark-as-read
      +
Processing Log
```

Temporary external-provider failures can still occur. During testing, Gemini returned a temporary `503 Service Unavailable` / high-demand error. Retry-on-failure can be enabled on provider-facing nodes for a production deployment.

---

## 20. Current Limitation: Thread Context

The workflow stores `thread_id`, and Gmail replies remain associated with Gmail conversations.

However, the current submitted version does not reconstruct the entire historical thread and inject it into the classifier or RAG prompt.

```text
message-level duplicate protection   implemented
Gmail reply threading                available through Gmail
full historical conversation memory  limited
```

A future extension can retrieve previous messages by `thread_id` before classification.

---

## Deployment View

```text
External Sender
      |
      v
    Gmail
      |
      v
Docker / n8n
  |      |       |        |
  |      |       |        +----> Google Sheets
  |      |       |
  |      |       +-------------> Discord
  |      |
  |      +---------------------> Gemini API
  |
  +-- host.docker.internal:8000
              |
              v
        FastAPI RAG Backend
              |
        +-----+------+
        |            |
        v            v
     Qdrant        Gemini
```

---

## Design Summary

The architecture separates responsibilities:

- **Gmail** — transport and inbox actions
- **n8n** — orchestration and decision flow
- **Gemini** — classification
- **FastAPI + Qdrant** — grounded knowledge retrieval
- **Discord** — human escalation
- **Google Sheets** — duplicate lookup and operational log

This separation makes the workflow easy to explain, test, debug and extend without rebuilding the Task 5 RAG system.
