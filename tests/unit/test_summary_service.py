from app.services.summary_service import split_sentences, summarize, top_keywords

TEXT = (
    "Workers process queued jobs in the background. "
    "The API places each job on a queue and returns immediately. "
    "Several workers can consume the same queue in parallel. "
    "Reliable workers retry temporary failures with exponential backoff. "
    "A dashboard shows the status of every job for the user. "
    "Completed jobs store a summary and a generated report."
)


def test_top_keyword_is_the_most_frequent_meaningful_word():
    keywords = top_keywords(TEXT, limit=5)
    assert keywords[0] == "workers"
    assert "the" not in keywords  # stopwords are ignored


def test_summary_has_at_most_n_sentences_in_original_order():
    summary = summarize(TEXT, max_sentences=2)
    sentences = split_sentences(summary)
    assert len(sentences) == 2
    assert TEXT.index(sentences[0]) < TEXT.index(sentences[1])


def test_summary_sentences_come_from_the_source():
    for sentence in split_sentences(summarize(TEXT, max_sentences=3)):
        assert sentence in TEXT


def test_empty_text_gives_empty_summary_and_keywords():
    assert summarize("") == ""
    assert top_keywords("") == []