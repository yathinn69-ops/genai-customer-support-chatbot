# genai-customer-support-chatbot
Production-ready GenAI customer support chatbot with RAG, knowledge-base management, multimodal processing, ticket automation, sentiment analysis, multilingual support, security, monitoring and rollback.
# GenAI Customer Support Chatbot

A production-oriented knowledge-base update and deployment workflow for a GenAI customer-support system.

The project focuses on safely processing knowledge-base documents, validating changes, creating versions, scheduling retries, activating approved updates during maintenance windows, monitoring service health, automatically rolling back failed updates, and recording audit events.

---

## Project Features

- Document fingerprinting and change detection
- New, modified, unchanged, and duplicate document detection
- File validation
- Unsupported/invalid file quarantine
- Document version management
- Quality and grounding threshold checks
- Configurable retry scheduling
- Maintenance-window scheduling
- Controlled activation of approved versions
- Five-minute health-monitoring capability
- Automatic rollback after health-check failure
- End-to-end workflow orchestration
- Audit logging for important workflow events
- Central JSON configuration
- Automated unit tests

---

## Architecture

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
              | Quality / Ground |
              |      Checks       |
              +-------------------+
                       |
                       v
              +-------------------+
              |    Versioning      |
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
           Keep version    Auto Rollback
                               |
                               v
                         Previous Version