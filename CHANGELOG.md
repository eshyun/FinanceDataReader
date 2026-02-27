# Changelog

## Unreleased

- Added KRX login/session support for `FinanceDataReader.krx` (optional `curl-cffi`) and routed KRX HTTP requests through a shared session wrapper.
- Enabled KRX auto-login by default (best-effort; requires credentials to actually login).
- Merged upstream KRX updates (KRX site changes) and aligned KRX request headers/Referer while keeping `krx_get`/`krx_post` session routing.
- Fixed an issue where KRX endpoints could return plain text `LOGOUT` for expired cookies, causing JSON parsing failures; `krx_get`/`krx_post` now clear the session and retry once.
- **[Breaking Change]** Credential file default location changed from `~/.config/finance-datareader/krx_credentials.json` to `~/.config/krx-session/krx_credentials.json`.
- Login sessions are now automatically saved to file (`~/.config/krx-session/session.json`) for **cross-process session sharing**.
- Multiple Python scripts or packages (FinanceDataReader, pykrx, etc.) can now share the same KRX session, preventing duplicate logins.
- Session files have a 30-minute TTL and automatically re-login when expired.
- Session file location can be customized via `KRX_SESSION_FILE` or `KRX_SESSION_DIR` environment variables.
- Added `clear_session_file()` function to manually delete saved sessions.
- Replaced POSIX-only `fcntl` file locks with `portalocker` to support Windows for session file locking.
