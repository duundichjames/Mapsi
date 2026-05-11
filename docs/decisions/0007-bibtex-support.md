# ADR 0007 — BibTeX 인용 처리 지원 (v0.2)

상태: Accepted (2026-05-11, `feature/bibtex-support` 시점)
관련: `mapsi/bibliography/`, `mapsi/parser.py`, `mapsi/ast_walker.py`,
`mapsi/builder/elements.py`, `mapsi/converter.py`, ADR 0002, ADR 0004, ADR 0005

## 배경

Mapsi v0.1 은 한/글 문서의 구조 변환(헤딩·리스트·표·그림·각주·수식·
인라인 서식)을 완성했다. 그러나 학술 문서의 핵심 요소인 **참고문헌
인용**은 지원하지 않았다. Pandoc 확장 문법 `[@key]` 형태의 BibTeX
인용이 마크다운 원고에 그대로 남아 평문으로 출력되었다.

한국어 학술 환경에서 인용 처리는 단순 치환이 아니다.

- 한국어 저자 (`김철수`)와 영어 저자 (`Smith, James`)는 표기 규칙이 다르다.
- 첫 등장과 재등장에서 저자 목록 축약 방식이 달라진다 (`이영희·박민수·최지훈`
  → `이영희 외`; `et al.`).
- APA·Chicago·MLA 등 서구 스타일의 직접 적용이 아닌, 한국 학술지의 관행을
  따르는 독자적 출력 형식이 필요하다.
- `.bib` 파일 경로를 YAML front matter 로 지정하는 방식과, 마크다운 문서 안에
  ` ```bibtex ``` ` 블록으로 직접 포함하는 방식 둘 다 지원해야 한다.

## 결정

아래 여섯 가지 설계 결정을 확정했다.

---

### 결정 1 — citation_marks 방식 채택 (텍스트 치환 대비)

인용 마크를 `block.meta["citation_marks"]` 에 구조화 데이터로 저장하고,
본문 텍스트에서는 인용 구문을 제거한 뒤 offset 으로 삽입 위치를 기록한다.
빌더(`build_paragraph`)가 `_make_run_with_citations` 로 텍스트와 마크를 조합해
최종 XML 을 생성한다.

이 방식은 v0.1 에서 각주(`footnote_marks`)와 수식(`equation_marks`),
인라인 서식(`inline_marks`)에 이미 확립된 패턴의 직접 연장이다.

**대안: 파서 단계에서 즉시 텍스트 치환**
- 장점: 구현이 단순하다. `[@kim2023]` → `(김철수, 2023)` 문자열 치환 후
  평문 단락으로 emit 하면 빌더 변경이 불필요하다.
- 단점: ① walker 또는 빌더가 인용 위치를 사후에 알 수 없어 인용 번호 부여,
  하이퍼링크, 참고문헌 목록 연동 등 v0.2 이후 확장이 불가능하다.
  ② 한 단락에 각주·수식과 인용이 공존할 때 기존 마크 충돌 검사를
  우회하게 되어 빌더 계약이 깨진다.

---

### 결정 2 — `read_front_matter()` 별도 공개 함수 추가

`parse_markdown(md_path)` 시그니처를 변경하지 않는다. 대신
`read_front_matter(md_path) -> dict` 를 새 공개 함수로 추가한다.
YAML front matter 의 `bibliography:` 키를 통해 외부 `.bib` 파일 경로를
읽는다.

`converter.py` 는 변환 전에 `read_front_matter` 를 먼저 호출해 BibTeX
데이터를 준비하고, 이후 `parse_markdown` 과 `walk(bib_data=...)` 를
순서대로 호출한다.

**대안 ①: `parse_markdown` 이 front matter 반환하도록 시그니처 변경**
- 단점: 기존 호출처 (`test_parser.py` 등 전체) 가 파괴적으로 깨진다.
  반환 타입이 `tuple[dict, list[Block]]` 으로 바뀌어 기존 코드가
  컴파일 오류 없이 잘못 동작할 위험이 있다.

**대안 ②: `parse_markdown` 이 front matter 를 `blocks[0].meta` 에 포함**
- 단점: 소비자가 front matter 를 쓰려면 첫 블록의 meta 를 검사해야 해
  API 가 암묵적이다. front matter 가 없을 때의 처리를 모든 소비자가
  직접 처리해야 한다.

---

### 결정 3 — `bibtexparser` 패키지 사용 (자체 파싱 대비)

BibTeX 파싱을 `bibtexparser` 라이브러리에 위임한다.
`mapsi/bibliography/parser.py::load_bibliography` 가 파일 경로 목록과
인라인 문자열 목록을 받아 `dict[str, dict]` (citekey → 필드 dict) 를
반환한다. 중복 citekey 는 선 정의 우선.

**대안: 정규식 기반 자체 BibTeX 파서 구현**
- 장점: 의존성 추가 없음.
- 단점: ① BibTeX 는 중첩 braces, string macro (`@string`),
  공통 문자열 (`month = jan`) 등 코너케이스가 많다. 정규식으로
  견고한 파서를 만들려면 학술 인용 처리와 무관한 파싱 작업에
  상당한 공수가 소요된다.
  ② 사용자가 LaTeX 도구로 생성한 실제 `.bib` 파일에는 매크로와
  특수 인코딩이 흔하게 등장한다. 자체 구현이 조용히 실패하면
  사용자가 인용 누락을 뒤늦게 발견한다.

---

### 결정 4 — `bibtexparser` v1.x 선택

`bibtexparser>=1.3,<2.0` 을 사용한다.

**v2.x 를 선택하지 않은 이유**

우리는 `pyproject.toml` 에서 `bibtexparser>=1.3,<2.0` 으로 v1 계열을
명시적으로 지정한다. v2 는 API 가 전면 재설계되어 학술 커뮤니티 도구들
(Zotero, JabRef 등) 의 호환성 테스트가 충분히 쌓이지 않았기 때문이다.

v1 API 는 단순하고(`bibtexparser.loads(content, parser)` →
`db.entries` 리스트) 우리가 필요한 기능(필드 추출, common strings 확장,
citekey 접근)을 모두 제공한다. v1 → v2 마이그레이션이 필요할 경우
`mapsi/bibliography/parser.py` 한 파일의 내부 구현만 교체하면 된다.

---

### 결정 5 — 기본 의존성으로 추가

`pyproject.toml` 의 `[project] dependencies` 에 `bibtexparser>=1.3,<2.0`
을 추가한다. optional extras 로 분리하지 않는다.

**optional 로 분리하지 않은 이유**

학술 문서 변환이 Mapsi 의 핵심 사용 사례이며, BibTeX 인용이 없는 `.md`
파일도 `bibtexparser` 가 설치되어 있어야 `import mapsi` 가 오류 없이
동작한다. optional 로 두면 front matter 에 `bibliography:` 가 없는 파일을
변환하려는 사용자도 의존성 설치 오류를 마주칠 수 있다. 패키지 크기 증가
(~200 KB) 는 학술 목적 도구로서 감수할 수 있는 트레이드오프다.

---

### 결정 6 — 한국어 학술 환경에 최적화된 출력 형식

`mapsi/bibliography/formatter.py::BibFormatter` 가 저자 언어(한국어/영어)를
자동 감지하여 서로 다른 형식을 적용한다.

#### 본문 인용 형식

| 인용 유형 | 마크다운 | 출력 (한국어 저자) | 출력 (영어 저자) |
|---|---|---|---|
| bracketed | `[@kim2023]` | `(김철수, 2023)` | `(Smith, 2020)` |
| locator 포함 | `[@kim2023, p. 15]` | `(김철수, 2023, p. 15)` | — |
| 복수 키 | `[@a; @b]` | `(저자A, 연도; 저자B, 연도)` | — |
| bare (in-text) | `@kim2023` | `김철수(2023)` | `Smith (2020)` |
| suppress_author | `-@kim2023` | `(2023)` | `(2020)` |

#### 저자 축약 규칙

- 3인 이상: 첫 등장 시 전체 나열 → 재등장 시 "X 외" (한국어) / "X et al." (영어)
- 한국어 저자 구분자: 중점 `·` (쉼표 대신)
- 영어 저자 구분자: `, ` 및 마지막 저자 앞 `and`

#### 참고문헌 목록 형식

- **한국어 article**: `저자. (연도). 제목. 저널명, 권(호), 페이지.`
- **한국어 book**: `저자. (연도). 제목. 도시: 출판사.`
- **영어 article**: `저자. 연도. "제목." 저널명 권(호): 페이지.` (Chicago 스타일)
- **영어 book**: `저자. 연도. 제목. 도시: 출판사.`

한국어 판별 기준: 저자·제목 필드에 `가`–`힣` 범위 문자가 포함되면 한국어로 분류.

#### 참고문헌 목록 삽입 위치

`# 참고문헌` / `# References` / `# Bibliography` 헤딩(대소문자 무관)이
문서에 존재하면 그 직후에 삽입. 존재하지 않으면 문서 끝에 헤딩 `# 참고문헌`
과 함께 자동 추가. 삽입 순서는 문서 내 최초 인용 등장 순.

## 구현 범위

```
mapsi/bibliography/
├── __init__.py         # load_bibliography, BibFormatter 공개 export
├── parser.py          # load_bibliography — .bib 파일 + 인라인 BibTeX 로드
└── formatter.py       # BibFormatter — 인용 형식화, 참고문헌 목록 생성

mapsi/parser.py        # read_front_matter, read_inline_bibtex 추가;
                       # _split_citations; bibtex 펜스 블록 억제
mapsi/ast_walker.py    # _resolve_citations, _inject_reference_list;
                       # walk(blocks, *, bib_data=None)
mapsi/builder/elements.py  # _make_run_with_citations; 4-mark 상호배제
mapsi/converter.py     # BibTeX 파이프라인 연결
pyproject.toml         # bibtexparser>=1.3,<2.0 추가
```

## 테스트 커버리지

| 테스트 파일 | 테스트 수 | 검증 범위 |
|---|---|---|
| `test_bibliography_parser.py` | 10 | `load_bibliography` 파일/인라인/혼합/중복 |
| `test_bibliography_formatter.py` | 24 | `BibFormatter` 5가지 인용 유형·축약·목록 형식 |
| `test_parser_citations.py` | 25 | `read_front_matter`, `read_inline_bibtex`, `_split_citations`, offset |
| `test_ast_walker_citations.py` | 17 | `_resolve_citations`, `_inject_reference_list` |
| `test_bibtex_integration.py` | 7 | 골든 파일 기반 end-to-end 및 빌더 통합 |
| **합계** | **83** | |

## 참고

- 인용 마크 패턴의 선례: ADR 0002 (equation_marks), ADR 0005 (footnote_marks)
- 4-mark 상호배제 계약: ADR 0004 §결정 4 (v0.1 에서 3-mark, v0.2 에서 citation 추가)
- 골든 픽스처: `tests/golden/11_bibtex/`
- 통합 검증: 한국어와 영어 혼합 문서로 5가지 인용 유형 end-to-end 검증 완료
