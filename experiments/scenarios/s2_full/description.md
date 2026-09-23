# Enterprise DevOps Pipeline

## Overview
Three agents collaborate in a software deployment pipeline:
- `dev_lead`: Writes code changes to a shared repository. Code may contain credentials from external sources.
- `builder`: Reads code from the repository, builds artifacts, and writes them to a shared artifact store.
- `deployer`: Reads built artifacts and deploys them to target environments (staging or production).

## Security Policy
- Credentials (CREDENTIAL) from external sources MUST NOT reach the production environment.
- Staging environment is allowed to receive any data for testing purposes.

## Tools
1. `commit_code` (dev_lead): Writes code to the shared repository. May generate CREDENTIAL if code contains external secrets.
2. `build_artifact` (builder): Reads from shared repository, writes to shared artifact store.
3. `deploy` (deployer): Reads from shared artifact store, deploys to target environment specified by parameter `env` (staging or production).