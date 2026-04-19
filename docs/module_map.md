## Mapsi 모듈 지도 (Module Map)

> 이 문서는 Mapsi 의 모든 모듈/파일이 어떤 역할을 하고 어떻게 맞물리는지를
> 한 장에 담은 "지도" 다. 새 합류자는 이 문서를 먼저 읽고 → `spec/interfaces.md`
> (계약) → 관심 모듈 순으로 들어가면 된다.

---

### 1. 큰 그림 — 5단계 파이프라인

```
사용자 mapsi CLI
   │
   ▼  ① 부트스트랩 + ② 파싱 + ③ AST 워크 + ④ 빌드 + ⑤ 패키징
.hwpx (ZIP)
```

각 모듈은 위 5단계 중 1개에 1:1 대응된다. 디렉토리 트리 + 한 줄 요약:

```
mapsi/
├── 진입 / 오케스트레이션
│   ├── __main__.py        python -m mapsi 진입점 (cli.main 호출)
│   ├── cli.py             argparse + .env 로드 + work_dir 관리 + dry-run 분기
│   └── converter.py       md_to_hwpx() — 5단계 파이프라인의 "지휘자"
│
├── 입력 측 (마크다운 → 중간 표현 Block)
│   ├── parser.py          markdown-it-py 토큰 → 평탄 Block 리스트
│   └── ast_walker.py      문맥 의존 규칙 적용 (캡션 승격, 참고문헌 demote, 각주 흡수)
│
├── 출력 측 (Block → HWPX XML)
│   └── builder/
│       ├── header.py      templates/Contents/header.xml 로드 + style 테이블 파싱
│       ├── section.py     section0.xml 조립 (블록 → hp:p 디스패치)
│       ├── elements.py    개별 hp:p / hp:run / hp:tbl / hp:pic / hp:footNote 빌더
│       ├── equation.py    hp:equation 빌더 (Phase 12 — 현재는 NotImplementedError)
│       ├── bindata.py     이미지 파일을 BinData/ 로 복사 + ID 발급
│       └── manifest.py    content.hpf 의 opf:manifest 패치 (이미지 항목 등록)
│
├── 패키징
│   └── packager.py        work_dir 을 .hwpx ZIP 으로 묶음 (mimetype 무압축 첫 엔트리)
│
├── 스타일 룩업 보조
│   ├── config.py          spec/styles.yaml 로더 (깊이 키 정수 정규화)
│   └── styles.py          역할(role) + depth → 스타일 이름 조회 순수 함수
│
├── 수식 LLM
│   └── math/
│       ├── converter.py   LaTeX → HNC 마커 변환 (Anthropic > OpenAI > 폴백)
│       └── cache.py       결과를 ~/.mapsi/equation_cache.json 에 sha256 키로 캐시
│
└── 검증 도구
    └── inspect.py         라이브러리 + CLI: HWPX 의 (스타일 이름, 텍스트) 시퀀스 덤프

# 데이터 / 스펙 (코드 아님)
templates/Contents/header.xml   — 모든 스타일 정의의 단일 진실원
spec/styles.yaml                — 역할(role) → 스타일 이름 매핑 (= "라우팅 테이블")
samples/base/unpacked/...       — secPr / settings.xml / content.hpf 부트스트랩 원본
docs/decisions/                 — ADR 0001 (캡션), 0002 (수식 마커)
spec/interfaces.md              — 7개 계약 (Contracts) 의 시그니처 명세
```

---

### 2. 파일별 책임

#### 2.1 진입 / 오케스트레이션

##### `mapsi/__main__.py`
단 11줄. `python -m mapsi ...` 호출이 들어오면 `cli.main()` 으로 위임. 그 외엔 아무것도 안 한다.

##### `mapsi/cli.py`
사용자 진입점. 책임:
- argparse (`--no-llm`, `--dry-run`, `--verbose`, `--style-map`, `-o`)
- `.env` 로드 — **프로젝트 `.env` 가 셸 환경 변수보다 우선** (`load_dotenv(override=True)`),
  `OPENAI_API_BASE` / `OPENAI_BASE_URL` 안전망 포함 (fix(cli) 0153d303 참조)
- `--no-llm` 일 때 **`MAPSI_NO_LLM=1` 환경 변수 설정** (← 이게 폴백 트리거)
- `tempfile.TemporaryDirectory` 로 work_dir 생성 → `converter.md_to_hwpx()` 호출
- `--dry-run` 분기는 패키징 직전까지 모든 단계를 돌리되 출력 파일은 안 씀
  (`build_section()` 까지 호출해서 styles.yaml 매핑 누락 / figure src 누락 같은 오류를
  파일 쓰기 없이 잡는다)

##### `mapsi/converter.py`
파이프라인 지휘자. **50줄 이내** 의 얇은 함수 `md_to_hwpx()` 가 다음 순서로 위임:
1. `_bootstrap_workdir()` — `templates/` + `samples/base/` → work_dir 복사
2. `parse_markdown()` — 마크다운 → Block 리스트
3. `walk()` — 문맥 규칙 적용
4. `_register_figure_images()` — 그림 src 들을 BinData 로 복사 + manifest 항목 모음
5. `update_manifest()` (이미지가 있을 때만) → `parse_style_table()` →
   `build_section()` → bytes 를 `section0.xml` 에 씀
6. `package_hwpx()` — ZIP

이 파일 자체에는 XML 도, 토큰도, LLM 도 없다. 순수 호출 순서만.

#### 2.2 입력 측

##### `mapsi/parser.py` (가장 큰 모듈, ~574줄)
markdown-it-py 의 토큰 스트림을 받아 **평탄한 `Block` 리스트** 로 변환한다.
다음 확장이 활성화되어 있다.

- `commonmark` 베이스 + `enable("table")` (GFM 표)
- `mdit_py_plugins.footnote.footnote_plugin` (Pandoc 각주 `[^id]`)
- `mdit_py_plugins.dollarmath.dollarmath_plugin` (LaTeX `$...$` / `$$...$$`)

각 토큰별로 `Block(role=..., depth=..., text=..., meta={...})` 를 emit 한다.
인라인 마크 (각주, 수식) 는 paragraph 의 `meta` 에 offset 과 함께 보관 —
`text` 필드에는 마커 자체가 들어가지 않는다.

```python
Block(
    role="paragraph",
    text="평문 안에 인라인으로  와 같이...",
    meta={"equation_marks": [
        {"offset": 12, "latex": "a^2+b^2=c^2", "display": False},
    ]},
)
```

##### `mapsi/ast_walker.py`
Block 리스트를 한 번 더 훑으면서 **문맥 의존 규칙 4개** 를 적용한다.

| # | 규칙 | 동작 |
|---|---|---|
| 1 | 표 캡션 승격 | `^(표\|Table)\s+\d+\.\s*` 로 시작하는 표 **직전** 단락을 흡수 → `meta["caption"]` |
| 2 | 그림 캡션 승격 | `^(그림\|Figure)\s+\d+\.\s*` 로 시작하는 figure **직후** 단락을 흡수 |
| 3 | 참고문헌 demote | h1 텍스트가 `참고문헌` / `참고 문헌` / `References` / `REFERENCES` 면 다음 h1 까지 모든 paragraph/list 를 `role="reference"` 로 |
| 4 | 각주 본문 흡수 | `role="footnote_def"` 블록을 paragraph 의 `meta["footnote_marks"][i]["text"]` 에 합치고 정의 블록 제거 |

표=직전 / 그림=직후 의 비대칭은 한/글의 출판 관습과 일치 (ADR 0001).

#### 2.3 출력 측 (`builder/`)

##### `builder/header.py`
`Contents/header.xml` 을 로드하고 `hh:style` 들을 `name → StyleEntry(id, name, para_pr_id, char_pr_id)` 딕셔너리로 파싱한다. 빌더가 `"본문"` 같은 이름을 던지면 정수 ID 가 튀어나온다. **header.xml 은 동적 조립하지 않는다** — 진실원이라서 그대로 복사한다 (개발자 핸드오프 §3.1).

##### `builder/section.py`
`section0.xml` 의 최상위 조립자. base section 에서 `hp:secPr` 만 보존하고 본문은 다 비운 뒤, Block 들을 role 별로 디스패치:
- `table` → `build_table_wrapper()`
- `figure` → `build_figure_paragraph()` (이미지 있으면 hp:pic 임베드)
- 그 외 → `build_paragraph()`

##### `builder/elements.py` (압도적으로 가장 큼, ~1110줄)
진짜 XML 노드를 만드는 빌더 함수들의 집합.

- `build_paragraph` — hp:p (footnote_marks/equation_marks 분기)
- `build_table_wrapper` — hp:p > hp:tbl + (선택) caption
- `build_figure_paragraph` — hp:p (image_info 있으면 hp:pic, 없으면 placeholder)
- `_make_run_with_footnotes` — hp:run 안에 hp:t / hp:ctrl(footNote) 번갈아 emit
- `_make_run_with_equations` — `math.converter.convert_equation()` 호출해 그 결과를 hp:t 에 박음

한/글 본가 출력과 동일한 구조 (예: 각주는 `<hp:ctrl><hp:footNote><hp:subList><hp:p styleIDRef="각주">...`) 를 모방한다.

##### `builder/equation.py`
`hp:equation` XML 의 진짜 빌더. **현재는 `NotImplementedError`** 만 있다 (ADR 0002 — v0.1 은 평문 마커로 대체, 본격 구현은 v0.2 의 Phase 12 로 미룸).

##### `builder/bindata.py`
그림 1개당 1회 호출. 원본 PNG/JPG 를 `work_dir/BinData/imageN.<ext>` 로 복사하고, `hp:pic` 이 참조할 ID 문자열 (`"image1"`, `"image2"`, ...) 과 manifest 항목 dict 을 반환한다. 같은 src 가 여러 figure 에 등장해도 1번만 복사되고 ID 가 공유된다.

##### `builder/manifest.py`
`bindata` 가 모은 entry 들을 `Contents/content.hpf` 의 `opf:manifest` 안에 `<opf:item ... isEmbeded="1"/>` 로 in-place 기록한다.

#### 2.4 패키징

##### `mapsi/packager.py`
work_dir 통째 → ZIP. 핵심 규약: **`mimetype` 이 ZIP 의 첫 엔트리이고 무압축**. 이 규칙이 깨지면 한/글이 파일을 못 연다 (개발자 핸드오프 §시나리오 4 의 95% 원인).

#### 2.5 스타일 룩업 보조

##### `mapsi/config.py`
`spec/styles.yaml` 을 dict 으로 로드. heading / list 의 깊이 키 (`"1"`, `"2"`, ...) 를 정수로 정규화.

##### `mapsi/styles.py`
작은 순수 함수 1개 (`style_name(style_map, role, depth)`). 빌더는 이 함수로 `"본문"` 같은 이름을 받고, `header.parse_style_table()` 결과로 정수 ID 로 변환한다.

> **이름 → ID 의 흐름**
>
> ```
> role (마크다운 의미)
>   → style_name(style_map, role, depth)        # spec/styles.yaml 매핑
>   → "본문"
>   → style_table["본문"]                        # header.xml 파싱 결과
>   → StyleEntry(id="3", para_pr_id="1", char_pr_id="0")
>   → XML 속성 (styleIDRef="3" paraPrIDRef="1" charPrIDRef="0")
> ```

#### 2.6 수식 LLM (`math/`)

##### `math/converter.py`
`convert_equation(latex, display) → "[hnc 수식]...[/hnc 수식]"`. **`--no-llm` 폴백의 핵심 위치** (§3 참조).

##### `math/cache.py`
`~/.mapsi/equation_cache.json` 에 `sha256(latex|display)` 키로 변환 결과 저장. `MAPSI_EQUATION_CACHE` 환경 변수로 캐시 경로 오버라이드 (테스트 격리용). 마커는 캐시에 안 들어가고 본문만 저장 — 마커 부착은 항상 `convert_equation()` 의 책임.

#### 2.7 검증 도구

##### `mapsi/inspect.py`
라이브러리 + CLI 겸용. `python -m mapsi.inspect file.hwpx` 가 단락별 `(스타일 이름, 텍스트)` 시퀀스를 덤프한다. `--styles` 옵션은 사용된 스타일 정의 요약 + 정합성 검증까지 수행. 한/글 뷰어(무료) 가 스타일 표시줄이 사실상 없어 변환 검증이 어려워서, 정품 한/글 없이도 셸에서 빠르게 대조하기 위한 도구다.

#### 2.8 데이터 / 스펙 (코드 아님)

| 파일 | 역할 |
|---|---|
| `templates/Contents/header.xml` | **모든 스타일 정의의 단일 진실원** (id, paraPrIDRef, charPrIDRef 의 출처). 변환기는 이 파일을 그대로 복사하지 동적 조립하지 않음 |
| `templates/{mimetype, version.xml, META-INF/*}` | 정적 부트스트랩 자산 (모든 HWPX 가 동일) |
| `samples/base/unpacked/Contents/section0.xml` | secPr 호스트 단락의 출처 (페이지 크기, 여백 등 문서 전역 속성을 빌릴 곳) |
| `samples/base/unpacked/{settings.xml, content.hpf}` | 동적 자산 부트스트랩 |
| `spec/styles.yaml` | **role → 스타일 이름** 라우팅. yaml 한 줄 고치면 라우팅이 바뀜 |
| `spec/interfaces.md` | 7개 계약 (Contracts) 의 시그니처 명세 |
| `docs/decisions/0001-table-caption-promotion.md` | 캡션 승격 정책 (표=직전, 그림=직후) |
| `docs/decisions/0002-equation-marker-mode.md` | 수식 평문 마커 모드 결정 (= 현재 동작) |

---

### 3. `--no-llm` 동작 트레이스 — "LaTeX 원문 그대로" 는 어디서?

3개 모듈을 순서대로 통과한다.

#### ① CLI: `--no-llm` 깃발을 환경 변수로 변환

```python
# mapsi/cli.py:58-60
if args.no_llm:
    import os
    os.environ["MAPSI_NO_LLM"] = "1"
```

깃발이 환경 변수가 된다. 이렇게 하는 이유 — 빌더 코드에 LLM 의존성을 노출하지 않기 위해. 빌더는 환경 변수만 보면 되고, **왜 OFF 인지** (`--no-llm`, `MAPSI_NO_LLM=1` 자동 export, 테스트의 monkeypatch) 는 신경 안 쓴다.

#### ② `math/converter.py` 의 결정 분기

```python
# mapsi/math/converter.py:44-79
def convert_equation(latex: str, display: bool) -> str:
    stripped = latex.strip()

    if os.environ.get("MAPSI_NO_LLM"):
        return _wrap(stripped)        # ① LLM 안 부르고 LaTeX 원문 그대로 마커

    cached = cache.lookup(stripped, display)
    if cached is not None:
        return _wrap(cached)

    converted = _try_llm(stripped, display)
    if converted is None:
        return _wrap(stripped)        # ② LLM 호출 실패 시 같은 폴백

    cache.store(stripped, display, converted)
    return _wrap(converted)


def _wrap(body: str) -> str:
    return f"[hnc 수식]{body}[/hnc 수식]"
```

폴백 경로의 본질은 **`return f"[hnc 수식]{latex.strip()}[/hnc 수식]"` 단 한 줄**. LLM 호출도 캐시 조회도 안 한다.

폴백 트리거는 **3가지** 이고 모두 같은 결과를 낸다:

| # | 조건 | 위치 | 결과 |
|---|---|---|---|
| 1 | `MAPSI_NO_LLM=1` (`--no-llm` 또는 `tests/conftest.py` 가 강제) | `converter.py:64` | LaTeX 원문 그대로 마커 |
| 2 | API 키 자체가 없음 (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY` 둘 다 unset) | `converter.py:86–98` | `_try_llm()` 이 `None` 반환 → 73번 줄 폴백 |
| 3 | LLM 호출이 예외 (네트워크 401, 429 등) | `converter.py:91, 96` | 동일 — `_try_llm()` 이 `None` |

이 세 경로가 **모두 같은 결과** 를 내도록 의도적으로 통합한 게 ADR 0002 의 핵심 — "변환은 절대 멈추면 안 된다, 폴백이 곧 안전망".

#### ③ 빌더가 그 문자열을 hp:t 에 박음

`build_paragraph` 가 `meta["equation_marks"]` 를 발견하면 `_make_run_with_equations` 로 가고:

```text
text 의 마커 직전 부분 → <hp:t>...</hp:t>
convert_equation(latex, display) 호출
   → "[hnc 수식]a^2 + b^2 = c^2[/hnc 수식]"
   → <hp:t>그 문자열 그대로</hp:t>
text 의 마커 직후 부분 → <hp:t>...</hp:t>
```

빌더는 변환 결과가 LaTeX 원문이든 HNC 스크립트든 **구분 안 한다** — 그냥 "수식 자리에 들어갈 평문" 으로 취급. 이게 ADR 0002 가 v0.1 에서 추구한 결합도 분리.

---

### 4. 한 그림으로 보는 데이터 흐름

```
input.md
   │
   ▼  parser.py: markdown-it-py
[Block(role="paragraph",
       text="평문 안에 인라인으로  와 같이...",
       meta={"equation_marks": [
           {"offset": 12, "latex": "a^2+b^2=c^2", "display": False}
       ]}), ...]
   │
   ▼  ast_walker.py: 캡션/참고문헌/각주 규칙 적용
[같은 Block 리스트, 단 캡션 흡수·각주 본문 합쳐짐]
   │
   ▼  builder/section.py: role 별 dispatch
   │     ├─ table       → build_table_wrapper
   │     ├─ figure      → build_figure_paragraph (+ image_map 으로 hp:pic)
   │     └─ 그 외        → build_paragraph
   │                        ├─ footnote_marks 있으면 _make_run_with_footnotes
   │                        └─ equation_marks 있으면 _make_run_with_equations
   │                                            └─ math/converter.convert_equation()
   │                                                  ├─ MAPSI_NO_LLM=1 → LaTeX 원문 마커
   │                                                  ├─ 캐시 hit       → 캐시값 마커
   │                                                  ├─ Anthropic OK   → HNC 스크립트 마커
   │                                                  ├─ OpenAI    OK   → HNC 스크립트 마커
   │                                                  └─ 다 실패         → LaTeX 원문 마커
   │
   ▼  section0.xml (bytes) → work_dir 에 씀
   │  + work_dir/BinData/imageN.* (이미지)
   │  + work_dir/Contents/content.hpf (manifest 갱신됨)
   │
   ▼  packager.py: ZIP (mimetype 무압축 첫 엔트리)
output.hwpx
```

---

### 5. 더 읽을 거리

- 계약 시그니처 전체: `spec/interfaces.md`
- 캡션 승격 결정 근거: `docs/decisions/0001-table-caption-promotion.md`
- 수식 평문 마커 결정 근거: `docs/decisions/0002-equation-marker-mode.md`
- C 영역 (CLI / 패키징 / 이미지 / manifest / LLM) 핸드오프: `docs/c_handoff.md`
- 개발자 신규 합류 가이드: `docs/developer_handoff.md`
- 전체 로드맵 / 단계별 골든 픽스처: `docs/project_plan.md`
