# ----------------------------------------------
import sys
sys.path.insert(0, r'D:dev\FinanceDataReader-dev\FinanceDataReader\src')

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


def test_krx_session_file_serializes_curl_cffi_cookies(tmp_path, monkeypatch):
    curl_cffi = pytest.importorskip("curl_cffi")
    monkeypatch.setenv("KRX_SESSION_DIR", str(tmp_path))

    session = curl_cffi.requests.Session()
    session.cookies.set(
        name="_test_cookie",
        value="1",
        domain="data.krx.co.kr",
        path="/",
    )

    serialized = fdr.krx._serialize_session_cookies(session)
    assert serialized["_test_cookie"]["value"] == "1"

    fdr.krx._save_session_to_file(session, mbr_no="1", ttl_minutes=1)

    loaded = fdr.krx._load_session_from_file()
    assert loaded is not None
    assert loaded.cookies.get_dict().get("_test_cookie") == "1"


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
    monkeypatch.setattr(krx, "get_http_session", lambda: None)
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
    assert len(df) > 200
    assert 'Code' in df.columns
    assert 'Name' in df.columns

@pytest.mark.krx
def test_krx_stock_listing_kosdaq():
    # Basic KOSDAQ listing
    df = fdr.StockListing('KOSDAQ')
    assert len(df) > 100
    assert 'Code' in df.columns
    assert 'Name' in df.columns    

@pytest.mark.krx
def test_krx_delisting_listing():
    # KRX Delisting
    df = fdr.StockListing('KRX-DELISTING')
    assert len(df) > 900
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
def test_ks11():
    # KOSPI Index
    df = fdr.DataReader('KS11', '2023-01-01', '2023-01-31')
    assert len(df) > 0
    
def test_krx_index_reader():
    # KRX-INDEX specific
    df = fdr.DataReader('KRX-INDEX:1001', '2023-01-01', '2023-01-31')
    assert len(df) > 0

@pytest.mark.krx
def test_krx_detail_reader():
    df = fdr.DataReader('KRX-DETAIL:005930', '2023-01-01', '2023-01-10')
    assert len(df) > 0

@pytest.mark.krx
def test_krx_stock_data_reader():
    stock_code = ['0004Y0', '0007C0', '0008Z0', '0009K0', '0010V0', '0013V0', '0015G0', '0015N0', '0015S0', '0030R0', '0037T0', '0041B0', '0041J0', '0041L0', '0044K0', '0054V0', '0068Y0', '0071M0', '0072Z0', '0088D0', '0091W0', '0093G0', '0096B0', '0096D0', '0097F0', '0098T0', '0099W0', '0099X0', '0101C0', '0105P0', '0120G0', '0126Z0']
    for code in stock_code:
        print(code)
        stock_data = fdr.DataReader(code, '2026-01-01')
        assert len(stock_data) > 0
        assert 'Close' in stock_data.columns