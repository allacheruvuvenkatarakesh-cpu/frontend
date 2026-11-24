from app.services import claims, search, textnorm, translate

TE_SEG = [{"id": 0, "start": 0.0, "end": 6.0, "text": "భారతదేశ జనాభా 140 కోట్లు దాటింది, ఇది ప్రపంచంలోనే అత్యధికం."},
          {"id": 1, "start": 6.0, "end": 9.0, "text": "సబ్‌స్క్రైబ్ చేయండి!"}]
HI_SEG = [{"id": 0, "start": 0.0, "end": 5.0, "text": "ताजमहल का निर्माण 1653 में पूरा हुआ था।"}]


def test_normalize_keeps_indic_letters_and_vowel_signs():
    assert textnorm.normalize("ताजमहल का निर्माण!") == "ताजमहल का निर्माण"
    assert textnorm.normalize("జనాభా, 140 కోట్లు.") == "జనాభా 140 కోట్లు"
    assert textnorm.normalize("Hello,   WORLD!") == "hello world"


def test_quote_matching_works_in_telugu_and_hindi():
    assert claims.quote_matches("భారతదేశ జనాభా 140 కోట్లు దాటింది", TE_SEG[0]["text"])
    assert claims.quote_matches("ताजमहल का निर्माण 1653 में पूरा हुआ", HI_SEG[0]["text"])
    assert not claims.quote_matches("ताजमहल का निर्माण 1999 में शुरू हुआ", HI_SEG[0]["text"], threshold=0.9)


def test_parse_claims_keeps_original_and_english():
    raw = {"claims": [{
        "text": "భారతదేశ జనాభా 140 కోట్లు దాటింది, ఇది ప్రపంచంలోనే అత్యధికం.",
        "text_en": "India's population has crossed 1.4 billion, the highest in the world.",
        "language": "te", "original_quote": "భారతదేశ జనాభా 140 కోట్లు దాటింది",
        "segment_ids": [0], "claim_type": "statistical", "checkworthiness": 0.9}]}
    out = claims.parse_claims(raw, TE_SEG, "te")
    assert len(out) == 1 and out[0]["language"] == "te"
    assert out[0]["text_en"].startswith("India's population") and out[0]["text"].startswith("భారతదేశ")


def test_language_codes():
    assert textnorm.language_code("Telugu") == "te" and textnorm.language_code("hindi") == "hi"
    assert textnorm.language_code("en") == "en" and textnorm.language_code("french") == "other"


def test_queries_include_original_language():
    q = search.build_queries("The Taj Mahal was completed in 1653", "ताजमहल का निर्माण 1653 में पूरा हुआ था")
    assert len(q) == 3 and q[2].startswith("ताजमहल")
    assert len(search.build_queries("Same text", "Same text")) == 2


def test_translation_number_guard():
    assert translate.numbers_preserved("India crossed 1,400 million in 2023", "भारत 2023 में 1400 मिलियन पार")
    assert not translate.numbers_preserved("about 8,849 metres", "लगभग 8,848 मीटर")
