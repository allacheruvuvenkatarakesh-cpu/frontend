from app.services import claims


def test_build_windows_overlap():
    segs = [{"id": i, "start": i, "end": i + 1, "text": "x" * 100} for i in range(50)]
    windows = claims.build_windows(segs, max_chars=1200, overlap=2)
    assert len(windows) > 1
    # consecutive windows share the overlap segments
    assert windows[0][-1]["id"] == windows[1][1]["id"]
    covered = {s["id"] for w in windows for s in w}
    assert covered == set(range(50))


def test_quote_matches_fuzzy():
    src = "Mount Everest is the highest mountain above sea level at about 8,849 metres."
    assert claims.quote_matches("highest mountain above sea level", src)
    assert claims.quote_matches("Mount Everest is the highest mountain above sea-level", src)
    assert not claims.quote_matches("K2 is the deadliest mountain", src)


def test_parse_claims_maps_timestamps_and_drops_hallucinations(sample_segments):
    raw = {"claims": [
        {"text": "Mount Everest is the highest mountain above sea level at about 8,849 metres.",
         "original_quote": "Mount Everest is the highest mountain above sea level", "segment_ids": [3],
         "claim_type": "scientific", "checkworthiness": 0.8},
        {"text": "The Eiffel Tower was built in 1999.", "original_quote": "the Eiffel Tower was built in 1999",
         "segment_ids": [3], "claim_type": "historical", "checkworthiness": 0.9},   # quote not in transcript
        {"text": "Something about segment 99", "original_quote": "", "segment_ids": [99]},  # unknown segment
        {"text": "Water boils at 100 degrees Celsius at sea level.", "original_quote": "Water boils at 100 degrees Celsius",
         "segment_ids": ["S7"], "claim_type": "weird-type", "checkworthiness": "0.7"},
    ]}
    out = claims.parse_claims(raw, sample_segments)
    assert [c["start"] for c in out] == [17.5, 41.0]
    assert out[0]["end"] == 23.9
    assert out[1]["claim_type"] == "other"
    assert out[1]["checkworthiness"] == 0.7


def test_dedupe_and_select():
    base = {"start": 0, "end": 1, "segment_ids": [0], "claim_type": "other", "original_quote": ""}
    items = [
        {**base, "text": "Water boils at 100 degrees Celsius at sea level.", "checkworthiness": 0.6, "start": 5},
        {**base, "text": "Water boils at 100 degrees Celsius at sea level", "checkworthiness": 0.9, "start": 5},
        {**base, "text": "The Great Wall is visible from the Moon.", "checkworthiness": 0.8, "start": 1},
        {**base, "text": "A low-value claim nobody cares about.", "checkworthiness": 0.2, "start": 2},
    ]
    sel = claims.select_claims(items, limit=10)
    assert len(sel) == 2
    assert sel[0]["start"] == 1  # sorted by time
    assert any(c["checkworthiness"] == 0.9 for c in sel)
