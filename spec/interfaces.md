# Mapsi 인터페이스 계약 (v1, 동결)

본 문서는 코어 엔진(B 담당) 과 주변 인프라(C 담당) 사이의 **유일한 의존면**을
정의한다. 본 계약 외부의 함수/클래스는 자유롭게 변경 가능하며, 본 계약에
포함된 시그니처는 0.1 릴리스까지 변경하지 않는다.

> 본 프로젝트 현재 단계에서는 C 부재로 B 가 C 영역까지 임시 구현(스텁)을
> 박아둔다. 단, 인터페이스 계약은 본 문서의 정의를 그대로 따른다.

---

## 0. 일반 규약

### 0.1. 식별자 컨벤션

- 모든 함수/변수/클래스/모듈/디렉토리 식별자는 **영문 snake_case / PascalCase**
- YAML 키, 사용자 노출 문자열(스타일 이름 "본문" 등), docstring/주석/커밋 메시지는 한국어 OK

### 0.2. 작업 디렉토리(work_dir) 의 수명주기

- `work_dir` 은 **호출자가 만들고 호출자가 정리**한다. 권장 방식은 `tempfile.TemporaryDirectory()` 컨텍스트
- `md_to_hwpx()` 는 `work_dir` 내부에 다음 구조를 채운다 (HWPX 의 OEBPS 레이아웃)

```
work_dir/
├── mimetype                ← templates/ 에서 복사
├── version.xml             ← templates/ 에서 복사
├── settings.xml            ← 부트스트랩에서 복사
├── META-INF/               ← templates/ 에서 복사
└── Contents/
    ├── header.xml          ← templates/Contents/header.xml 그대로 복사
    ├── section0.xml        ← B 의 빌더가 생성
    └── content.hpf         ← 부트스트랩에서 복사 후 manifest 갱신
└── BinData/                ← 이미지가 있을 때만 (C 의 register_image 가 생성)
```

- `md_to_hwpx()` 는 `work_dir` 자체를 mkdir 하지도, rmtree 하지도 않는다
- 마지막으로 `package_hwpx(work_dir, output_path)` 가 work_dir 내용을 ZIP 으로 패키징

### 0.3. 경로 인자

모든 경로 인자는 `str` 또는 `pathlib.Path` 호환을 받지만, 본 문서는 시그니처를 `str`로 표기한다. 구현은 내부에서 `Path(...)` 로 정규화한다.

---

## 1. C 가 구현 → B 가 호출

### 계약 1. `load_style_map`

```python
def load_style_map(yaml_path: str) -> dict:
    """`spec/styles.yaml` 을 로드해 스타일 매핑 딕셔너리를 반환한다.

    반환 구조는 spec/styles.yaml 의 키 구조를 그대로 유지하되,
    heading / bullet_list / ordered_list 의 깊이 키는 정수로 정규화한다.
    예) {"heading": {1: {"name": "개요 1", "id": 4}, ...}, ...}
    """
```

- 위치: `mapsi/config.py`
- 호출처: `mapsi/cli.py`(C) → `mapsi/converter.py`(B) 에 인자로 전달

### 계약 2. `package_hwpx`

```python
def package_hwpx(work_dir: str, output_path: str) -> None:
    """work_dir 의 내용을 HWPX(ZIP) 으로 패키징해 output_path 에 쓴다.

    제약:
      - mimetype 을 ZIP 의 첫 엔트리로, **무압축(STORED)** 으로 저장
      - mimetype 의 extra field 는 비워둠
      - 그 외 모든 파일은 DEFLATE 로 압축
      - work_dir 자체는 변형하지 않으며, 함수 종료 후에도 보존
    """
```

- 위치: `mapsi/packager.py`
- 호출처: `mapsi/converter.py`(B) 의 마지막 단계

### 계약 3. `register_image`

```python
def register_image(src_path: str, work_dir: str) -> tuple[str, dict]:
    """원본 이미지를 work_dir/BinData/ 로 복사하고 고유 binary_item_id 를 발급한다.

    반환:
      (binary_item_id, manifest_entry)
      - binary_item_id: header.xml 의 hp:img 가 참조할 ID 문자열
      - manifest_entry: content.hpf 의 opf:manifest 에 추가할 항목 dict
        키: id, href, media-type
    """
```

- 위치: `mapsi/builder/bindata.py`
- 호출처: `mapsi/builder/elements.py`(B) 의 그림 빌더

### 계약 4. `update_manifest`

```python
def update_manifest(content_hpf_path: str, entries: list[dict]) -> None:
    """content.hpf 의 opf:manifest 를 in-place 로 갱신한다.

    entries 의 각 dict 는 id, href, media-type 키를 갖는다.
    이미 동일 id 의 항목이 있으면 덮어쓰며, 없으면 추가한다.
    spine 은 변경하지 않는다.
    """
```

- 위치: `mapsi/builder/manifest.py`
- 호출처: `mapsi/converter.py`(B) — 모든 이미지 등록이 끝난 뒤 한 번 호출

### 계약 5. `main`

```python
def main(argv: list[str]) -> int:
    """CLI 엔트리포인트. 종료 코드를 반환한다 (0 = 성공).

    인자:
      mapsi [--style-map PATH] [--verbose] [--no-llm] [--dry-run] INPUT.md -o OUTPUT.hwpx

    내부 동작:
      1) argparse 로 argv 파싱
      2) load_style_map(--style-map) 으로 스타일 매핑 로드
      3) tempfile.TemporaryDirectory() 로 work_dir 생성
      4) md_to_hwpx(input, output, style_map, work_dir) 호출
    """
```

- 위치: `mapsi/cli.py`

### 계약 7. `convert_equation`  *(LLM/캐시 의존부 격리)*

```python
def convert_equation(latex: str, display: bool) -> str:
    """LaTeX 수식을 한/글 HNC 수식 문법으로 변환한다.

    동작:
      1) 환경변수에 ANTHROPIC_API_KEY 가 있으면 Anthropic API 호출
      2) 없고 OPENAI_API_KEY 가 있으면 OpenAI API 호출
      3) 둘 다 없거나 호출 실패 시 폴백:
           반환값 = "[hnc 수식]" + latex + "[/hnc 수식]"
      4) 성공 시 ~/.mapsi/equation_cache.json 에 (sha256(latex)[:16] → result) 캐시
    """
```

- 위치: `mapsi/math/converter.py`
- 호출처: `mapsi/builder/equation.py`(B)

---

## 2. B 가 구현 → C 가 호출

### 계약 6. `md_to_hwpx`

```python
def md_to_hwpx(
    md_path: str,
    output_path: str,
    style_map: dict,
    work_dir: str,
) -> None:
    """마크다운 파일을 HWPX 로 변환한다. 변환 파이프라인의 코어 진입점.

    파이프라인 (5 단계):
      1) parser.parse_markdown(md_path) → list[Block]
      2) ast_walker.walk(blocks) → 문맥 의존 규칙 적용 (캡션 승격 등)
      3) builder.section.build_section(walked, style_map) → section0.xml 문자열
      4) work_dir 부트스트랩 (templates/ + base 부트스트랩 복사) 후
         생성된 section0.xml 을 work_dir/Contents/section0.xml 로 기록
      5) packager.package_hwpx(work_dir, output_path) 호출
    """
```

- 위치: `mapsi/converter.py`
- 호출처: `mapsi/cli.py`(C)

---

## 3. 변경 절차

본 계약을 변경해야 하는 경우, 다음 순서를 따른다.

1. B 가 변경 사유와 영향 범위를 PR 본문에 명시
2. C 영역 호출처(현 단계는 동일 인물) 의 동시 수정 포함
3. `tests/` 의 회귀가 통과해야 머지 가능
4. 본 문서의 해당 계약 섹션을 동일 PR 에서 갱신
