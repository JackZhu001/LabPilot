import os

import pytest

from labpilot.literature.arxiv import ArxivProvider
from labpilot.literature.semantic_scholar import SemanticScholarProvider


@pytest.mark.live_literature
def test_live_arxiv_search_normalizes_metadata() -> None:
    papers = ArxivProvider().search("dropout neural network regularization", 1)
    assert len(papers) <= 1
    if papers:
        assert papers[0].provider == "arxiv"
        assert papers[0].title


@pytest.mark.live_literature
@pytest.mark.skipif(not os.getenv("SEMANTIC_SCHOLAR_API_KEY"), reason="API key not configured")
def test_live_semantic_scholar_search_normalizes_metadata() -> None:
    papers = SemanticScholarProvider().search("dropout neural network regularization", 1)
    assert len(papers) <= 1
    if papers:
        assert papers[0].provider == "semantic_scholar"
        assert papers[0].title
