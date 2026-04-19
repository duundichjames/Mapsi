# Mapsi

Markdown Adapter for Paragraph-Style Injection

마크다운 문서를 한/글 HWPX 로 변환하면서 각 단락에 적절한 hwpx 스타일을
자동으로 부여하는 변환기이다. "맵시" 는 "모양새, 차림새" 를 뜻하는 한국어이며,
본 프로젝트는 마크다운의 구조를 hwpx 의 스타일로 맵시 있게 옮기는 도구이다.

## 설치

목적에 따라 둘 중 하나를 선택한다.

```bash
# 변환기만 사용 (런타임 의존성: markdown-it-py, mdit-py-plugins, lxml, pyyaml, Pillow)
pip install -e .

# + 수식 LLM 변환 (anthropic, openai, python-dotenv 추가 설치)
pip install -e ".[llm]"

# 개발 / 테스트까지 (위 + pytest, pytest-cov 추가 설치)
pip install -e ".[dev]"

# LLM + 개발 모두
pip install -e ".[llm,dev]"
```

`.[dev]` / `.[llm,dev]` 의 대괄호는 `pyproject.toml` 의
`optional-dependencies.*` 묶음을 가리킨다. zsh 에서는 글로빙 충돌을 막기
위해 따옴표가 필요하다.

### 수식 변환 (선택)

`.md` 안의 `$ ... $` (인라인) / `$$ ... $$` (디스플레이) LaTeX 수식은
본문에 `[hnc 수식]<HNC 스크립트>[/hnc 수식]` 평문 마커로 박힌다 (자세한
배경은 [ADR 0002](docs/decisions/0002-equation-marker-mode.md)).

마커 안 본문은 LLM 키 유무에 따라 결정된다:

| 환경 | 마커 안 본문 | 사용자 동작 |
|---|---|---|
| `MAPSI_NO_LLM=1` 또는 키 없음 | LaTeX 원문 | 한/글 수식 편집기에서 LaTeX 보고 직접 입력 |
| `ANTHROPIC_API_KEY` 또는 `OPENAI_API_KEY` 설정 | HNC 수식 문법 | 마커 안 텍스트 복사 → 한/글 수식 편집기에 붙여넣기 → 즉시 렌더링 |

키는 셸 환경 변수에 직접 두거나, 프로젝트 루트의 `.env` 에 적어 두면
CLI 가 `python-dotenv` 로 자동 로드한다 (`mapsi[llm]` 설치 시):

```dotenv
# .env
ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...    # 둘 다 있으면 Anthropic 우선
```

CLI 옵션으로 일회성으로 LLM 을 끌 수도 있다:

```bash
mapsi input.md -o out.hwpx --no-llm
```

## 사용

### 변환

```bash
mapsi input.md -o output.hwpx
# 또는
python -m mapsi input.md -o output.hwpx


# LLM 끄기 (수식을 LaTeX 원문 그대로)
mapsi input.md -o output.hwpx --no-llm

# 무슨 일이 일어나는지 자세히 보기
mapsi input.md -o output.hwpx --verbose
```

### 검증 — 변환 결과가 의도대로인지 확인

한/글(정품) 없이 셸에서 변환 결과를 1초에 점검하는 도구가 함께 제공된다.
한글 뷰어(무료) 는 스타일 표시줄이 없어 시각 검증이 어렵기 때문에,
**구조적 정확성** 은 본 도구로 확인하고 시각 스타일은 정품 한/글에서
열어 조정하는 워크플로를 권장한다.

```bash
# 단락별 (스타일 이름, 텍스트) 시퀀스 출력
python -m mapsi.inspect output.hwpx

# 사용된 스타일 정의 요약 + 정합성 점검까지
python -m mapsi.inspect output.hwpx --styles

# 여러 파일을 한 번에
python -m mapsi.inspect output/*.hwpx
```

출력 예시:

```
=== output/04_blockquote_code.hwpx ===
    1. [ 본문 ] id=3   아래는 인용문 예시입니다.
    2. [ 인용 ] id=8   진실은 단순함이라는 옷을 입고 나타난다.
    3. [ 인용 ] id=8   — 익명
    4. [ 본문 ] id=3   이어서 코드 예시를 보입니다.
    5. [ 코드 ] id=9   def greet(name):
    6. [ 코드 ] id=9       print(f"Hello, {name}!")
    7. [ 코드 ] id=9   greet("Mapsi")
    8. [ 본문 ] id=3   마무리 평문 단락입니다.

[사용된 스타일 정의]
  styleIDRef=0    바탕글
  styleIDRef=3    본문
  styleIDRef=8    인용
  styleIDRef=9    코드

[정합성]
  OK 모든 styleIDRef 가 header.xml 에 정의되어 있다
  ㆍ 본문에 등장한 스타일 4 종 / header.xml 의 스타일 정의 37 종
```

### 테스트

```bash
pytest                          # 전체 (현재 275개)
pytest tests/test_golden.py -v  # 골든 회귀만
```

세션 시작 시 `tests/conftest.py` 가 `MAPSI_NO_LLM=1` 을 강제 설정해, 키가
있어도 회귀는 항상 폴백 (LaTeX 원문) 경로를 탄다. 캐시 경로도 임시
디렉토리로 격리해 사용자의 `~/.mapsi/equation_cache.json` 을 오염시키지
않는다.

## 디자인 철학

마크다운의 **구조적 역할** 을 한/글 **스타일 이름** 에 매핑한다.
시각 속성(폰트·색·들여쓰기) 은 결정하지 않는다 — 그건 사용자가 한/글의
스타일 편집기에서 일괄 조정하면 된다.

진실원 분리:

- `spec/styles.yaml` — 정책 (역할 → 한/글 스타일 이름)
- `templates/Contents/header.xml` — 한/글이 정의한 스타일 사실
  (이름 → id, paraPrIDRef, charPrIDRef)

빌더는 둘을 이름으로 조인해 본문 XML 에 ID 를 박는다.

## 라이선스

MIT License
자세한 프로젝트 계획은 docs/project_plan.md 를 참조한다.

## 개발자 문서

- [프로젝트 전체 계획](docs/project_plan.md)
- [개발자 핸드오프 문서](docs/developer_handoff.md) — B 가 무엇을 어떻게 하는지
- [Team C 핸드오프 문서](docs/c_handoff.md) — C 영역 (이미지/매니페스트/패키지)
- [API 인터페이스 명세](spec/interfaces.md) — B ↔ C 계약
- [골든 회귀 테스트 가이드](tests/golden/README.md)
