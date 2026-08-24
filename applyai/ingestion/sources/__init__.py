"""applyai.ingestion.sources — future job source adapters (V2+).

Each source must declare:
  source_id: str      — machine-readable identifier
  permitted_method: str — how data is accessed (manual_paste | official_api | rss | export)

No source may use headless browsers, CAPTCHA bypass, session injection, or
scraping that violates a platform's Terms of Service.
"""
