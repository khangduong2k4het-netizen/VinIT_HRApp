from typing import List, Dict, Any, Tuple, Optional
import re
import math
import unicodedata
from app.core.config import settings
from app.schemas.criteria import CriterionRating, CriteriaCategory


class MatchingEngine:
    """Deterministic scoring and ranking engine - NO LLM CALLS HERE
    All calculations follow approved policy to eliminate hallucination risk.
    """

    SCORE_MAP = {
        CriterionRating.STRONG_MATCH: settings.STRONG_MATCH_SCORE,
        CriterionRating.MATCH: settings.MATCH_SCORE,
        CriterionRating.NO_MATCH: settings.NO_MATCH_SCORE,
        CriterionRating.UNCLEAR: None  # Does not count towards score or coverage
    }
    POLICY_VERSION = settings.MATCHING_POLICY_VERSION
    MIN_EVIDENCE_STRENGTH = 0.35
    _BAND_STRENGTH = {"HIGH": 0.9, "MEDIUM": 0.75, "LOW": 0.5}

    @staticmethod
    def canonicalize_findings(
        criteria: list[dict[str, Any]],
        findings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return exactly one finding per rubric criterion, in rubric order."""
        by_id: dict[str, dict[str, Any]] = {}
        for finding in findings or []:
            if not isinstance(finding, dict):
                continue
            criterion_id = str(finding.get("criterion_id") or "")
            if criterion_id and criterion_id not in by_id:
                by_id[criterion_id] = finding
        canonical = []
        valid_outcomes = {rating.value for rating in CriterionRating}
        for criterion in criteria:
            criterion_id = str(criterion.get("criterion_id") or "")
            finding = dict(by_id.get(criterion_id) or {})
            outcome = str(finding.get("outcome") or CriterionRating.UNCLEAR.value).upper()
            if outcome not in valid_outcomes:
                outcome = CriterionRating.UNCLEAR.value
            evidence = finding.get("evidence") if isinstance(finding.get("evidence"), dict) else {}
            canonical.append({
                **finding,
                "criterion_id": criterion_id,
                "outcome": outcome,
                "reasoning": str(finding.get("reasoning") or ""),
                "evidence": {
                    **evidence,
                    "verbatim_quote": str(evidence.get("verbatim_quote") or ""),
                    "page_number": evidence.get("page_number"),
                    "chunk_id": evidence.get("chunk_id") or evidence.get("evidence_chunk_id"),
                },
                "requires_verification": bool(finding.get("requires_verification")),
            })
        return canonical

    @classmethod
    def _evidence_strength(cls, finding: dict[str, Any]) -> float:
        """Best available evidence strength without a hard confidence cliff."""
        if "evidence_strength" in finding:
            try:
                strength = float(finding.get("evidence_strength"))
                if math.isfinite(strength):
                    return min(1.0, max(0.0, strength))
            except (TypeError, ValueError):
                pass
            return 0.0
        if "confidence" in finding:
            try:
                confidence = float(finding.get("confidence"))
                if math.isfinite(confidence) and 0 <= confidence <= 1:
                    return confidence
            except (TypeError, ValueError):
                pass
            return 0.0
        band = str(finding.get("confidence_band") or "").strip().upper()
        return cls._BAND_STRENGTH.get(band, 0.0)

    def calculate_criterion_weight(
        self,
        criterion: Dict[str, Any],
        all_criteria: List[Dict[str, Any]],
        group_weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """Calculate effective weight for a criterion: group_total_weight * relative_weight_in_group"""
        group_weight = (group_weights.get(criterion["category"], 0.0) if group_weights is not None else (
            settings.MANDATORY_CRITERIA_WEIGHT_DEFAULT
            if criterion["category"] == CriteriaCategory.MUST_HAVE.value
            else settings.NICE_TO_HAVE_WEIGHT_DEFAULT
        ))
        # Sum of weight_in_group in this category
        group_total = sum(float(c["weight_in_group"]) for c in all_criteria if c["category"] == criterion["category"])
        if group_total == 0:
            return 0
        relative = float(criterion["weight_in_group"]) / group_total
        return group_weight * relative

    def calculate_assessment_scores(
        self,
        criteria: List[Dict[str, Any]],
        findings: List[Dict[str, Any]],
        group_weights: Optional[Dict[str, float]] = None,
    ) -> Tuple[Optional[float], float, str, List[Dict[str, Any]], bool]:
        """
        Calculate matching score, evidence coverage, and matching status.
        Returns: (score, coverage, matching_status, augmented_findings, needs_verification)
        """
        total_applicable_weight = 0.0
        total_scored_weight = 0.0
        weighted_score_sum = 0.0
        has_mandatory_mismatch = False
        needs_verification = False
        augmented_findings = []

        findings = self.canonicalize_findings(criteria, findings)

        for crit in criteria:
            crit_id = str(crit["criterion_id"])
            effective_weight = self.calculate_criterion_weight(crit, criteria, group_weights)
            total_applicable_weight += effective_weight

            finding = next(item for item in findings if item["criterion_id"] == crit_id)
            outcome = finding["outcome"]
            evidence_strength = self._evidence_strength(finding)
            confidence = evidence_strength
            confidence_band = str(finding.get("confidence_band") or "LOW").strip().upper()
            if confidence_band not in {"HIGH", "MEDIUM", "LOW"}:
                confidence_band = "LOW"

            # No hard 0.6/band cliff: a non-UNCLEAR outcome is scored once it
            # has a minimum evidence strength. An explicit review request or
            # very weak evidence remains UNCLEAR for scoring.
            is_scored = (
                outcome != CriterionRating.UNCLEAR.value
                and evidence_strength >= self.MIN_EVIDENCE_STRENGTH
                and not finding.get("requires_verification")
            )
            if not is_scored:
                outcome = CriterionRating.UNCLEAR.value

            point_value = None
            if is_scored:
                raw_score = finding.get("score")
                try:
                    point_value = float(raw_score) if raw_score is not None else None
                    if point_value is not None and not math.isfinite(point_value):
                        point_value = None
                except (TypeError, ValueError):
                    point_value = None
                if point_value is None:
                    point_value = self.SCORE_MAP.get(CriterionRating(outcome), None)
                if point_value is not None:
                    point_value = min(100.0, max(0.0, point_value))
                    if outcome == CriterionRating.NO_MATCH.value:
                        point_value = 0.0
                    weighted_score_sum += (point_value / 100) * effective_weight
                    total_scored_weight += effective_weight
                    if outcome == CriterionRating.NO_MATCH.value and crit["category"] == CriteriaCategory.MUST_HAVE.value:
                        has_mandatory_mismatch = True
            elif crit["category"] == CriteriaCategory.MUST_HAVE.value:
                needs_verification = True

            aug_finding = {**finding, "criterion_id": crit_id, "outcome": outcome,
                           "confidence": confidence, "confidence_band": confidence_band,
                           "evidence_strength": evidence_strength,
                           "score": point_value if is_scored else None,
                           "requires_verification": bool(finding.get("requires_verification")) or not is_scored,
                           "effective_weight": effective_weight}
            augmented_findings.append(aug_finding)

        # Calculate final scores. UNCLEAR means "not enough evidence to
        # judge", not zero attainment: it is excluded from both the score
        # numerator and denominator. Evidence coverage separately reports
        # how much of the applicable rubric was scored, and the mandatory
        # status/coverage gates keep low-coverage cases out of the normal
        # MEETS_MANDATORY review tier.
        if total_scored_weight == 0:
            matching_score = None
        else:
            matching_score = round((weighted_score_sum / total_scored_weight) * 100, 1)

        # The DB stores two decimal places. Round down conservatively before
        # applying the threshold so 69.9% cannot be stored as 70% and ranked.
        evidence_coverage = (min(1.0, math.floor((total_scored_weight / total_applicable_weight + 1e-12) * 100) / 100)
                             if total_applicable_weight > 0 else 0)

        # Check coverage threshold
        if evidence_coverage < settings.MIN_EVIDENCE_COVERAGE:
            needs_verification = True

        # Determine matching status
        if not criteria or total_applicable_weight == 0:
            matching_status = "NOT_ASSESSED"
        elif has_mandatory_mismatch and not needs_verification:
            matching_status = "POSSIBLE_MISMATCH"
        elif needs_verification:
            matching_status = "NEEDS_HR_VERIFICATION"
        else:
            matching_status = "MEETS_MANDATORY"

        return matching_score, evidence_coverage, matching_status, augmented_findings, needs_verification

    @staticmethod
    def _normalized_with_map(value: str) -> tuple[str, list[int]]:
        chars: list[str] = []
        origins: list[int] = []
        for index, char in enumerate(value or ""):
            decomposed = unicodedata.normalize("NFKD", char)
            base = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
            for normalized_char in base:
                if normalized_char.isalnum():
                    chars.append(normalized_char)
                    origins.append(index)
                elif chars and chars[-1] != " ":
                    chars.append(" ")
                    origins.append(index)
        while chars and chars[-1] == " ":
            chars.pop()
            origins.pop()
        return "".join(chars), origins

    def find_quote_span(
        self,
        quote: str,
        cv_full_text: str,
        *,
        preferred_page: int | None = None,
        preferred_start: int | None = None,
        preferred_end: int | None = None,
    ) -> tuple[int, int] | None:
        """Locate a quote tolerant to case, accents, punctuation and spacing.

        Returns original character offsets so callers can persist the exact
        CV substring instead of trusting the model's transcription.  When a
        quote repeats, a caller-supplied page or chunk range selects the
        intended occurrence instead of always taking the first one.
        """
        if not quote or len(quote.strip()) < 10 or not cv_full_text:
            return None
        needle, _ = self._normalized_with_map(quote)
        if len(needle) < 8:
            return None
        haystack, origins = self._normalized_with_map(cv_full_text)
        occurrences: list[tuple[int, int]] = []
        cursor = 0
        while True:
            index = haystack.find(needle, cursor)
            if index < 0:
                break
            occurrences.append((origins[index], origins[index + len(needle) - 1] + 1))
            cursor = index + 1
        if not occurrences:
            return None
        if preferred_start is not None:
            range_end = preferred_end if preferred_end is not None else preferred_start
            for occurrence in occurrences:
                if occurrence[0] < range_end and occurrence[1] > preferred_start:
                    return occurrence
            return min(
                occurrences,
                key=lambda item: abs(item[0] - preferred_start),
            )
        if preferred_page is not None:
            for occurrence in occurrences:
                if self._page_for_span(occurrence, cv_full_text) == preferred_page:
                    return occurrence
        return occurrences[0]

    @staticmethod
    def _page_for_span(span: tuple[int, int], cv_full_text: str) -> int | None:
        page = None
        for marker in re.finditer(r"--- Page (\d+) ---", cv_full_text):
            if marker.start() > span[0]:
                break
            page = int(marker.group(1))
        return page

    def verify_verbatim_quote(self, quote: str, cv_full_text: str) -> bool:
        """Verify a quote by locating its normalized span in the CV text."""
        return self.find_quote_span(quote, cv_full_text) is not None

    def quote_pages(
        self,
        quote: str,
        cv_full_text: str,
        span: tuple[int, int] | None = None,
    ) -> list[int]:
        """Return the actual PDF page containing the located quote span."""
        located = span or self.find_quote_span(quote, cv_full_text)
        if located is None:
            return []
        page = self._page_for_span(located, cv_full_text)
        return [page] if page is not None else []

    def rank_applications(
        self,
        applications_with_assessments: List[Dict[str, Any]],
        criteria: List[Dict[str, Any]],
        *,
        ltr_scores: Dict[str, float] | None = None,
        ltr_mode: str = "OFF",
    ) -> List[Dict[str, Any]]:
        """
        Rank applications within same position per policy:
        Priority 1: Match mandatory criteria (MEETS_MANDATORY > NEEDS_VERIFICATION > POSSIBLE_MISMATCH)
        Priority 2: Matching score (descending)
        Priority 3: Evidence coverage (descending)

        LTR may only reorder inside Priority 1 (and inside the coverage
        eligibility gate) in ACTIVE mode.  SHADOW records scores without
        changing the published order.
        """
        status_order = {
            "MEETS_MANDATORY": 0,
            "NEEDS_HR_VERIFICATION": 1,
            "POSSIBLE_MISMATCH": 2,
            "NOT_ASSESSED": 3
        }
        mode = (ltr_mode or "OFF").upper()
        scores = ltr_scores or {}

        def application_id(item: Dict[str, Any]) -> str:
            return str(item.get("application_id") or item.get("id") or "")

        def sort_key(item):
            assess = item.get("latest_assessment", {})
            status = assess.get("matching_status", "NOT_ASSESSED")
            score = assess.get("matching_score")
            score = score if score is not None else -1
            coverage = assess.get("evidence_coverage") or 0
            eligible = coverage >= settings.MIN_EVIDENCE_COVERAGE and status != "NOT_ASSESSED"
            ltr_score = scores.get(application_id(item))
            if mode == "ACTIVE":
                return (
                    status_order.get(status, 99),
                    0 if eligible else 1,
                    -float(ltr_score) if ltr_score is not None else float("inf"),
                    -score,
                    -coverage,
                    application_id(item),
                )
            return (
                status_order.get(status, 99),
                -score,  # Negative for descending sort
                -coverage,
                application_id(item),
            )

        sorted_items = sorted(applications_with_assessments, key=sort_key)

        # Assign rank numbers only to applications with enough evidence
        result = []
        current_rank = 1
        for item in sorted_items:
            assess = item.get("latest_assessment", {})
            coverage = assess.get("evidence_coverage") or 0
            status = assess.get("matching_status", "NOT_ASSESSED")

            rank_num = current_rank if (
                coverage >= settings.MIN_EVIDENCE_COVERAGE
                and status != "NOT_ASSESSED"
            ) else None

            result.append({
                **item,
                "rank_number": rank_num,
                "ltr_score": scores.get(application_id(item)),
                "has_mismatch": status == "POSSIBLE_MISMATCH",
                "needs_verification": status == "NEEDS_HR_VERIFICATION" or coverage < settings.MIN_EVIDENCE_COVERAGE
            })

            if rank_num is not None:
                current_rank += 1

        return result

    def detect_duplicates(
        self,
        applications: List[Dict[str, Any]]
    ) -> List[Tuple[str, str, float, str]]:
        """
        Detect potential duplicate applications within same position.
        Returns list of (app_id_1, app_id_2, confidence, signal_type)
        """
        duplicates = []

        for i, app1 in enumerate(applications):
            identity1 = app1.get("identity", {})
            email1 = (identity1.get("email") or "").lower().strip()
            phone1 = (identity1.get("phone") or "").strip()

            for j in range(i + 1, len(applications)):
                app2 = applications[j]
                identity2 = app2.get("identity", {})
                email2 = (identity2.get("email") or "").lower().strip()
                phone2 = (identity2.get("phone") or "").strip()

                # Exact email match
                if email1 and email1 == email2:
                    duplicates.append((
                        app1["application_id"],
                        app2["application_id"],
                        0.98,
                        "EMAIL_MATCH"
                    ))
                    continue

                # Exact phone match
                if phone1 and phone1 == phone2:
                    duplicates.append((
                        app1["application_id"],
                        app2["application_id"],
                        0.95,
                        "PHONE_MATCH"
                    ))
                    continue

                # Fuzzy name match + content similarity would go here in production
                # For MVP MVP we only use hard contact signals

        return duplicates


# Singleton instance
matching_engine = MatchingEngine()
