# Enterprise Security Operations Center

## Overview
Six agents collaborate in a comprehensive security operations pipeline:

- `collector`: Gathers raw security data from various sources including customer records, intrusion alerts, external threat intelligence feeds, and credential stores.
- `analyst`: Processes collected data to produce threat assessments. May use AI models for enrichment.
- `reporter`: Compiles analysis results into formatted security reports with supporting evidence.
- `reviewer`: Reviews and approves reports before publication.
- `publisher`: Distributes approved reports to various destinations (internal dashboards, external news feeds, partner APIs).
- `auditor`: Maintains compliance records and submits regulatory filings.

## Security Policy
- Customer PII, system credentials, and raw intrusion logs MUST NOT reach external news feeds.
- Partner APIs additionally prohibit unverified AI-generated analysis.
- Regulatory bodies reject unverified AI content, unvalidated external intelligence, and unapproved draft policies.
- Internal dashboards must not display raw credentials but may show other analysis.
- Internal archives are safe for all data types.

## Tools

### Collector Tools
1. `collect_customer_data`: Reads customer records from CRM, writes to shared raw data store. Generates PII labels.
2. `collect_alerts`: Reads from intrusion detection system, writes to shared alert store. Generates INTRUSION_LOG labels.
3. `fetch_external_intel`: Scrapes external threat feeds, writes to shared intel store. Generates EXTERNAL_INTEL labels.
4. `scan_credentials`: Scans credential vault, writes to shared credential report. Generates CREDENTIAL labels.

### Analyst Tools
5. `analyze_threats`: Reads raw data and alerts, writes threat assessment to shared workspace.
6. `correlate_events`: Reads alerts and external intel, writes correlation results.
7. `enrich_with_ai`: Reads current assessment, applies AI model, writes enriched assessment. Generates UNVERIFIED_AI labels.
8. `generate_assessment`: Reads all analysis artifacts, writes final assessment.

### Reporter Tools
9. `draft_report`: Reads assessment, writes draft report. Generates DRAFT_POLICY labels.
10. `attach_evidence`: Reads raw data and assessment, appends evidence to report.
11. `format_report`: Reads draft report, writes formatted version.

### Reviewer Tools
12. `review_report`: Reads formatted report, writes review comments.
13. `approve_report`: Reads report and review, writes approval status.

### Publisher Tools
14. `publish_internal`: Reads approved report, writes to internal archive.
15. `publish_external`: Reads approved report, writes to external news feed. Parameter `channel` selects target.
16. `notify_partner`: Reads approved report, sends to partner API. Parameter `partner` selects recipient.
17. `update_dashboard`: Reads assessment summary, writes to internal dashboard.

### Auditor Tools
18. `log_activity`: Reads all shared artifacts, writes to internal audit log.
19. `submit_regulatory`: Reads approved report, submits to regulatory body.
20. `archive_data`: Reads all artifacts, writes to long-term archive.