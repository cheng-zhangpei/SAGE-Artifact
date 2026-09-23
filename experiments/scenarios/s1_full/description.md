# Enterprise Support & Ops System

## Overview
This system consists of two agents: `support` and `ops`. They collaborate to handle customer tickets.
- The `support` agent reads customer tickets (which may contain PII) and writes analysis reports to a shared database.
- The `ops` agent reads these shared reports and can send summaries to external channels (Slack or Email) or log them internally.

## Security Policy
- Customer PII is strictly confidential. It may be used internally for analysis but MUST NOT be sent to any external channel (`external.slack` or `external.email`).
- Internal logs are safe for PII.

## Tools
1. `read_ticket`: Reads a ticket from the external CRM. (Generates PII if the ticket contains it).
2. `write_report`: Writes an analysis to the shared report database.
3. `send_slack`: Sends a message to an external Slack channel.
4. `send_email`: Sends an email to an external address.
5. `log_internal`: Writes to the internal audit log.