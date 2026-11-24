from app.services import context

SEGS = [
    {"id": 0, "start": 0, "end": 4, "text": "Some people online say vaccines are useless."},
    {"id": 1, "start": 4, "end": 9, "text": "Crime fell by 40 percent last year."},
    {"id": 2, "start": 9, "end": 14, "text": "But that was only in one district, and it rose everywhere else."},
    {"id": 3, "start": 14, "end": 18, "text": "Thanks for watching."},
]


def test_window_bounds():
    w = context.surrounding_window(SEGS, [1], size=1)
    assert [s["id"] for s in w] == [0, 1, 2]
    assert context.surrounding_window(SEGS, []) == []


def test_ground_flags_requires_verbatim_transcript_quote():
    raw = {"flags": [
        {"type": "out_of_context", "explanation": "The next sentence limits it to one district.",
         "transcript_quote": "only in one district, and it rose everywhere else", "segment_id": 2},
        {"type": "selective_quote", "explanation": "Invented.", "transcript_quote": "crime doubled nationally", "segment_id": 2},
        {"type": "misleading_statistic", "explanation": "40% of a small base.", "transcript_quote": "", "segment_id": None},
        {"type": "made_up_type", "explanation": "x"},
        {"type": "out_of_context", "explanation": "duplicate", "transcript_quote": "only in one district", "segment_id": 2},
    ]}
    flags = context.ground_flags(raw, SEGS[:3])
    assert [f["type"] for f in flags] == ["out_of_context", "misleading_statistic"]
    assert flags[0]["start"] == 9 and flags[0]["label"] == "Taken out of context"


def test_risk_levels():
    oc = [{"type": "out_of_context"}]
    assert context.risk_level([], "false") == "none"
    assert context.risk_level(oc, "verified") == "medium"
    assert context.risk_level(oc, "misleading") == "high"
    assert context.risk_level([{"type": "missing_information"}], "verified") == "low"
    assert context.risk_level([{"type": "missing_information"}, {"type": "incomplete_claim"}], None) == "high"


def test_parse_contradictions_validates_codes():
    claims = [{"_id": "c1", "code": "CLM001", "start": 4}, {"_id": "c2", "code": "CLM002", "start": 30}]
    raw = {"contradictions": [
        {"a": "CLM001", "b": "CLM002", "explanation": "Different numbers for the same thing."},
        {"a": "clm002", "b": "CLM001", "explanation": "duplicate pair"},
        {"a": "CLM001", "b": "CLM009", "explanation": "unknown code"},
        {"a": "CLM001", "b": "CLM001", "explanation": "self"},
    ]}
    out = context.parse_contradictions(raw, claims)
    assert len(out) == 1 and out[0]["claim_b_id"] == "c2" and out[0]["start_b"] == 30
