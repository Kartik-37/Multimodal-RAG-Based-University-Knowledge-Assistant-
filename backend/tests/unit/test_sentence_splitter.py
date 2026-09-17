"""
Unit Tests for Deterministic SentenceSplitter.
"""

from backend.app.services.grounding.sentence_splitter import SentenceSplitter


def test_sentence_splitter_basic_splitting() -> None:
    splitter = SentenceSplitter()
    text = (
        "First-Come First-Served is a CPU scheduling algorithm. [source_1] "
        "It executes processes strictly in arrival order. [source_1] "
        "Waiting time can be relatively high. [source_2]"
    )
    claims = splitter.split(text)

    assert len(claims) == 3
    assert claims[0].claim_index == 1
    assert "First-Come First-Served is a CPU scheduling algorithm." in claims[0].text
    assert claims[0].cited_source_ids == ["source_1"]
    assert claims[0].is_conversational is False

    assert claims[1].claim_index == 2
    assert "It executes processes strictly in arrival order." in claims[1].text
    assert claims[1].cited_source_ids == ["source_1"]

    assert claims[2].claim_index == 3
    assert "Waiting time can be relatively high." in claims[2].text
    assert claims[2].cited_source_ids == ["source_2"]


def test_sentence_splitter_protects_abbreviations() -> None:
    splitter = SentenceSplitter()
    text = (
        "Operating systems use scheduling algorithms, e.g. FCFS and SJF. [source_1] "
        "Dr. Smith proposed an extension vs. the standard approach. [source_2]"
    )
    claims = splitter.split(text)

    # Neither e.g. nor Dr. nor vs. should cause a sentence break
    assert len(claims) == 2
    assert "e.g." in claims[0].text
    assert "Dr." in claims[1].text
    assert "vs." in claims[1].text


def test_sentence_splitter_protects_decimals_and_versions() -> None:
    splitter = SentenceSplitter()
    text = "The time quantum is 3.14 ms. [source_1] The release version is v1.2.3. [source_2]"
    claims = splitter.split(text)

    assert len(claims) == 2
    assert "3.14" in claims[0].text
    assert "v1.2.3" in claims[1].text


def test_sentence_splitter_handles_markdown_lists() -> None:
    splitter = SentenceSplitter()
    text = (
        "Here are the scheduling properties:\n"
        "1. FCFS is non-preemptive. [source_1]\n"
        "2. Round Robin uses time slicing. [source_2]\n"
        "- SJF minimizes average waiting time. [source_3]"
    )
    claims = splitter.split(text)

    assert len(claims) == 4
    # The preamble is conversational
    assert claims[0].is_conversational is True
    # The list items have list markers stripped
    assert claims[1].text == "FCFS is non-preemptive."
    assert claims[1].cited_source_ids == ["source_1"]
    assert claims[2].text == "Round Robin uses time slicing."
    assert claims[3].text == "SJF minimizes average waiting time."


def test_sentence_splitter_classifies_conversational_preamble_and_refusals() -> None:
    splitter = SentenceSplitter()

    text1 = "Based on the provided documents, FCFS is non-preemptive. [source_1]"
    claims1 = splitter.split(text1)
    assert len(claims1) == 1
    assert claims1[0].is_conversational is True

    text2 = "I could not find any relevant information in the available documents to answer your question."
    claims2 = splitter.split(text2)
    assert len(claims2) == 1
    assert claims2[0].is_conversational is True


def test_sentence_splitter_bounds_enforcement() -> None:
    splitter = SentenceSplitter(max_claims=2)
    text = "Sentence one. Sentence two. Sentence three. Sentence four."
    claims = splitter.split(text)

    assert len(claims) == 2
    assert claims[0].claim_index == 1
    assert claims[1].claim_index == 2


def test_sentence_splitter_empty_and_whitespace_input() -> None:
    splitter = SentenceSplitter()
    assert splitter.split("") == []
    assert splitter.split("   \n\t  ") == []
