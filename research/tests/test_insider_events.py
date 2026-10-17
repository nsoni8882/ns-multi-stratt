import pandas as pd

from research import insider_events as ie


def tables():
    sub = pd.DataFrame({"ACCESSION_NUMBER": ["a", "b", "c", "d"], "FILING_DATE": ["02-JAN-2020"] * 4,
                        "DOCUMENT_TYPE": ["4", "4", "4/A", "4"], "ISSUERTRADINGSYMBOL": ["AAA", "BBB", "CCC", "BRK.B"]})
    trn = pd.DataFrame({"ACCESSION_NUMBER": ["a", "b", "c", "d"], "TRANS_CODE": ["P", "S", "P", "P"],
                        "TRANS_SHARES": ["1000", "1000", "1000", "10"], "TRANS_PRICEPERSHARE": ["50", "50", "50", "400"],
                        "TRANS_ACQUIRED_DISP_CD": ["A", "D", "A", "A"]})
    own = pd.DataFrame({"ACCESSION_NUMBER": ["a", "b", "c", "d"], "RPTOWNERCIK": ["1", "2", "3", "4"],
                        "RPTOWNER_RELATIONSHIP": ["Officer", "Director", "Director", "10% Owner"]})
    return sub, trn, own


def test_only_officer_or_director_open_market_buys_on_form_4_survive():
    out = ie.buys(*tables())
    assert list(out["ticker"]) == ["AAA"] and out["value"].iloc[0] == 50_000  # sale, 4/A and 10%-owner-only dropped


def test_the_entry_is_the_first_bar_after_the_filing_date_not_the_filing_day():
    idx = pd.date_range("2020-01-01", periods=300, freq="B", tz="UTC")
    close = pd.Series(range(100, 400), index=idx, dtype=float)
    bars = {"AAA": pd.DataFrame({"close": close})}
    member = pd.DataFrame(True, index=idx, columns=["AAA"])
    sig = pd.DataFrame({"ticker": ["AAA"], "filed": [pd.Timestamp("2020-03-02")]})
    tr = ie.score(sig, bars, member, 20)
    assert tr["entry"].iloc[0] == pd.Timestamp("2020-03-03", tz="UTC")
