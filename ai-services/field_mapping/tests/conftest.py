import os
import sys
from pathlib import Path

# The existing codebase (mapping.py, ingestion/, field_mapping/, ...) uses
# top-level imports like `from mapping import ...`, assuming ai-services/
# itself is on sys.path -- exactly like `uvicorn app:app` run from that
# directory. Make pytest behave the same way regardless of where it's
# invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Deterministic, offline embeddings for the whole test session -- no
# network access or downloaded model required, and results don't drift
# with whatever sentence-transformers model happens to be cached locally.
os.environ.setdefault("ONERECON_FORCE_HASH_EMBEDDER", "1")
