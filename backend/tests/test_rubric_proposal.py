"""Proposal validation uses synthetic data only, not HR or candidate records."""
import json
from pathlib import Path

from app.api.rubric_library import Draft
from app.services.deterministic_matching import deterministic_matcher

ROOT = Path(__file__).resolve().parents[2]
PROPOSAL = ROOT / 'frontend/src/data/rubric-proposal-it-backend.json'


def load_proposal():
    return json.loads(PROPOSAL.read_text(encoding='utf-8'))


def test_proposal_has_valid_draft_and_group_weights():
    data = load_proposal()
    draft = Draft.model_validate(data)
    assert data['job_family_code'] == 'IT_DIGITAL'
    assert draft.mandatory_weight_total == 70 and draft.nice_to_have_weight_total == 30
    assert len(draft.items) == 5
    for category in ('MUST_HAVE', 'NICE_TO_HAVE'):
        assert sum(item.weight_in_group for item in draft.items if item.category == category) == 100
    python = draft.items[0]
    assert python.requirement_spec.kind == 'SKILL'
    assert python.requirement_spec.terms == ['Python'] and python.requirement_spec.min_years == 4
    framework = deterministic_matcher.build_requirement_spec({'criterion_id': 'framework', **draft.items[1].model_dump()})
    assert len(framework.terms) == 1 and framework.terms[0].label == 'python framework'


def test_proposal_python_partial_backend_keeps_unclear():
    item = dict(load_proposal()['items'][0], criterion_id='python')
    fixture = (ROOT / 'staging/synthetic/candidates/partial_backend.txt').read_text(encoding='utf-8')
    result = deterministic_matcher.evaluate_criteria(fixture, [item], {})
    # No rule match/negative conclusion: caller must use the existing UNCLEAR
    # fallback and HR verification, not a silently lowered threshold.
    assert result['findings'] == []
    assert result['unresolved_criterion_ids'] == ['python']


def test_proposal_frameworks_are_alternatives():
    item = dict(load_proposal()['items'][1], criterion_id='framework')
    for name in ('FastAPI', 'Django', 'Flask'):
        text = f'WORK EXPERIENCE\nBuilt Python backend APIs using {name} for internal services.'
        result = deterministic_matcher.evaluate_criteria(text, [item], {})
        assert result['findings'] and result['findings'][0]['outcome'] in ('MATCH', 'STRONG_MATCH'), name
