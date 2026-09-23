# Frozen 72-workflow guard-authoring study

The suite contains 36 base workflows and 36 nested composition workflows.

| Layer / arm | PASS | FAIL | UNKNOWN | DER | BBR |
|---|---:|---:|---:|---:|---:|
| base: MiMo one-shot | 35/36 | 1/36 | 0/36 | 97.2% | 0.0% |
| base: SAGE additive | 36/36 | 0/36 | 0/36 | 100.0% | 0.0% |
| base: DirectSAGE | 36/36 | 0/36 | 0/36 | 100.0% | 0.0% |
| composition: MiMo one-shot | 24/36 | 9/36 | 3/36 | 94.7% | 2.9% |
| composition: SAGE additive | 36/36 | 0/36 | 0/36 | 100.0% | 2.9% |
| composition: DirectSAGE | 36/36 | 0/36 | 0/36 | 100.0% | 0.0% |
| all: MiMo one-shot | 59/72 | 10/72 | 3/72 | 94.8% | 2.8% |
| all: SAGE additive | 72/72 | 0/72 | 0/72 | 100.0% | 2.8% |
| all: DirectSAGE | 72/72 | 0/72 | 0/72 | 100.0% | 0.0% |

Composition levels within a business family are nested and correlated.
