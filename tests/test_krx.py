# ----------------------------------------------
# import sys
# sys.path.insert(0, r'G:\내 드라이브\g_dev\FinanceDataReader-dev\FinanceDataReader\src')

import FinanceDataReader as fdr
import pytest
import pandas as pd
import requests


def test_krx_login_api_exposed():
    assert hasattr(fdr, 'krx')
    assert hasattr(fdr.krx, 'login')
    assert hasattr(fdr.krx, 'enable_auto_login_on_failure')
    assert hasattr(fdr.krx, 'auto_login_on_failure_enabled')
    assert fdr.krx.auto_login_on_failure_enabled() is True


def test_krx_session_file_lock_and_write(tmp_path, monkeypatch):
    monkeypatch.setenv("KRX_SESSION_DIR", str(tmp_path))

    session = requests.Session()
    session.cookies.set(
        name="_test_cookie",
        value="1",
        domain="data.krx.co.kr",
        path="/",
    )

    fdr.krx._save_session_to_file(session, mbr_no="1", ttl_minutes=1)

    session_file = tmp_path / "session.json"
    lock_file = tmp_path / "session.json.lock"
    assert session_file.exists()
    assert lock_file.exists()


def test_krx_post_retries_on_logout(monkeypatch):
    import FinanceDataReader.krx as krx

    class _Resp:
        def __init__(self, text: str):
            self.text = text

    calls = {"n": 0}

    def fake_post(url, headers=None, data=None, timeout=30):
        calls["n"] += 1
        if calls["n"] == 1:
            return _Resp("LOGOUT")
        return _Resp('{"output": []}')

    monkeypatch.setattr(krx, "_maybe_auto_login", lambda: None)
    monkeypatch.setattr(krx, "_load_session_from_file", lambda: None)
    monkeypatch.setattr(krx, "clear_session_file", lambda: None)
    monkeypatch.setattr(krx, "set_http_session", lambda session: None)
    monkeypatch.setattr(krx.requests, "post", fake_post)

    resp = krx.krx_post("http://example.com", headers={}, data={})
    assert calls["n"] == 2
    assert resp.text != "LOGOUT"

@pytest.mark.krx
def test_krx_stock_listing():
    # Basic KRX listing
    df = fdr.StockListing('KRX')
    assert len(df) > 2000
    assert 'Code' in df.columns
    assert 'Name' in df.columns

@pytest.mark.krx
def test_krx_delisting_listing():
    # KRX Delisting
    df = fdr.StockListing('KRX-DELISTING')
    assert len(df) > 3000
    assert 'Symbol' in df.columns

@pytest.mark.krx
def test_krx_administrative_listing():
    # KRX Administrative stocks
    df = fdr.StockListing('KRX-ADMINISTRATIVE')
    assert len(df) > 10

@pytest.mark.krx
def test_krx_data_reader_basics():
    # Individual stock
    df = fdr.DataReader('005930', '2023-01-01', '2023-01-31') # Samsung
    assert len(df) > 0
    assert 'Close' in df.columns

@pytest.mark.krx
def test_krx_index_reader():
    # KOSPI Index
    df = fdr.DataReader('KS11', '2023-01-01', '2023-01-31')
    assert len(df) > 0
    
    # KRX-INDEX specific
    df = fdr.DataReader('KRX-INDEX:1001', '2023-01-01', '2023-01-31')
    assert len(df) > 0

@pytest.mark.krx
def test_krx_detail_reader():
    # KRX-DETAIL (KrxDailyDetailReader might require more parameters or specific symbols)
    # Testing for common symbol
    try:
        df = fdr.DataReader('KRX-DETAIL:005930', '2023-01-01', '2023-01-10')
        assert len(df) > 0
    except Exception as e:
        pytest.skip(f"KRX-DETAIL might be unstable or require specific environment: {e}")
