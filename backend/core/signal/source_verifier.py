"""
Dual-source confirmation for Resolution Timing strategy.
No LLM in MVP — uses structured regex + market metadata analysis.

Audit hard rule: ANY textual ambiguity → confirmed = False.
"""
import logging
import re
from dataclasses import dataclass
from datetime import datetime

from core.data.normalization import Market

logger = logging.getLogger(__name__)

# Category-A markets: machine-verifiable, lowest oracle risk
CATEGORY_A_PATTERNS = [
    r"(?i)will .+ (win|lose|score|defeat)",
    r"(?i)final score",
    r"(?i)will the fed (raise|cut|hold)",
    r"(?i)unemployment rate",
    r"(?i)cpi|inflation rate",
    r"(?i)gdp (growth|shrink)",
    r"(?i)election (result|winner|called)",
]

# Red flags: ambiguous resolution criteria → always False
AMBIGUITY_PATTERNS = [
    r"(?i)at (any|some) point",
    r"(?i)generally",
    r"(?i)substantially",
    r"(?i)significant(ly)?",
    r"(?i)approximately",
    r"(?i)could be interpreted",
    r"(?i)depending on",
    r"(?i)or (similar|equivalent)",
]


@dataclass
class VerificationResult:
    confirmed: bool
    confidence: float  # 0.0–1.0
    category: str  # "A" for category-A, "B" for other
    sources: list[str]
    reason: str


class SourceVerifier:
    """
    Verifies resolution opportunity via structured analysis of market metadata.

    In MVP: uses regex parsing of resolution criteria + timing heuristics.
    Future: add LLM dual-parser when calibration database is established.
    """

    def verify(self, market: Market, side: str) -> VerificationResult:
        criteria = market.resolution_criteria or ""
        question = market.question or ""
        combined = f"{question} {criteria}"

        # Check for hard ambiguity red flags first
        for pattern in AMBIGUITY_PATTERNS:
            if re.search(pattern, combined):
                return VerificationResult(
                    confirmed=False,
                    confidence=0.0,
                    category="B",
                    sources=[],
                    reason=f"Ambiguous resolution criteria: matched pattern '{pattern}'",
                )

        # Check if market has actually passed its end date
        now = datetime.utcnow()
        if market.end_date > now:
            # Market not yet ended — cannot confirm resolution
            return VerificationResult(
                confirmed=False,
                confidence=0.0,
                category="B",
                sources=[],
                reason=f"Market end date {market.end_date.isoformat()} is in the future",
            )

        # Check for Category-A market type (lowest oracle risk)
        is_category_a = any(re.search(p, combined) for p in CATEGORY_A_PATTERNS)
        category = "A" if is_category_a else "B"

        # Confidence scoring
        hours_past_end = (now - market.end_date).total_seconds() / 3600

        if is_category_a and hours_past_end >= 1.0:
            base_confidence = min(0.92, 0.82 + (hours_past_end / 24.0) * 0.10)
            sources = ["market_end_date_passed", "category_a_criteria"]
        elif hours_past_end >= 2.0:
            base_confidence = min(0.78, 0.62 + (hours_past_end / 24.0) * 0.12)
            sources = ["market_end_date_passed"]
        else:
            return VerificationResult(
                confirmed=False,
                confidence=0.3,
                category=category,
                sources=[],
                reason=f"Only {hours_past_end:.1f}h past end date — insufficient confirmation time",
            )

        # Weight confidence by market-implied probability of this side winning.
        # A NO token at 92¢ → market is 92% confident NO wins → high confidence.
        # A YES token at 7¢  → market is  7% confident YES wins → low confidence.
        # This replaces the flat 0.75 score that was the same for both.
        market_implied_prob = float(market.best_ask) if side == "YES" else (1.0 - float(market.best_ask))
        market_implied_prob = max(0.01, min(0.99, market_implied_prob))

        # Blend: 40% time-based evidence, 60% market consensus
        confidence = 0.4 * base_confidence + 0.6 * market_implied_prob

        if confidence < 0.65:
            return VerificationResult(
                confirmed=False,
                confidence=confidence,
                category=category,
                sources=sources,
                reason=f"Blended confidence {confidence:.2f} below 0.65 (base={base_confidence:.2f}, market={market_implied_prob:.0%})",
            )

        return VerificationResult(
            confirmed=True,
            confidence=confidence,
            category=category,
            sources=sources,
            reason=f"Confirmed: {hours_past_end:.1f}h past end, market={market_implied_prob:.0%}, conf={confidence:.2f}",
        )
