# Data Pipeline with Conditional Processing

## Overview
Three agents manage a data processing pipeline:
- `ingestor`: Ingests data from various sources into the staging area.
- `processor`: Processes staged data using different modes.
- `exporter`: Exports processed data to external partners or internal storage.

## Security Policy
- Sensitive data and unverified external data MUST NOT reach the partner API.
- Internal warehouse is safe for all data.

## Tools
1. `ingest` (ingestor): Ingests data from the source specified by `source` parameter into staging.
2. `process` (processor): Processes staged data. The `mode` parameter determines processing behavior.
3. `export` (exporter): Exports processed data to the destination specified by `dest` parameter.