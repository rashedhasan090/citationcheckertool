from citeguard.models import Candidate, Citation
from citeguard.parsers import clean_doi, parse_citations
from citeguard.scoring import metadata_score


def test_doi_clean():
    assert clean_doi("https://doi.org/10.1038/s41586-020-2649-2.") == "10.1038/s41586-020-2649-2"


def test_bibtex_parse():
    cs=parse_citations('@article{x, title={Attention Is All You Need}, author={Vaswani, Ashish and Shazeer, Noam}, year={2017}, doi={10.48550/arXiv.1706.03762}}')
    assert len(cs)==1 and cs[0].year==2017 and "Attention" in cs[0].title


def test_exact_metadata_scores_high():
    c=Citation(raw="",title="Attention Is All You Need",authors=["Ashish Vaswani"],year=2017,doi="10.1/x")
    k=Candidate(source="x",title="Attention Is All You Need",authors=["Ashish Vaswani"],year=2017,doi="10.1/x")
    score,_=metadata_score(c,k)
    assert score>0.95
