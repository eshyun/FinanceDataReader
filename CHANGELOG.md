# Changelog

## Unreleased

- Added KRX login/session support for `FinanceDataReader.krx` (optional `curl-cffi`) and routed KRX HTTP requests through a shared session wrapper.
- Enabled KRX auto-login by default (best-effort; requires credentials to actually login).
