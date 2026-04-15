"""
Calibration tracking: logs predicted vs actual outcomes, computes Brier score.
Brier score = (predicted_prob - actual_outcome)^2, lower is better.
"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class CalibrationTracker:
    def __init__(self):
        self._log: list[dict] = []  # in-memory; flushed to DB by monitoring node

    def log_prediction(
        self,
        market_id: str,
        question: str,
        predicted_prob: float,
        strategy: str = "resolution_timing",
    ) -> dict:
        entry = {
            "market_id": market_id,
            "question": question,
            "predicted_prob": predicted_prob,
            "strategy": strategy,
            "actual_outcome": None,
            "brier_score": None,
            "created_at": datetime.utcnow().isoformat(),
            "resolved_at": None,
        }
        self._log.append(entry)
        return entry

    def record_outcome(self, market_id: str, actual_outcome: float):
        """Record actual outcome (0.0 = NO, 1.0 = YES) and compute Brier score."""
        for entry in self._log:
            if entry["market_id"] == market_id and entry["actual_outcome"] is None:
                entry["actual_outcome"] = actual_outcome
                entry["brier_score"] = (entry["predicted_prob"] - actual_outcome) ** 2
                entry["resolved_at"] = datetime.utcnow().isoformat()
                logger.info(
                    f"Calibration: market={market_id} "
                    f"predicted={entry['predicted_prob']:.3f} "
                    f"actual={actual_outcome} "
                    f"brier={entry['brier_score']:.4f}"
                )

    @property
    def mean_brier_score(self) -> Optional[float]:
        resolved = [e for e in self._log if e["brier_score"] is not None]
        if not resolved:
            return None
        return sum(e["brier_score"] for e in resolved) / len(resolved)

    def drain(self) -> list[dict]:
        """Return and clear pending log entries for DB persistence."""
        entries = list(self._log)
        self._log.clear()
        return entries
