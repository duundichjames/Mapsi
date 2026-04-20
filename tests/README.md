# Mapsi 테스트 가이드

본 디렉토리는 Mapsi 변환기의 자동 회귀 테스트를 보관함. 모든 테스트는
`pytest` 로 실행되며, 단위 테스트와 통합/회귀 테스트로 구성됨.

## 빠른 실행

```bash
pytest                          # 전체 (현재 275개)
pytest tests/test_parser.py     # 파일 단위
pytest -k golden                # 이름 매칭
pytest -k "01_headings"         # 특정 픽스처만
pytest -v                       # 상세 출력
```

설치는 `pip install -e ".[dev]"` 로 pytest 포함된 개발 의존성을 설치해야 함.

## 파이프라인 개관

Mapsi 의 변환은 5 단계 파이프라인이며, 각 단계는 독립 모듈로 분리됨.
테스트도 단계별로 묶여 있음.

```
입력 .md
   │
   ▼  ┌──────────────────────────────────────────────┐
   │  │ ① 파서   mapsi/parser.py                     │  ← test_parser.py
   │  │   "# 제목" → Block(role="heading", depth=1)  │
   │  └──────────────────────────────────────────────┘
   ▼
   │  ┌──────────────────────────────────────────────┐
   │  │ ② AST walker   mapsi/ast_walker.py           │  (현재는 identity)
   │  └──────────────────────────────────────────────┘
   ▼
   │  ┌──────────────────────────────────────────────┐
   │  │ ③ 스타일 룩업   mapsi/styles.py + styles.yaml │  ← test_styles.py
   │  │   ("heading", 1) → "개요 1"  (이름)           │
   │  └──────────────────────────────────────────────┘
   ▼
   │  ┌──────────────────────────────────────────────┐
   │  │ ④ 빌더   mapsi/builder/                      │  ← test_elements.py
   │  │   "개요 1" + header.xml 룩업                  │  ← test_header.py
   │  │   → <hp:p styleIDRef="2" ...>제목</hp:p>      │
   │  └──────────────────────────────────────────────┘
   ▼
   │  ┌──────────────────────────────────────────────┐
   │  │ ⑤ 패키저   mapsi/packager.py                 │  ← test_smoke.py
   │  │   work/ 디렉토리 → ZIP (.hwpx)               │
   │  └──────────────────────────────────────────────┘
   ▼
출력 .hwpx
   │
   ▼  ┌──────────────────────────────────────────────┐
      │ ① ~ ⑤ 끝단 회귀                              │  ← test_golden.py
      │ .hwpx 검사 도구                               │  ← test_inspect.py
      │                                              │  ← test_golden_helper.py
      └──────────────────────────────────────────────┘
```

## 테스트 파일 일람

| 파일 | 개수 | 단계 | 검증 대상 |
|---|---:|---|---|
| `test_parser.py` | 49 | ① 파서 | 마크다운 → `Block` 리스트 변환 |
| `test_ast_walker.py` | 57 | ② 워크 | 표/그림 캡션 승격 + 각주 본문 흡수 + 참고문헌 섹션 demote |
| `test_styles.py` | 28 | ③ 스타일 룩업 | `(role, depth) → 스타일 이름` 매핑 |
| `test_header.py` | 3 | ④ 빌더 (헤더) | `header.xml` 로드 + 스타일표 파싱 |
| `test_elements.py` | 50 | ④ 빌더 (요소) | `Block` → `<hp:p>` / `<hp:tbl>` / `<hp:pic>` / `<hp:footNote>` / 수식 마커 XML 생성 |
| `test_bindata.py` | 10 | ④ 빌더 (자산) | 이미지 → `BinData/` 복사 + ID 발급 |
| `test_manifest.py` | 8 | ④ 빌더 (manifest) | `content.hpf` 의 `opf:manifest` 패치 |
| `test_math.py` | 29 | LaTeX → HNC | 수식 캐시 + 변환기 분기 (Anthropic > OpenAI > 폴백) |
| `test_converter_images.py` | 6 | 오케스트레이터 | figure → image_map 등록 헬퍼 |
| `test_smoke.py` | 8 | ⑤ 패키저 | `.hwpx` ZIP 형식 정합성 |
| `test_inspect.py` | 12 | 검사 도구 | `mapsi.inspect` 라이브러리 + CLI |
| `test_golden_helper.py` | 6 | 검사 도구 | `tests/_golden.py` 헬퍼 |
| `test_golden.py` | 9 | 끝단 회귀 | `.md` → `.hwpx` 전 파이프라인 |

총 **275개**.

---

## 단계별 상세

### ① 파서 — `test_parser.py` (49개)

**대상**: `mapsi/parser.py`의 `parse_markdown(md_text) -> list[Block]`

마크다운 문자열을 `markdown-it-py` 토큰으로 자르고, 우리 내부 자료구조인
`Block(role, depth, text, children, meta)` 의 평탄한 리스트로 변환함.

검증 케이스:
- 기초: 빈 입력 / 단일 단락 / 다중 단락
- 헤딩: h1~h6 + 본문/제목 혼합
- YAML front matter 제거
- 미지원 토큰(`hr`) → `NotImplementedError`
- Blockquote: 단일/다중/주변 단락 혼합
- 코드 블록: 펜스드(한 줄당 1 Block) / 빈 줄 보존 / 들여쓰기 코드
- 글머리 목록: 1단계 / 3단계 중첩 / 주변 단락
- 번호 목록
- softbreak → 개행
- 표: 단일 표 → 1 Block 평탄화 / 주변 단락 / 캡션 미승격
- 그림: 단독 이미지 단락 → `figure` 블록 / 빈 alt / 텍스트 혼합 폴백 /
  주변 단락 / 캡션 미승격
- 라운드트립: 골든 픽스처 01/02 의 `Block` 시퀀스 검증
- 각주 (Phase 7): `[^id]` 본문 → paragraph `meta["footnote_marks"]` 보존
  (offset 정확성, 마커 텍스트 제외, 등장 순서로 0,1,... 재부여,
  같은 단락 내 다중 마커, 정의 본문 strip, 07 샘플 라운드트립)
- 수식 (Phase 9): 인라인 `$...$` → paragraph `meta["equation_marks"]` 보존
  (offset / display=False / 단락 시작·끝·다중 마커); 디스플레이 `$$...$$`
  → 단독 paragraph `text=""` + offset=0 + display=True; 09 샘플 라운드트립

### ② AST walker — `test_ast_walker.py` (57개)

**대상**: `mapsi/ast_walker.py` 의 `walk()` 와
`TABLE_CAPTION_PATTERN` / `FIGURE_CAPTION_PATTERN` /
`REFERENCE_HEADING_TEXTS`.

파서가 만든 평탄 Block 리스트에 문맥 의존 규칙을 적용. 현재는 네
종류 — 표 캡션 승격 (직전 단락), 그림 캡션 승격 (직후 단락), 각주
본문 흡수 (footnote_def), 참고문헌 섹션 demote (h1 텍스트로 트리거).

검증 케이스:
- `TestCaptionPattern` (7): 표 정규식 매치 — 한국어 / 영어 / 다자리 번호 /
  마침표 없음 / 공백 없음 / 소문자 `table` / 줄 중간 매치 안 됨
- `TestCaptionPromotion` (10): 표 직전 단락 흡수 / 영어 캡션 /
  사용자 번호 무시 / 비매치 보존 / 헤딩 비승격 / 이미 캡션 있는 표 보존 /
  접두사만 있는 단락 비승격 / 첫 블록 표 / 입력 불변성 / 다중 표
- `TestFigureCaptionPattern` (6): 그림 정규식 매치 + 표/그림 정규식 상호
  비매치
- `TestFigureCaptionPromotion` (11): 그림 직후 단락 흡수 / 영어 캡션 /
  사용자 번호 무시 / 비매치 보존 / 접두사만 있는 단락 비승격 / 이미 캡션
  있는 그림 보존 / 마지막 그림 (다음 블록 없음) / 헤딩 비승격 / 입력
  불변성 / 다중 그림 / 표·그림 캡션 동시 흡수
- `TestFootnoteAbsorption` (7): 정의 본문이 본문 paragraph 의 마크에 흡수 /
  여러 정의가 id 키로 매칭 / 정의 없는 마크는 빈 본문 / 참조 없는 정의는
  소리없이 제거 / 마크 없는 단락은 객체 그대로 통과 / 같은 id 충돌 시
  처음 정의 우선 / 입력 불변성
- `TestReferenceHeadingTexts` (2): 후보 4 종 정확 일치 (`참고문헌`,
  `참고 문헌`, `References`, `REFERENCES`) / 소문자 `references` 비매치
- `TestReferenceSectionDemote` (13): 한국어 헤딩 후 단락 demote / 영어
  헤딩 / 대문자 `REFERENCES` / 무관한 헤딩은 트리거 X / h2 는 섹션 종료
  신호 아님 / 새 h1 이 섹션 종료 / 연속된 reference 헤딩 / bullet & ordered
  list 도 reference + depth=0 / 표는 섹션 안에서 passthrough / 헤딩 텍스트
  좌우 공백 strip 매치 / 내부 공백 정규화 안 함 / 헤딩 자체 role 보존 /
  입력 불변성

### ③ 스타일 룩업 — `test_styles.py` (28개)

**대상**: `mapsi/styles.py` 의 `style_name(map, role, depth) -> str`
+ `mapsi/config.py` 의 `load_style_map(path)`

`spec/styles.yaml` 의 정책 표가 잘 로드되고, `(role, depth)` 가 올바른
한/글 스타일 *이름* 으로 매핑되는지 확인. 이 단계는 ID 를 모름.

검증 케이스:
- `TestLoadStyleMap`: 13개 역할 존재 / 깊이 키 정수 정규화 / 단순 역할 값 문자열
- `TestStyleName`: 22개 역할별 이름 매핑 + unknown role/depth 에러
  + paragraph 의 depth 무시

### ④ 빌더 — `test_header.py` + `test_elements.py` + `test_bindata.py` + `test_manifest.py` (3 + 50 + 10 + 8 = 71개)

**대상**: `mapsi/builder/header.py`, `mapsi/builder/elements.py`,
`mapsi/builder/bindata.py`, `mapsi/builder/manifest.py`

#### 헤더 (`test_header.py` 3개)
- `templates/Contents/header.xml` 바이트 로드
- `parse_style_table()` 가 `name -> StyleEntry(id, paraPrIDRef, charPrIDRef)`
  매핑을 반환
- 알려진 스타일 ("본문", "개요 1" 등) 의 속성 정확성

#### 요소 (`test_elements.py` 50개)
- `build_paragraph` (8): 본문 단락 / h1~h5 헤딩 / 빈 텍스트 처리 / 필수 속성
- `TestBuildTableWrapper` (10): 표 wrapper 구조 / 본문 스타일 / 표내용 셀
  스타일 / 셀 텍스트 / cellAddr / 캡션 유무 / autoNum 패턴 (`numType=TABLE`) /
  jagged row 패딩 / 빈 rows 에러
- `TestBuildFigureParagraph` (4): Phase 6a placeholder 모드 — 그림 스타일
  단락 / alt placeholder / 빈 alt → `<hp:t>` 생략 / 필수 속성
- `TestBuildFigureCaptionParagraph` (4): 그림캡션 스타일 / autoNum
  `numType=PICTURE` / `<hp:t>그림 </hp:t><autoNum/><hp:t> 본문</hp:t>` 패턴 /
  autoNumFormat 속성
- `TestBuildFigureParagraphWithPic` (8): Phase 6b 모드 — `image_info` 가
  주어졌을 때 `hp:p > hp:run > hp:pic` 발급 / 필수 자식 노드 (offset, orgSz,
  curSz, renderingInfo, img, imgRect, imgClip, sz, pos) 존재 / `hc:img` 의
  `binaryItemIDRef` / orgSz·curSz HWPUNIT 값 / alt → `hp:shapeComment` /
  alt 없을 때 shapeComment 생략 / caption → `hp:caption` (side=BOTTOM,
  numType=PICTURE) 흡수 / caption 없을 때 hp:caption 생략
- `TestBuildParagraphWithFootnotes` (10): Phase 7 — `meta["footnote_marks"]`
  가 없을 때 평문 폴백 / 마커 1 개의 `<hp:t>/<hp:ctrl>/<hp:t>` 분할 /
  마커가 끝/시작 위치일 때 빈 hp:t 생략 / 다중 마커 교차 / offset 역순
  방어적 정렬 / 각주 본문이 'footnote'(=각주) 스타일 사용 / `number` /
  `autoNum.num` 이 `id+1` (1-base, numType=FOOTNOTE) / 본문 텍스트 앞
  공백 1 개 (한/글 표기 관습) / 정의 없는 마크도 hp:footNote 노드는 emit
- `TestEquationParagraph` (6): Phase 9 — 인라인 수식 마커가 평문 사이에
  3 개 hp:t 로 분할 / 마커가 단락 시작·끝일 때 빈 hp:t 생략 / 다중 마커
  교차 / 디스플레이 수식 단독 단락도 본문 스타일 유지 (ADR 0002) / 한
  단락에 각주+수식 동시 → NotImplementedError

#### LaTeX → HNC (`test_math.py` 29개)
- `cache.py` (14): sha256 키의 결정성 / display 모드가 키에 반영 / 16자
  hex / 환경변수 override / 기본 ~/.mapsi 경로 / 캐시 없으면 빈 dict /
  save→load 라운드트립 / 부모 디렉토리 자동 생성 / 손상 JSON 폴백 /
  비-dict top-level 폴백 / lookup miss / store→lookup / display 모드별
  분리 저장
- `converter.py` (15): 폴백 4 종 (NO_LLM 환경변수 / 키 없음 / strip 처리 /
  빈 입력) / LLM 분기 5 종 (Anthropic 단독 / OpenAI 단독 / Anthropic
  우선순위 / Anthropic 실패 → OpenAI / 둘 다 실패 → 폴백) / 캐시 2 종
  (1 회 호출 후 hit / NO_LLM 모드는 캐시 비오염) / 응답 정리 4 종 (공백
  strip / 코드 펜스 unwrap with-lang / no-lang / 평문 통과)

#### BinData (`test_bindata.py` 10개)
- `register_image` 가 ID `image1` → `image2` … 자동 증가
- 같은 src 두 번 호출해도 충돌 없음 / 기존 BinData 파일 보존
- `BinData/` 디렉토리 자동 생성 / non-image 파일 무시
- 확장자별 media-type (.png/.jpg/.jpeg) / 대소문자 정규화
- 누락 파일 → `FileNotFoundError`, 확장자 누락/미지원 → `ValueError`

#### Manifest (`test_manifest.py` 8개)
- 신규 항목 append (isEmbeded="1" 자동 부여)
- 기존 manifest 항목 (header, section0, settings) 보존
- 동일 ID 재호출 시 멱등 덮어쓰기
- 한 번에 여러 항목 추가
- 빈 entries → no-op (파일 변동 없음)
- 누락 파일 / 필수 키 누락 → 에러
- XML 선언 + UTF-8 인코딩 보존

### 오케스트레이터 — `test_converter_images.py` (6개)

**대상**: `mapsi/converter._register_figure_images` (헬퍼).

walked Block 리스트에서 figure 들의 이미지를 BinData 에 등록하고
`build_section` 에 넘길 image_map 을 구성하는 헬퍼. 끝단 변환은
`test_golden.py::06_figure_struct` 가 검증하므로, 본 파일은 경계
동작만 다룬다.

- 단일 figure → image1 발급 + 200×120 px @ 96 dpi → 15000×9000 HWPUNIT
- 같은 src 가 여러 figure 에 등장하면 BinData 복사·entries 모두 1 개로 공유
- figure 가 없으면 `BinData/` 도 만들지 않음
- 누락 src → `FileNotFoundError`
- 상대 src 가 `md_dir` 기준으로 해석됨
- `meta["src"]` 가 비면 무시 (드물지만 방어)

### ⑤ 패키저 / 스모크 — `test_smoke.py` (8개)

**대상**: `mapsi/packager.py` 의 `package_hwpx(work_dir, output)` +
전체 파이프라인이 만든 ZIP 의 형식 정합성.

스타일 정확성과는 무관, "한/글이 열 수 있는 ZIP 인가" 만 검증.

- `TestSmokePackaging` (6)
  - 출력 파일 존재 + 비어있지 않음
  - 유효한 ZIP
  - **mimetype 이 첫 엔트리이고 STORED(무압축)** ← HWPX 표준
  - 필수 5개 파일 (`mimetype`, `version.xml`, `Contents/header.xml`,
    `Contents/section0.xml`, `META-INF/container.xml`) 존재
  - mimetype 시그니처 = `application/hwp+zip`
  - `section0.xml` 이 well-formed XML
- `TestSmokeCli` (2)
  - `mapsi` 명령과 `python -m mapsi` 동일 출력
  - CLI 인자 처리

### 검사 도구 — `test_inspect.py` + `test_golden_helper.py` (12 + 6 = 18개)

**대상**: `mapsi/inspect.py` (라이브러리 + CLI), `tests/_golden.py` (얇은 어댑터)

검증 도구가 틀리면 골든 회귀 결과를 신뢰할 수 없으므로 별도 단위 테스트
필수.

- `mapsi.inspect` 라이브러리: `extract_paragraph_sequence`,
  `extract_style_id_to_name`, `filter_nonempty`
- `mapsi.inspect` CLI: 기본 출력, `--styles` 정의 요약, `--all` 빈 단락 포함,
  없는 파일 에러, 다중 파일 처리
- 각주 (Phase 7): 본문 단락의 텍스트가 `hp:footNote` 안 텍스트를 포함하지
  않음 (이중 카운트 방지) / 각주 본문이 별도 "각주" 스타일 단락으로 따로
  열거 + 본문 앞 공백 1 개 보존
- `tests/_golden.py`: `mapsi.inspect` 재익스포트 + `load_expected` 로더

### 끝단 회귀 — `test_golden.py` (9개)

**대상**: 전체 파이프라인 (`mapsi.converter.md_to_hwpx`).

`tests/golden/<name>/input.md` 를 변환하여 나온 `.hwpx` 의 단락 시퀀스를
`expected.yaml` 과 비교. 비교는 *스타일 이름* 기준 (raw ID 가 아님).
픽스처 자체에 대한 자세한 규약은 [`golden/README.md`](./golden/README.md)
참고.

현재 픽스처:
| 픽스처 | 검증 내용 |
|---|---|
| `01_headings` | 본문 + 제목 1~5 |
| `02_bullet_list` | 글머리 목록 3단계 중첩 |
| `03_ordered_list` | 번호 목록 2단계 중첩 |
| `04_blockquote_code` | 인용 + 코드 블록 (들여쓰기 보존) |
| `05_table` | GFM 표 + 캡션 승격 (ADR 0001) |
| `06_figure_struct` | 그림 + 캡션 (Phase 6b; 실 hp:pic + BinData 임베드) |
| `07_footnote` | 각주 (Phase 7; `[^id]` → `hp:footNote` 인라인 임베드) |
| `08_references` | 참고문헌 (Phase 8; "참고 문헌" 헤딩 이하 단락 → 참고문헌 스타일) |
| `09_equations` | 수식 (Phase 9; `$..$`/`$$..$$` → `[hnc 수식]…[/hnc 수식]` 평문 마커, 폴백 경로) |

---

## 공용 유틸

### `conftest.py`
세션 스코프 픽스처 4종:
- `repo_root` — 리포지토리 루트 경로
- `samples_dir` — `samples/` 경로
- `templates_dir` — `templates/` 경로
- `spec_dir` — `spec/` 경로

### `_golden.py`
`mapsi.inspect` 의 핵심 헬퍼를 재익스포트하고, `expected.yaml` 로더만
추가로 제공. 기존 테스트 호환성을 위해 유지.

### `golden/`
끝단 회귀용 입력/기대 출력 픽스처. 각 디렉토리에 `input.md` +
`expected.yaml`. 추가 절차는 [`golden/README.md`](./golden/README.md) 참조.

---

## 새 테스트를 추가할 때

1. **단위 테스트 우선** — 단계 한 곳에서 닫히는 케이스는 해당
   `test_<단계>.py` 에 추가. 새 파이프라인 단계가 생기면 새 파일 분리.
2. **회귀 테스트는 끝단** — 여러 단계가 얽힌 케이스는 `golden/<NN_name>/`
   픽스처로 추가. `test_golden.py` 가 자동 발견.
3. **검사 도구 변경** — `mapsi/inspect.py` 를 수정하면 `test_inspect.py` 와
   `test_golden_helper.py` 둘 다 손봐야 할 수 있음 (후자는 얇은 어댑터).
4. 픽스처 파일은 모두 UTF-8 / LF / front matter 없는 순수 본문.

## 자주 쓰는 명령

```bash
pytest                                  # 전부
pytest -x                               # 첫 실패에서 멈춤
pytest --collect-only -o addopts=""     # 테스트 트리 출력
pytest -k "heading and not bullet"      # 키워드 필터
pytest tests/test_parser.py::test_round_trip_01_headings_fixture
```
