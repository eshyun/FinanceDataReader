# KRX 회원제 변경 대응 (KRX Data Marketplace Migration)

[[단독] 한국거래소 정보데이터시스템, 회원제 '데이터 마켓플레이스'로 변경 - 글로벌이코노믹](https://www.g-enews.com/view.php?ud=202512070927435241edf69f862c_1)

한국거래소는 2025-12-27부터 기존 정보데이터시스템이 회원 가입해야 이용할 수 있는 **KRX Data Marketplace**로 전면 개편했습니다.

이 변경으로 인해 `data.krx.co.kr` 기반으로 KRX 데이터를 스크레이핑하던 패키지(`FinanceDataReader` 포함)가 비로그인 상태에서 **403/HTML(비JSON) 응답/세션 만료** 등으로 실패할 수 있습니다.

관련 이슈(배경 참고):

- https://github.com/sharebook-kr/pykrx/issues/244

본 저장소는 이를 해결하기 위해 `FinanceDataReader`를 fork하여 **KRX 로그인 기능(세션/쿠키 확보) 및 자동 로그인(기본 ON)**을 추가했습니다.

## 수정 내용

### 1) KRX 로그인/세션 레이어 추가

#### 1.1. 목적

KRX Data Marketplace 전환 이후, KRX JSON 엔드포인트(`getJsonData.cmd`, `executeForResourceBundle.cmd`) 호출이 비로그인 상태에서 실패하는 경우가 많아졌습니다.

따라서 로그인 후 쿠키/세션을 확보하여, KRX 요청을 동일 세션으로 수행하도록 공통 레이어를 추가했습니다.

#### 1.2. 추가된 공개 API

`FinanceDataReader` 최상위에서 다음 API에 접근할 수 있습니다.

- `import FinanceDataReader as fdr`
- `fdr.krx.login(...)`
- `fdr.krx.enable_auto_login_on_failure(True/False, allow_dup_login=...)`
- `fdr.krx.auto_login_on_failure_enabled()`
- `fdr.krx.set_http_session(session)` / `fdr.krx.get_http_session()`
- `fdr.krx.krx_get(...)` / `fdr.krx.krx_post(...)`

#### 1.3. 구현 개요(기술 세부)

- 로그인은 KRX Data Marketplace 웹 로그인 API를 호출합니다.
  - 세션/쿠키 초기화:
    - `GET https://data.krx.co.kr/contents/MDC/COMS/client/view/login.jsp?site=mdc`
  - 로그인 API:
    - `POST https://data.krx.co.kr/contents/MDC/COMS/client/MDCCOMS001D1.cmd`
- `curl-cffi`의 `requests.Session(impersonate="chrome")`을 사용하여 브라우저 유사 세션을 구성합니다.
- 로그인 성공은 `MBR_NO` 등의 필드 존재 여부로 엄격히 판별합니다.

### 2) FinanceDataReader 내부 KRX 모듈을 공통 세션 래퍼로 연결

기존에는 `requests.get/post`로 KRX 엔드포인트를 직접 호출했습니다. 본 수정에서는 로그인 세션을 재사용할 수 있도록 아래 모듈에서 HTTP 호출을 공통 래퍼로 라우팅했습니다.

- `src/FinanceDataReader/krx/data.py`
- `src/FinanceDataReader/krx/listing.py`
- `src/FinanceDataReader/krx/snap.py`

즉, 로그인 세션이 있으면 해당 세션으로 요청하고, 없으면 일반 요청을 수행합니다(단, auto-login이 ON이면 로그인 best-effort 수행).

### 3) 자격증명(credential) 로딩 규칙

자격증명은 다음 우선순위로 로드합니다.

1. 함수 인자: `mbr_id`, `password`
2. 환경변수:
   - `KRX_MBR_ID` 또는 `KRX_ID`
   - `KRX_PASSWORD` 또는 `KRX_PW`
3. 자격증명 파일:
   - `KRX_CREDENTIALS_FILE`
   - 기본값: `~/.config/finance-datareader/krx_credentials.json`

자격증명 파일 포맷 예시:

```json
{
  "mbrId": "YOUR_ID",
  "pw": "YOUR_PASSWORD"
}
```

### 4) 자동 로그인(auto-login) 기본값: ON

- 본 fork에서는 auto-login을 **기본 ON**으로 설정했습니다.
- 동작은 best-effort이며, 자격증명이 설정되지 않은 경우 로그인 시도 없이 요청을 진행합니다.

## 사용법

### 1) 설치

KRX 로그인 기능은 optional dependency로 제공됩니다.

```bash
pip install "finance-datareader[krx]"
```

### 2) 환경변수 설정 예시

```bash
export KRX_MBR_ID="YOUR_ID"
export KRX_PASSWORD="YOUR_PASSWORD"
```

### 3) 코드 예시

```python
import FinanceDataReader as fdr

# (권장) 명시적으로 먼저 로그인
fdr.krx.login()

# 이후 KRX 데이터 호출
stocks = fdr.StockListing('KRX')
index_df = fdr.DataReader('KRX-INDEX:1001', '2023-01-01', '2023-01-31')
```

### 4) auto-login 제어

```python
import FinanceDataReader as fdr

# 기본값은 ON
assert fdr.krx.auto_login_on_failure_enabled() is True

# 필요 시 OFF
fdr.krx.enable_auto_login_on_failure(False)
```

## 참고

- KRX 서버 정책/차단 로직은 외부 환경 요인에 따라 변할 수 있습니다.
- 로그인/세션이 있어도 응답이 비정상(HTML 등)일 수 있으므로, 해당 경우 원인 파악을 위해 응답 스니펫 기반 에러 처리가 중요합니다.
