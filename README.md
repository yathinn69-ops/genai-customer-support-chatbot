# GenAI Customer Support Chatbot

A production-oriented Generative AI customer support chatbot developed as an internship project. The system is implemented incrementally across six assigned tasks and includes knowledge-base management, multimodal evidence processing, ticket workflows, RAG-based knowledge retrieval, sentiment analysis, escalation, multilingual conversations, and session management.

## Project Overview

The chatbot is designed to support an end-to-end customer-support workflow:

- Maintain and update a chatbot knowledge base
- Process new and modified support documents
- Detect duplicate and invalid documents
- Protect the pipeline against prompt injection and sensitive-data exposure
- Analyse customer messages, screenshots, invoices, PDFs, and product images
- Extract and validate customer/order evidence
- Convert unresolved conversations into structured support tickets
- Prioritize and route tickets using configurable SLA rules
- Retrieve authorized and time-valid knowledge using RAG
- Provide source-grounded answers
- Detect sentiment, frustration, urgency, sarcasm, and high-risk issues
- Automatically escalate qualifying conversations
- Support multilingual and mixed-language conversations
- Preserve conversation context and manage session expiry/restoration

---

# Internship Tasks

## Task 1 – Production Knowledge-Base Pipeline

The production pipeline updates and monitors the chatbot knowledge base.

### Implemented capabilities

- Processes only new or modified documents
- Detects duplicate documents
- Quarantines invalid files
- Maintains document versions
- Supports rollback
- Runs quality tests before activation
- Rejects updates that fail configured accuracy or grounding thresholds
- Supports configurable update scheduling
- Retries failed updates after 15, 30, and 60 minutes
- Activates approved updates only during the maintenance window
- Performs post-activation health checks
- Supports automatic rollback when health checks fail
- Implements access control
- Provides prompt-injection protection
- Masks sensitive data
- Monitors latency, failures, confidence, and escalations

### Main Task 1 components

```text
app/access_control.py
app/activation.py
app/audit.py
app/config.py
app/document_tracker.py
app/maintenance.py
app/monitoring.py
app/orchestrator.py
app/pipeline.py
app/prompt_security.py
app/quality.py
app/quarantine.py
app/scheduler.py
app/validation.py
app/versioning.py
```

---

# Task 2 – Multimodal Customer Support

The chatbot was extended to analyse customer messages and supporting evidence such as screenshots, invoices, PDFs, and product images.

### Implemented capabilities

- Processes customer messages and supporting files
- Extracts order IDs
- Extracts dates
- Extracts monetary amounts
- Extracts product information
- Extracts error codes
- Compares extracted evidence with the customer's message
- Detects conflicting evidence
- Handles low-quality or unclear evidence
- Requests clarification or another file when evidence is insufficient
- Does not invent missing values
- Masks personal and payment information in logs
- Rejects unsafe files
- Rejects malicious instructions hidden inside uploaded evidence
- Supports background processing for long-running evidence processing
- Supports notification of delayed processing
- Supports configured upload retention and cleanup

### Main Task 2 components

```text
app/background_queue.py
app/data_masking.py
app/evidence_extractor.py
app/multimodal.py
```

---

# Task 3 – Automated Ticket Workflow and SLA Management

The chatbot converts unresolved customer conversations into structured support tickets.

### Implemented capabilities

- Extracts customer details
- Extracts order details
- Extracts product information
- Extracts issue information
- Extracts evidence
- Extracts contact details
- Identifies missing mandatory information
- Calculates ticket priority
- Considers severity
- Considers sentiment
- Considers waiting time
- Considers customer impact
- Considers SLA conditions
- Routes tickets using team skills
- Considers team availability
- Considers workload
- Considers business hours
- Supports configurable SLA durations
- Excludes configured weekends and holidays from SLA calculations
- Generates a warning at 75% of the allowed SLA time
- Escalates after an SLA breach
- Supports runtime SLA configuration changes
- Detects duplicate requests
- Groups related issues
- Separates unrelated issues
- Generates a masked handoff summary

### Main Task 3 component

```text
app/ticket_workflow.py
tests/test_ticket_workflow.py
```

### Task 3 dedicated test result

```text
15 / 15 tests passing
```

---

# Task 4 – RAG Knowledge Assistant

The chatbot was extended with a retrieval-augmented generation knowledge assistant using product documents, FAQs, policies, and troubleshooting information.

### Document metadata

Knowledge documents support metadata including:

- Product
- Region
- Access level
- Effective date
- Expiry date
- Document version

### Implemented capabilities

- Retrieves authorized information
- Selects the latest applicable policy when documents conflict
- Ignores future-dated policies for current questions
- Ignores expired policies for current questions
- Supports historical questions using the policy active on the requested date
- Provides source citations for factual answers
- Refuses or requests clarification when evidence is missing
- Handles ambiguous evidence
- Detects unsupported claims
- Ignores malicious instructions embedded in knowledge documents

### Main Task 4 component

```text
app/rag_assistant.py
tests/test_rag_assistant.py
```

### Task 4 dedicated test result

```text
22 / 22 tests passing
```

---

# Task 5 – Sentiment Analysis and Escalation

The chatbot was extended with multilingual sentiment analysis and automated escalation handling.

### Sentiment capabilities

The system identifies:

- Positive messages
- Neutral messages
- Negative messages
- Frustrated messages
- Very negative messages
- Urgent messages
- Sarcastic messages

The analysis considers the current message and available conversation history.

### Implemented capabilities

- Generates sentiment confidence scores
- Detects sarcasm
- Adjusts response tone without changing business policies
- Detects repeated negative messages
- Detects high-risk account compromise issues
- Detects duplicate payment issues
- Detects legal threats
- Handles calm high-risk complaints
- Escalates repeated negative conversations
- Routes urgent after-hours complaints to an on-call queue
- Schedules normal after-hours complaints for the next working day
- Handles weekends
- Handles configured holidays
- Escalates negative conversations unresolved for more than 15 minutes
- Records escalation reason
- Records the triggered condition
- Records a conversation summary
- Records escalation creation time
- Records the escalation queue

### Tone handling

The implementation supports tone selection based on sentiment, including:

- Friendly tone for positive conversations
- Empathetic tone for negative conversations
- Neutral-professional tone for neutral conversations
- Calm and clarifying tone for detected sarcasm

### Main Task 5 component

```text
app/sentiment_escalation.py
tests/test_sentiment_escalation.py
task5_result.txt
```

### Task 5 dedicated test result

```text
28 / 28 tests passing
```

---

# Task 6 – Multilingual Conversation and Session Management

Task 6 extends the chatbot to support additional languages, mixed-language conversations, language switching, conversation context, and configurable session management.

## Supported languages

The configured language set includes:

- English
- Hindi
- Kannada
- Spanish
- Tamil
- Telugu
- French

The three additional languages introduced for Task 6 are:

- Tamil
- Telugu
- French

English is included as a supported language.

## Multilingual capabilities

The Task 6 implementation supports:

- Multilingual customer messages
- Mixed-language messages
- Language switching within the same conversation
- Language confidence scoring
- Intent confidence scoring
- Clarification when language confidence is low
- Clarification when intent confidence is low
- Spelling correction
- Transliteration
- Multiple requests in a single message
- Corrected customer information
- Preservation of important customer information
- Conversation context retention

## Information preservation

The system is designed to preserve:

- Customer names
- Order IDs
- Dates
- Product codes

## Conversation context

The system supports:

- At least 10 messages of configured context
- Multiple simultaneous customer sessions
- Context retention within the active session
- Conversation summary restoration when applicable

## Session lifecycle

The configured Task 6 session rules are:

- Active session inactivity timeout: 30 minutes
- Session restoration window: 24 hours
- A returning customer within the restoration window can have the conversation summary restored
- A returning customer after the restoration window begins a new session

## Configurable Task 6 settings

The configuration includes:

```json
"multilingual_session": {
    "languages": [
        "english",
        "hindi",
        "kannada",
        "spanish",
        "tamil",
        "telugu",
        "french"
    ],
    "additional_languages": [
        "tamil",
        "telugu",
        "french"
    ],
    "confidence_threshold": 0.60,
    "intent_confidence_threshold": 0.60,
    "max_context_messages": 10,
    "session_inactivity_minutes": 30,
    "session_restore_hours": 24
}
```

## Main Task 6 files

```text
app/multilingual_session.py
tests/test_multilingual_session.py
```

## Task 6 dedicated test result

```text
22 / 22 tests passing
```

---

# Project Structure

The main project is organized into application modules, configuration, data, demo material, and automated tests.

```text
genai-customer-support-chatbot/
│
├── app/
│   ├── access_control.py
│   ├── activation.py
│   ├── audit.py
│   ├── background_queue.py
│   ├── config.py
│   ├── data_masking.py
│   ├── document_tracker.py
│   ├── evidence_extractor.py
│   ├── main.py
│   ├── maintenance.py
│   ├── monitoring.py
│   ├── multilingual_session.py
│   ├── multimodal.py
│   ├── orchestrator.py
│   ├── pipeline.py
│   ├── prompt_security.py
│   ├── quality.py
│   ├── quarantine.py
│   ├── rag_assistant.py
│   ├── scheduler.py
│   ├── sentiment_escalation.py
│   ├── ticket_workflow.py
│   ├── validation.py
│   └── versioning.py
│
├── config/
│   └── settings.json
│
├── data/
│   ├── audit/
│   ├── documents/
│   ├── monitoring/
│   ├── quarantine/
│   └── versions/
│
├── demo/
│   └── sample_policy_v3.txt
│
├── tests/
│   ├── test_access_control.py
│   ├── test_activation.py
│   ├── test_audit.py
│   ├── test_config.py
│   ├── test_data_masking.py
│   ├── test_document_tracker.py
│   ├── test_evidence_extractor.py
│   ├── test_maintenance.py
│   ├── test_monitoring.py
│   ├── test_monitoring_integration.py
│   ├── test_multilingual_session.py
│   ├── test_multimodal.py
│   ├── test_orchestrator.py
│   ├── test_pipeline.py
│   ├── test_pipeline_masking.py
│   ├── test_pipeline_prompt_security.py
│   ├── test_quality.py
│   ├── test_rag_assistant.py
│   ├── test_scheduler.py
│   ├── test_sentiment_escalation.py
│   ├── test_ticket_workflow.py
│   ├── test_validation.py
│   └── test_versioning.py
│
├── .gitignore
├── README.md
└── task5_result.txt
```

---

# Configuration

The main configuration file is:

```text
config/settings.json
```

The project uses configuration for areas including:

- Maintenance windows
- Retry delays
- Quality thresholds
- Health checks
- Ticket business hours
- Weekends
- Holidays
- SLA durations
- Priority weights
- Duplicate similarity thresholds
- Related-issue similarity thresholds
- Support-team availability and workload
- Multilingual language settings
- Language confidence
- Intent confidence
- Context size
- Session inactivity
- Session restoration

---

# Testing

The project uses Python's built-in `unittest` framework.

## Run the complete test suite

Use the Python interpreter from the project Anaconda environment:

```powershell
& "$env:USERPROFILE\anaconda3\envs\chatbot-internship\python.exe" -m unittest discover -s tests -p "test_*.py"
```

## Final test result

```text
Ran 251 tests

OK
```

Therefore:

```text
251 / 251 tests passing
```

## Dedicated task test results

```text
Task 3: 15 / 15
Task 4: 22 / 22
Task 5: 28 / 28
Task 6: 22 / 22
```

The complete suite includes the automated tests for the earlier project components as well as the dedicated tests for the latest tasks.

---

# Security and Reliability

Security and reliability considerations implemented across the project include:

- Access control
- Prompt-injection protection
- Sensitive-data masking
- Input validation
- File validation
- Quarantine handling
- Audit logging
- Monitoring
- Quality checks before knowledge activation
- Version tracking
- Rollback support
- Health checks
- Duplicate detection
- Evidence validation
- Source-grounded RAG responses
- Authorization-aware retrieval
- Escalation auditing
- Safe handling of unsupported or ambiguous evidence

---

# Task Completion Summary

| Task | Description | Dedicated Tests | Status |
|------|-------------|----------------:|--------|
| Task 1 | Production Knowledge-Base Pipeline | Covered by project suite | Completed |
| Task 2 | Multimodal Customer Support | Covered by project suite | Completed |
| Task 3 | Automated Ticket Workflow and SLA Management | 15 / 15 | Completed |
| Task 4 | RAG Knowledge Assistant | 22 / 22 | Completed |
| Task 5 | Sentiment Analysis and Escalation | 28 / 28 | Completed |
| Task 6 | Multilingual Conversation and Session Management | 22 / 22 | Completed |

---

# Final Automated Test Status

```text
251 / 251 tests passing
```

# Overall Project Status

```text
All 6 internship tasks completed.
Full automated test suite passing.
Task 6 dedicated tests: 22 / 22 passing.
Complete project test suite: 251 / 251 passing.
```

---

# Development Environment

The project was tested using:

```text
Python 3.12.14
Anaconda environment: chatbot-internship
Windows
```

The environment can be invoked directly with:

```powershell
& "$env:USERPROFILE\anaconda3\envs\chatbot-internship\python.exe"
```

If `conda` is not available as a PowerShell command, the environment's Python executable can still be used directly as shown above.

---

# Internship Project

This repository contains the implementation developed incrementally for the assigned internship tasks.

The final implementation covers:

```text
Knowledge Base
      ↓
Multimodal Evidence
      ↓
Ticket Workflow + SLA
      ↓
RAG Knowledge Assistant
      ↓
Sentiment + Escalation
      ↓
Multilingual Conversations + Sessions
```

---

# Author

GenAI Customer Support Chatbot Internship Project
