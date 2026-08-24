"""applyai.processing — deterministic processing modules (zero LLM usage).

All modules in this package use pure Python only:
  deduplicator.py    — SHA-256 content hashing + DB lookup
  url_normalizer.py  — urllib.parse normalization
  date_parser.py     — dateutil-based parsing
  salary_extractor.py — regex-based salary extraction
  scorer.py          — weighted score aggregation from config

Phase 2 scope.
"""
