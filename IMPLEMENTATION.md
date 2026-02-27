# Implementation Notes

## KRX login/session

FinanceDataReader's `FinanceDataReader.krx` module now provides a KRX "login" flow and shared HTTP session layer similar to `pykrx`.

### Key points

- `FinanceDataReader.krx.login(...)` performs a login handshake against `https://data.krx.co.kr` and stores the resulting session globally.
- KRX modules (`FinanceDataReader.krx.data`, `FinanceDataReader.krx.listing`, `FinanceDataReader.krx.snap`) use `krx_get`/`krx_post` so that the shared session can be reused for all KRX requests.
- KRX request headers (including `Referer`) are kept in sync with KRX site requirements while still routing requests through the shared session.
- Login requires credentials and uses `curl-cffi` to create a browser-impersonated session.
- Cross-process session sharing uses a file lock implemented with `portalocker` for cross-platform support.

### Credentials resolution

Credentials are resolved in the following order:

1. Explicit `mbr_id` / `password` arguments
2. Environment variables:
   - `KRX_MBR_ID` (or `KRX_ID`)
   - `KRX_PASSWORD` (or `KRX_PW`)
3. Credentials file:
   - `KRX_CREDENTIALS_FILE` (if set)
   - otherwise `~/.config/finance-datareader/krx_credentials.json`

### Auto-login

- Auto-login is enabled by default.
- `krx_get`/`krx_post` will attempt to login once (best-effort) before sending requests.
- If KRX returns plain text `LOGOUT` (typically due to expired/invalid cookies), `krx_get`/`krx_post` will clear the saved/global session and retry the request once.

Relevant public APIs:

- `FinanceDataReader.krx.login`
- `FinanceDataReader.krx.enable_auto_login_on_failure`
- `FinanceDataReader.krx.auto_login_on_failure_enabled`
- `FinanceDataReader.krx.set_http_session` / `get_http_session`
