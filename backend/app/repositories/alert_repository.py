"""
RetailFlow AI — Alert Repository

Data access layer for AlertConfig records.
Extracted into its own file for separation of concerns:
  - queue_repository.py  → QueueSnapshot (write-heavy, append-only)
  - alert_repository.py  → AlertConfig (read-heavy, low frequency writes)
"""

from app.repositories.queue_repository import AlertRepository

# Re-export from queue_repository for backward compatibility
__all__ = ["AlertRepository"]
