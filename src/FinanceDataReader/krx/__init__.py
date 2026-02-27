
import json
import os
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timedelta

import requests

try:
    import portalocker
except Exception:
    portalocker = None


_HTTP_SESSION = None


class KrxRequestError(RuntimeError):
    pass


@contextmanager
def _file_lock(lock_file: Path, *, shared: bool):
    if portalocker is None:
        yield
        return

    lock_file.parent.mkdir(parents=True, exist_ok=True)
    flags = portalocker.LOCK_SH if shared else portalocker.LOCK_EX
    with portalocker.Lock(str(lock_file), mode="a", flags=flags):
        yield


def set_http_session(session):
    global _HTTP_SESSION
    _HTTP_SESSION = session


def get_http_session():
    return _HTTP_SESSION


def _create_curl_session():
    try:
        from curl_cffi import requests as crequests
    except Exception as e:
        raise KrxRequestError(
            "curl-cffi is required for KRX login. Please install curl-cffi."
        ) from e

    try:
        return crequests.Session(impersonate="chrome")
    except TypeError:
        return crequests.Session()


def _load_krx_credentials_from_file(path: str | None):
    if not path:
        return None
    p = Path(path).expanduser()
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise KrxRequestError(f"Failed to read KRX credentials file: {p}") from e
    if not isinstance(data, dict):
        raise KrxRequestError(f"Invalid KRX credentials file format: {p}")
    return data


def _resolve_krx_credentials(mbr_id: str | None, password: str | None):
    if mbr_id and password:
        return mbr_id, password

    if mbr_id is None:
        mbr_id = os.getenv("KRX_MBR_ID") or os.getenv("KRX_ID")
    if password is None:
        password = os.getenv("KRX_PASSWORD") or os.getenv("KRX_PW")
    if mbr_id and password:
        return mbr_id, password

    cred_path = os.getenv("KRX_CREDENTIALS_FILE")
    if not cred_path:
        cred_path = str(Path("~/.config/krx-session/krx_credentials.json"))
    data = _load_krx_credentials_from_file(cred_path)
    if data:
        mbr_id = mbr_id or data.get("mbrId") or data.get("mbr_id") or data.get("id")
        password = password or data.get("pw") or data.get("password")
    return mbr_id, password


_AUTO_LOGIN_ENABLED = True
_AUTO_LOGIN_ALLOW_DUP_LOGIN = False


def enable_auto_login(enabled: bool = True, *, allow_dup_login: bool = False):
    global _AUTO_LOGIN_ENABLED, _AUTO_LOGIN_ALLOW_DUP_LOGIN
    _AUTO_LOGIN_ENABLED = bool(enabled)
    _AUTO_LOGIN_ALLOW_DUP_LOGIN = bool(allow_dup_login)


def is_auto_login_enabled() -> bool:
    return _AUTO_LOGIN_ENABLED


def _get_session_file_path():
    """Get the session file path from environment or default location."""
    session_file = os.getenv("KRX_SESSION_FILE")
    if session_file:
        return Path(session_file).expanduser()
    
    session_dir = os.getenv("KRX_SESSION_DIR")
    if session_dir:
        return Path(session_dir).expanduser() / "session.json"
    
    return Path("~/.config/krx-session/session.json").expanduser()


def _serialize_session_cookies(session):
    """Serialize session cookies to a dict."""
    try:
        if hasattr(session, 'cookies'):
            cookies = {}
            for cookie in session.cookies:
                cookies[cookie.name] = {
                    'value': cookie.value,
                    'domain': cookie.domain,
                    'path': cookie.path,
                    'secure': cookie.secure,
                    'expires': cookie.expires,
                }
            return cookies
    except Exception:
        pass
    return {}


def _deserialize_session_cookies(session, cookies_dict):
    """Deserialize cookies dict back to session."""
    try:
        if hasattr(session, 'cookies'):
            for name, attrs in cookies_dict.items():
                session.cookies.set(
                    name=name,
                    value=attrs.get('value'),
                    domain=attrs.get('domain'),
                    path=attrs.get('path'),
                )
    except Exception:
        pass


def _save_session_to_file(session, mbr_no=None, ttl_minutes=30):
    """Save session to file with file locking."""
    session_file = _get_session_file_path()
    session_file.parent.mkdir(parents=True, exist_ok=True)
    
    now = datetime.now()
    expires_at = now + timedelta(minutes=ttl_minutes)
    
    session_data = {
        'cookies': _serialize_session_cookies(session),
        'created_at': now.isoformat(),
        'expires_at': expires_at.isoformat(),
        'last_used': now.isoformat(),
        'mbr_no': mbr_no,
        'ttl_minutes': ttl_minutes,
    }
    
    lock_file = session_file.parent / f"{session_file.name}.lock"
    try:
        with _file_lock(lock_file, shared=False):
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
    except Exception:
        try:
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
        except Exception:
            pass


def _load_session_from_file():
    """Load session from file if valid."""
    session_file = _get_session_file_path()
    if not session_file.exists():
        return None
    
    lock_file = session_file.parent / f"{session_file.name}.lock"
    
    try:
        with _file_lock(lock_file, shared=True):
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
    except Exception:
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
        except Exception:
            return None
    
    expires_at_str = session_data.get('expires_at')
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if datetime.now() >= expires_at:
                return None
        except Exception:
            return None
    
    try:
        session = _create_curl_session()
        cookies_dict = session_data.get('cookies', {})
        _deserialize_session_cookies(session, cookies_dict)
        
        session_data['last_used'] = datetime.now().isoformat()
        try:
            with _file_lock(lock_file, shared=False):
                with open(session_file, 'w', encoding='utf-8') as f:
                    json.dump(session_data, f, indent=2)
        except Exception:
            pass
        
        return session
    except Exception:
        return None


def clear_session_file():
    """Clear the saved session file."""
    session_file = _get_session_file_path()
    if session_file.exists():
        try:
            session_file.unlink()
        except Exception:
            pass


def login(
    mbr_id: str | None = None,
    password: str | None = None,
    *,
    session=None,
    set_global_session: bool = True,
    site: str = "mdc",
    allow_dup_login: bool = False,
):
    mbr_id, password = _resolve_krx_credentials(mbr_id, password)
    if not mbr_id or not password:
        raise KrxRequestError(
            "KRX login requires credentials. Provide mbr_id/password or set environment variables "
            "KRX_MBR_ID and KRX_PASSWORD. You may also set KRX_CREDENTIALS_FILE or use "
            "~/.config/krx-session/krx_credentials.json"
        )

    if session is None:
        session = _create_curl_session()

    base = "https://data.krx.co.kr"
    login_page = f"{base}/contents/MDC/COMS/client/view/login.jsp?site={site}"
    login_api = f"{base}/contents/MDC/COMS/client/MDCCOMS001D1.cmd"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"{base}/contents/MDC/COMS/client/MDCCOMS001.cmd",
        "Origin": base,
    }

    try:
        session.get(login_page, headers=headers, timeout=30)
    except TypeError:
        session.get(login_page, headers=headers)

    payload = {
        "mbrId": mbr_id,
        "pw": password,
        "mbrNm": "",
        "telNo": "",
        "di": "",
        "certType": "",
    }

    try:
        resp = session.post(login_api, headers=headers, data=payload, timeout=30)
    except TypeError:
        resp = session.post(login_api, headers=headers, data=payload)

    if getattr(resp, "status_code", None) != 200:
        snippet = (getattr(resp, "text", "") or "")[:200]
        raise KrxRequestError(
            f"KRX login failed with status={resp.status_code}. Response snippet: {snippet}"
        )

    def _parse_json_response(r):
        try:
            return r.json()
        except Exception:
            txt = getattr(r, "text", "") or ""
            try:
                return json.loads(txt)
            except Exception as e:
                ctype = (r.headers.get("content-type") or "").lower()
                snippet = txt[:200]
                raise KrxRequestError(
                    f"KRX login response is not JSON (content-type={ctype}). Response snippet: {snippet}"
                ) from e

    data = _parse_json_response(resp)

    err = (
        data.get("errorCode")
        or data.get("ERROR_CODE")
        or data.get("error_code")
        or data.get("_error_code")
    )
    msg = data.get("_error_message") or data.get("error_message") or data.get("ERROR_MESSAGE")

    success_codes = {"CD001"}
    if err and err in success_codes:
        err = None

    if err:
        if err == "CD011" and allow_dup_login:
            payload["skipDup"] = "Y"
            try:
                resp2 = session.post(login_api, headers=headers, data=payload, timeout=30)
            except TypeError:
                resp2 = session.post(login_api, headers=headers, data=payload)
            data2 = _parse_json_response(resp2)
            err2 = (
                data2.get("errorCode")
                or data2.get("ERROR_CODE")
                or data2.get("error_code")
                or data2.get("_error_code")
            )
            if err2:
                msg2 = data2.get("_error_message") or data2.get("error_message") or data2.get("ERROR_MESSAGE")
                if msg2:
                    raise KrxRequestError(f"KRX login failed (errorCode={err2}). {msg2}")
                snippet2 = str(data2)[:200]
                raise KrxRequestError(f"KRX login failed (errorCode={err2}). Payload snippet: {snippet2}")
            data = data2
        else:
            if msg:
                raise KrxRequestError(f"KRX login failed (errorCode={err}). {msg}")
            snippet = str(data)[:200]
            raise KrxRequestError(f"KRX login failed (errorCode={err}). Payload snippet: {snippet}")

    mbr_no = data.get("MBR_NO") or data.get("mbrNo")
    if not mbr_no:
        snippet = str(data)[:200]
        raise KrxRequestError(
            "KRX login did not return expected success fields (MBR_NO). "
            f"Payload snippet: {snippet}"
        )

    if set_global_session:
        set_http_session(session)
    
    # Save session to file for cross-process sharing
    _save_session_to_file(session, mbr_no=mbr_no, ttl_minutes=30)

    return session, data


def krx_login(*args, **kwargs):
    return login(*args, **kwargs)


def enable_auto_login_on_failure(enabled: bool = True, *, allow_dup_login: bool = False):
    return enable_auto_login(enabled, allow_dup_login=allow_dup_login)


def auto_login_on_failure_enabled() -> bool:
    return is_auto_login_enabled()


def _maybe_auto_login():
    if not _AUTO_LOGIN_ENABLED:
        return
    if get_http_session() is not None:
        return
    mbr_id, password = _resolve_krx_credentials(None, None)
    if not mbr_id or not password:
        return
    login(
        mbr_id=mbr_id,
        password=password,
        set_global_session=True,
        allow_dup_login=_AUTO_LOGIN_ALLOW_DUP_LOGIN,
    )


def _is_logout_response(resp) -> bool:
    """Detect a KRX 'LOGOUT' response which indicates an invalid/expired session.

    KRX sometimes returns plain text 'LOGOUT' (non-JSON) when the session cookies
    are no longer valid.
    """
    if resp is None:
        return False
    try:
        txt = (getattr(resp, "text", "") or "")
    except Exception:
        return False
    return txt.strip() == "LOGOUT"


def krx_get(url: str, *, headers: dict | None = None, params=None, timeout: int = 30):
    # Try to load session from file if not in memory
    if get_http_session() is None:
        file_session = _load_session_from_file()
        if file_session is not None:
            set_http_session(file_session)
    
    for attempt in range(2):
        _maybe_auto_login()
        session = get_http_session()
        if session is None:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        else:
            try:
                resp = session.get(url, headers=headers, params=params, timeout=timeout)
            except TypeError:
                resp = session.get(url, headers=headers, params=params)

        if attempt == 0 and _is_logout_response(resp):
            clear_session_file()
            set_http_session(None)
            continue
        return resp


def krx_post(url: str, *, headers: dict | None = None, data=None, timeout: int = 30):
    # Try to load session from file if not in memory
    if get_http_session() is None:
        file_session = _load_session_from_file()
        if file_session is not None:
            set_http_session(file_session)
    
    for attempt in range(2):
        _maybe_auto_login()
        session = get_http_session()
        if session is None:
            resp = requests.post(url, headers=headers, data=data, timeout=timeout)
        else:
            try:
                resp = session.post(url, headers=headers, data=data, timeout=timeout)
            except TypeError:
                resp = session.post(url, headers=headers, data=data)

        if attempt == 0 and _is_logout_response(resp):
            clear_session_file()
            set_http_session(None)
            continue
        return resp
