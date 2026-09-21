# GenAI Customer Support Chatbot

A production-oriented GenAI customer-support chatbot extended from the original training project with internship features for knowledge-base management, multimodal customer-support processing, automated ticket workflows, SLA management, security, monitoring, and rollback.

---

## Project Overview

This project provides a production-style customer-support workflow covering:

- Knowledge-base document management
- Multimodal evidence processing
- Automated support-ticket creation
- Ticket priority and SLA management
- Skill-based ticket routing
- Duplicate and related-issue detection
- Sensitive-data protection
- Monitoring and health checks
- Version management and rollback

The internship tasks were implemented as additional features within the same training project.

---

# Task 1 — Production Knowledge-Base Pipeline

## Objective

Create a production pipeline that safely updates and monitors the chatbot's knowledge base.

## Features Implemented

- Processes new and modified documents
- Detects unchanged documents
- Detects duplicate documents
- Validates uploaded files
- Quarantines invalid and unsupported files
- Maintains document versions
- Supports version rollback
- Runs quality and grounding checks before activation
- Rejects updates that fail configured accuracy and grounding thresholds
- Supports configurable update scheduling
- Retries failed updates using configured retry delays
- Activates approved updates during the maintenance window
- Performs post-activation health checks
- Automatically rolls back unhealthy updates
- Provides access-control checks
- Provides prompt-injection protection
- Masks sensitive information
- Monitors latency
- Monitors failures
- Monitors confidence
- Monitors escalations
- Records important workflow events through audit logging
- Uses centralized JSON configuration

## Workflow

```text
                    Document
                       |
                       v
                +--------------+
                |   Validation |
                +--------------+
                       |
                       v
              +-------------------+
              | Change Detection  |
              | Duplicate Check   |
              +-------------------+
                       |
                       v
              +-------------------+
              | Quality / Ground  |
              |      Checks       |
              +-------------------+
                       |
                       v
              +-------------------+
              |    Versioning     |
              +-------------------+
                       |
                       v
              +-------------------+
              | Maintenance Window|
              +-------------------+
                       |
                       v
              +-------------------+
              |    Activation     |
              +-------------------+
                       |
                       v
              +-------------------+
              | Health Monitoring |
              +-------------------+
                    /       \
                   /         \
             Healthy       Unhealthy
                |              |
                v              v
           Keep Version    Auto Rollback
                               |
                               v
                         Previous Version
```

## Validation and Security

Documents are validated before processing. The pipeline applies access control, prompt-injection protection, sensitive-data masking, quarantine, audit logging, quality checks, and controlled activation.

## Testing

Task 1 functionality is covered by the project's automated test suite.

---

# Task 2 — Multimodal Customer Support

## Objective

Extend the chatbot to analyse customer messages together with screenshots, invoices, PDFs, and product images.

## Features Implemented

- Customer-message analysis
- Screenshot processing
- Invoice processing
- PDF processing
- Product-image processing
- OCR-based information extraction
- Order ID extraction
- Date extraction
- Amount extraction
- Product information extraction
- Error-code extraction
- Comparison of extracted evidence with the customer message
- Evidence conflict detection
- Low-quality image handling
- Clarification requests when evidence is incomplete or conflicting
- Missing-value handling without inventing values
- Personal-data masking
- Payment-information masking
- Unsafe-file rejection
- Prompt-injection protection for instructions contained in uploaded evidence
- Background processing for delayed requests
- Customer notification for delayed processing
- Configurable uploaded-file retention and deletion

## Workflow

```text
Customer Message + Uploaded Evidence
                  |
                  v
          File Validation
                  |
                  v
          Security Checks
                  |
                  v
             OCR / Parsing
                  |
                  v
        Evidence Extraction
                  |
                  v
       Compare With Message
             /         \
            /           \
         Match        Conflict
           |              |
           v              v
       Continue       Request
                      Clarification
```

## Validation and Security

Uploaded evidence is validated before processing. The workflow handles unsafe files, low-quality evidence, conflicting information, sensitive data, and prompt-injection attempts.

Missing information is not invented. When evidence is insufficient or conflicting, the workflow can request clarification or another file.

## Testing

Task 2 functionality is covered by the project's multimodal and evidence-processing test suites.

---

# Task 3 — Automated Ticket Workflow

## Objective

Convert unresolved customer conversations into structured support tickets and manage their priority, routing, and SLA lifecycle.

## Features Implemented

- Structured ticket creation
- Customer-detail extraction
- Order-detail extraction
- Product information
- Issue description
- Evidence information
- Contact information
- Missing mandatory information detection
- Priority calculation
- Severity consideration
- Sentiment consideration
- Waiting-time consideration
- Customer-impact consideration
- SLA urgency consideration
- P1, P2, P3, and P4 priorities
- Configurable SLA durations
- Business-hour calculation
- Weekend exclusion
- Holiday exclusion
- 75% SLA warning
- SLA breach detection
- SLA escalation
- Runtime SLA configuration changes
- Skill-based team routing
- Team availability checks
- Workload-based routing
- After-hours handling
- Duplicate ticket detection
- Related-issue grouping
- Unrelated-issue separation
- Masked agent handoff
- Ticket serialization

## Workflow

```text
Customer Conversation
          |
          v
   Ticket Extraction
          |
          v
Missing Information Check
          |
          v
  Priority Calculation
          |
          v
    SLA Calculation
          |
          v
    Team Routing
          |
          v
Duplicate / Related Check
          |
          v
   Agent Handoff
          |
          v
SLA Monitoring
      /        \
 Warning       Breach
    |             |
    v             v
 Continue      Escalate
```

## Validation and Security

The ticket workflow checks mandatory information, team availability, workload, SLA conditions, duplicate requests, and related issues.

Agent handoff information is masked to reduce unnecessary exposure of customer and contact information.

## Testing

Task 3 has a dedicated test suite covering:

- Structured ticket extraction
- Missing mandatory information
- Priority calculation
- Business-hour SLA
- Weekend exclusion
- Holiday exclusion
- SLA warning at 75%
- SLA breach escalation
- Runtime SLA changes
- Available-team routing
- Unavailable-team handling
- Duplicate detection
- Unrelated request handling
- Masked agent handoff
- After-hours SLA handling
- Ticket serialization

Task 3 test result:

```text
15 tests
15 passed
0 failed
```

---

# Security

Security controls implemented across the project include:

- Access control
- Prompt-injection protection
- Sensitive-data masking
- Payment-information masking
- Unsafe-file validation
- Audit logging
- Controlled activation
- Version rollback

---

# Monitoring

The project includes monitoring for:

- Processing latency
- Failures
- Confidence
- Escalations
- Service health
- Activation health

---

# Configuration

Central configuration is maintained in:

```text
config/settings.json
```

Configuration includes:

- Maintenance windows
- Retry delays
- Quality thresholds
- Health-check settings
- Ticket workflow settings
- SLA durations
- Business hours
- Holidays
- Support teams
- Priority weights
- Duplicate detection thresholds
- Related-ticket thresholds

---

# Project Structure

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
│   ├── multimodal.py
│   ├── orchestrator.py
│   ├── pipeline.py
│   ├── prompt_security.py
│   ├── quality.py
│   ├── quarantine.py
│   ├── scheduler.py
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
│   ├── test_*.py
│   └── test_ticket_workflow.py
│
├── .gitignore
└── README.md
```

---

# Setup

## Clone the Repository

```bash
git clone https://github.com/yathinn69-ops/genai-customer-support-chatbot.git
cd genai-customer-support-chatbot
```

## Create a Virtual Environment

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

## Install Dependencies

If the repository contains a requirements file:

```powershell
pip install -r requirements.txt
```

---

# Testing

## Run the Complete Test Suite

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## Run Task 3 Tests

```bash
python -m unittest tests.test_ticket_workflow -v
```

## Latest Full Test Result

```text
179 tests
179 passed
0 failed
0 errors
```

## Latest Task 3 Test Result

```text
15 tests
15 passed
0 failed
```

---

# Internship Task Status

| Task | Description | Status |
|---|---|---|
| Task 1 | Production Knowledge-Base Pipeline | Completed |
| Task 2 | Multimodal Customer Support | Completed |
| Task 3 | Automated Ticket Workflow and SLA Management | Completed |

---

# Development Approach

The internship functionality was implemented as extensions to the original training project rather than as an unrelated project.

The features were developed incrementally and tested after implementation.

The complete project test suite was executed after integrating the internship tasks to verify that the existing functionality and internship functionality work together.

---

# Repository

GitHub Repository:

https://github.com/yathinn69-ops/genai-customer-support-chatbot

The repository contains:

- Source code
- Configuration
- Automated tests
- Demonstration files
- Project documentation
- Internship task implementations

---

# Final Status

```text
Task 1 — Production Knowledge-Base Pipeline
Status: Completed

Task 2 — Multimodal Customer Support
Status: Completed

Task 3 — Automated Ticket Workflow and SLA Management
Status: Completed

Full Test Suite:
179 / 179 tests passing
```
