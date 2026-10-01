# GenAI Customer Support Chatbot

A production-oriented GenAI customer support chatbot developed as part of an internship project. The system is designed to support customer conversations, knowledge-base management, multimodal evidence processing, automated ticket workflows, SLA management, RAG-based knowledge retrieval, sentiment analysis, and escalation.

The project is implemented incrementally across five internship tasks, with automated tests covering the implemented functionality.

---

## Project Overview

The chatbot provides an end-to-end customer support workflow that can:

- Maintain and update a chatbot knowledge base
- Process customer messages and supporting documents
- Analyze images, screenshots, invoices, and PDFs
- Convert unresolved conversations into structured tickets
- Prioritize and route tickets
- Manage configurable SLAs
- Retrieve authorized and time-valid knowledge using RAG
- Provide source-grounded answers
- Detect customer sentiment and urgency
- Detect sarcasm
- Identify high-risk customer situations
- Automatically escalate conversations
- Maintain escalation audit information
- Protect against prompt injection and sensitive-data exposure
- Validate functionality through automated tests

---

# Internship Tasks

## Task 1 – Production Knowledge-Base Pipeline

### Status: Completed

The production knowledge-base pipeline manages updates to the chatbot's knowledge base while validating documents and protecting the system from invalid or unsafe updates.

### Implemented Features

- Processes only new or modified documents
- Detects duplicate documents
- Quarantines invalid files
- Maintains document versions
- Supports rollback
- Runs quality tests before activating updates
- Rejects updates that reduce accuracy or grounding quality
- Supports configurable update scheduling
- Retries failed updates after:
  - 15 minutes
  - 30 minutes
  - 60 minutes
- Activates approved updates during the configured maintenance window
- Performs health checks after activation
- Automatically rolls back updates when health checks fail
- Supports access-control checks
- Provides prompt-injection protection
- Masks sensitive information
- Monitors:
  - Latency
  - Failures
  - Confidence
  - Escalations

### Validation

The pipeline includes automated testing for scenarios such as:

- Duplicate documents
- Invalid documents
- Failed updates
- Unauthorized access
- Maintenance-window handling
- Rollback behaviour
- Health-check failures

---

# Task 2 – Multimodal Customer Support

### Status: Completed

The multimodal customer-support component processes customer messages together with supporting evidence such as screenshots, invoices, PDFs, and product images.

### Implemented Features

The system can process and extract information such as:

- Order IDs
- Dates
- Amounts
- Product information
- Error codes

The extracted information can be compared with the customer's message to identify inconsistencies.

### Evidence Handling

The system:

- Detects conflicts between customer messages and uploaded evidence
- Requests clarification when information is missing or conflicting
- Handles low-quality or blurred images
- Avoids inventing missing values
- Masks personal and payment information in logs
- Rejects unsafe instructions contained in uploaded content
- Supports delayed/background processing for long-running operations
- Handles upload retention and expiration requirements

### Validation

Testing covers multimodal scenarios including:

- Low-quality images
- Conflicting invoices
- Delayed processing
- Expired files
- Prompt injection in uploaded content

---

# Task 3 – Automated Ticket Workflow and SLA Management

### Status: Completed

The ticket workflow converts unresolved customer conversations into structured support tickets and manages ticket priority, routing, SLA monitoring, and escalation.

## Ticket Creation

Structured tickets can contain:

- Customer details
- Order details
- Product information
- Issue description
- Evidence
- Contact details
- Missing mandatory information

## Priority Management

Ticket priority considers factors such as:

- Severity
- Customer sentiment
- Waiting time
- Customer impact
- SLA requirements

## Ticket Routing

Tickets can be routed based on:

- Agent/team skills
- Availability
- Current workload
- Business hours
- SLA requirements

## SLA Management

The system supports:

- Configurable SLA durations
- Business-hour calculations
- Weekend exclusions
- Holiday exclusions
- SLA warning thresholds
- SLA breach escalation
- Runtime SLA configuration changes

## Duplicate and Related Tickets

The workflow can:

- Detect duplicate tickets
- Group related conversations
- Keep unrelated conversations separate

## Handoff

The system generates a masked handoff summary for transferring a customer issue to the appropriate support workflow.

### Validation

Task 3 includes automated tests covering ticket creation, priority, routing, SLA handling, duplicate detection, business hours, escalation, and configuration changes.

---

# Task 4 – RAG Knowledge Assistant

### Status: Completed

The RAG-based knowledge assistant retrieves information from the chatbot's knowledge sources, including product documentation, FAQs, policies, and troubleshooting guides.

## Knowledge Metadata

Knowledge documents support metadata including:

- Product
- Region
- Access level
- Effective date
- Expiry date
- Document version

## Retrieval Rules

The system:

- Retrieves relevant knowledge for customer questions
- Applies authorization rules
- Uses the latest applicable policy when policies conflict
- Ignores future policies for current questions
- Excludes expired information from current responses
- Supports historical questions using the applicable information for the requested date
- Provides source citations for factual answers
- Refuses to provide unsupported information
- Requests clarification when evidence is ambiguous
- Detects unsupported claims
- Protects against prompt injection in retrieved content

## Grounded Responses

The RAG assistant is designed to ensure that factual responses are supported by available knowledge sources.

When sufficient evidence is unavailable, the system does not invent an answer and instead follows the configured clarification/refusal behaviour.

### Validation

Task 4 includes automated tests for:

- Authorization
- Effective dates
- Expiry dates
- Historical queries
- Policy conflicts
- Source citations
- Missing evidence
- Ambiguous evidence
- Unsupported claims
- Prompt injection

---

# Task 5 – Sentiment Analysis and Escalation

### Status: Completed

The sentiment and escalation component analyzes customer messages and conversation history to determine sentiment, urgency, sarcasm, risk, response tone, and escalation requirements.

## Sentiment Detection

The system supports:

- Positive
- Neutral
- Negative
- Frustrated
- Very negative
- Urgent

The analysis can consider both the current message and previous conversation history.

## Confidence Score

Sentiment analysis produces a confidence score representing the system's confidence in the detected sentiment.

## Sarcasm Detection

The system detects common sarcastic expressions so that sarcastic complaints are not incorrectly interpreted as positive customer feedback.

Example:

> "Great, another problem. Thanks for nothing."

This type of message is handled as a sarcastic/negative interaction rather than genuine positive feedback.

## Response Tone

The system adjusts the recommended response tone based on customer sentiment without changing the underlying business policies.

Supported tones include:

- Friendly
- Neutral professional
- Empathetic
- Calm and clarifying

---

## High-Risk Escalation

The system identifies high-risk situations including:

### Account Compromise

Examples include unauthorized access or unknown account activity.

### Duplicate Payment

Examples include a customer reporting that the same order or transaction was charged more than once.

### Legal Threat

Examples include a customer stating that they may take legal action.

High-risk conditions can trigger escalation even when the customer's wording is calm.

---

## Repeated Negative Messages

Repeated negative messages can trigger automatic escalation.

The threshold is configurable.

---

## Negative Conversation Timeout

A negative conversation that remains unresolved for more than 15 minutes can trigger automatic escalation.

---

## After-Hours Handling

Urgent complaints received outside business hours are routed to:

```text
on_call
```

Normal complaints received outside business hours are routed/scheduled for:

```text
next_business_day
```

Normal complaints received during business hours can continue through the normal workflow.

---

## Business Calendar

The escalation workflow supports:

- Business hours
- Weekends
- Configured holidays

This allows customer-support behaviour to change depending on the operating calendar.

---

## Escalation Audit Information

Each escalation records information including:

- Reason
- Triggered condition
- Conversation summary
- Creation timestamp
- Queue

This provides traceability for escalation decisions.

---

## Multilingual Sentiment

The sentiment component includes handling for supported multilingual examples, including:

- Hindi
- Kannada
- Spanish

The multilingual tests verify both language detection and negative/frustrated sentiment handling.

---

# Project Structure

```text
genai-customer-support-chatbot/
│
├── app/
│   ├── ticket_workflow.py
│   ├── rag_assistant.py
│   └── sentiment_escalation.py
│
├── config/
│   └── settings.json
│
├── demo/
│   └── ...
│
├── tests/
│   ├── test_ticket_workflow.py
│   ├── test_rag_assistant.py
│   ├── test_sentiment_escalation.py
│   └── ...
│
├── .gitignore
├── README.md
└── task5_result.txt
```

---

# Important Task 5 Files

## Implementation

```text
app/sentiment_escalation.py
```

This file contains the Task 5 sentiment and escalation implementation.

It includes functionality for:

- Sentiment classification
- Confidence scoring
- Sarcasm detection
- Conversation history
- High-risk detection
- Repeated-negative detection
- Timeout-based escalation
- Business-hour handling
- Weekend handling
- Holiday handling
- Queue selection
- Escalation audit information
- Conversation state

## Automated Tests

```text
tests/test_sentiment_escalation.py
```

This file contains the Task 5 automated test suite.

## Task 5 Result

```text
task5_result.txt
```

This file contains Task 5 test-result information.

---

# Testing

Automated tests are included throughout the project.

The final complete project test suite was executed successfully.

```text
Ran 229 tests
OK
```

## Final Test Result

```text
229 / 229 tests passing
```

## Task 5 Test Result

```text
28 / 28 tests passing
```

## Task 4 Test Result

```text
22 / 22 tests passing
```

## Task 3 Test Result

```text
15 / 15 tests passing
```

The test suites cover the implemented functionality across the five internship tasks.

---

# Security and Safety

The project incorporates security and safety measures for customer-support workflows.

These include:

- Access-control checks
- Sensitive-data masking
- Prompt-injection protection
- Authorization-aware knowledge retrieval
- Evidence validation
- Protection against unsupported claims
- High-risk issue escalation
- Escalation audit information
- Safe handling of missing information
- Avoidance of fabricated customer/order information
- Validation of uploaded customer evidence

---

# Configuration

The system uses configuration-driven behaviour where applicable.

Configuration can include items such as:

- Business hours
- Holidays
- SLA durations
- Sentiment thresholds
- Escalation thresholds
- Maintenance windows
- Retry intervals
- Knowledge-base update settings

Configuration allows workflow behaviour to be adjusted without changing the core application logic.

---

# Technologies and Concepts

The project demonstrates concepts related to:

- Python
- Generative AI
- Customer-support automation
- Retrieval-Augmented Generation (RAG)
- Knowledge-base management
- Document processing
- Multimodal customer support
- OCR/evidence processing
- Ticket automation
- SLA management
- Sentiment analysis
- Sarcasm detection
- Escalation workflows
- Access control
- Prompt-injection protection
- Sensitive-data masking
- Automated testing
- Configuration-driven workflows
- Git
- GitHub

---

# Development Workflow

The project was developed incrementally according to the internship task sequence.

```text
Task 1
Production Knowledge-Base Pipeline
        │
        ▼
Task 2
Multimodal Customer Support
        │
        ▼
Task 3
Automated Ticket Workflow and SLA Management
        │
        ▼
Task 4
RAG Knowledge Assistant
        │
        ▼
Task 5
Sentiment Analysis and Escalation
```

Each task was implemented and validated with automated tests before moving to the next stage.

---

# Final Status

| Task | Description | Status |
|------|-------------|--------|
| Task 1 | Production Knowledge-Base Pipeline | Completed |
| Task 2 | Multimodal Customer Support | Completed |
| Task 3 | Automated Ticket Workflow and SLA Management | Completed |
| Task 4 | RAG Knowledge Assistant | Completed |
| Task 5 | Sentiment Analysis and Escalation | Completed |

## Final Automated Test Status

```text
229 / 229 tests passing
```

## Overall Project Status

```text
All 5 internship tasks completed.
Full automated test suite passing.
```

---

# Author

Developed as part of an internship project focused on Generative AI and customer-support automation.
