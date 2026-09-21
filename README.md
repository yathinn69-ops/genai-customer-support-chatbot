# GenAI Customer Support Chatbot

A production-oriented GenAI customer-support chatbot with knowledge-base management, multimodal evidence processing, automated ticket workflows, SLA management, security controls, monitoring, and rollback capabilities.

This project was developed by extending the original training project with the assigned internship tasks.

---

## Project Overview

The system is designed to support a production-style customer-support workflow:

1. Safely process and update the chatbot knowledge base.
2. Analyse customer messages and uploaded evidence such as screenshots, invoices, PDFs, and product images.
3. Convert unresolved conversations into structured support tickets.
4. Calculate ticket priority and manage SLA deadlines.
5. Route tickets to suitable support teams.
6. Detect duplicate and related issues.
7. Protect sensitive customer information.
8. Monitor processing and service health.
9. Maintain versions and support rollback when an update causes problems.

---

# Internship Tasks

## Task 1 — Production Knowledge-Base Pipeline

The knowledge-base pipeline safely manages document updates before they become active.

### Features

- Document fingerprinting and change detection
- Processing of new and modified documents
- Duplicate document detection
- File validation
- Invalid/unsupported file quarantine
- Document version management
- Version rollback
- Quality and grounding checks
- Accuracy and grounding threshold validation
- Configurable update scheduling
- Retry scheduling after failed updates
- Maintenance-window controlled activation
- Health monitoring after activation
- Automatic rollback when health checks fail
- Access control
- Prompt-injection protection
- Sensitive-data masking
- Monitoring of latency, failures, confidence, and escalations
- Audit logging
- Central JSON configuration

### Pipeline Flow

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
           Keep version    Auto Rollback
                               |
                               v
                         Previous Version