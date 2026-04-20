# ADR 0002 — 수식: `hp:equation` XML 미사용, 평문 마커 모드 채택

상태: Accepted (2026-04-19, Phase 9 구현 시점)
관련: ADR 0001 (캡션/각주 흡수 패턴), 계약 7 (`spec/interfaces.md`),
A 의 `samples/incremental/09_equations/`

## 배경

마크다운의 `$ ... $` (인라인) / `$$ ... $$` (디스플레이) 수식을 한/글
HWPX 로 변환할 때, 정상 경로는 한/글의 `<hp:equation>` 요소를 emit 하는
것이다. 그러나:

1. `<hp:equation>` 은 단순 텍스트 노드가 아니라 OLE-유사 객체에 가깝다.
   `id`, `version`, `baseUnit`, `charPrIDRef`, `baseline`, `script`,
   미리보기 이미지 (`hp:image binaryItemIDRef`), `posInfo`, `size` 등 다수
   부속 정보를 정확히 채워야 한다. 한 글자라도 어긋나면 한/글이 "파일이
   손상되었습니다" 로 거부한다 (= mimetype 위반과 동일한 종류의 위험).
2. 한/글 HWPX 의 수식 스키마는 공식 문서가 부분적이며, 실제 동작은 한/글
   2024 버전 별로 미세 차이가 있다.
3. A 가 정답으로 제공한 `samples/incremental/09_equations/09_equations.hwpx`
   를 까보면 `<hp:equation>` 요소가 0 개이고, `$a^2 + b^2 = c^2$` 가 본문
   `<hp:t>` 안에 평문으로 들어 있다. 즉 *A 도 정복하지 못하고 평문으로
   회피* 한 상태다.
4. 본 프로젝트의 코어 가치 명제는 "구조 → 스타일 이름 매핑" 이지 "수식
   렌더링" 이 아니다. 수식 자동 렌더링에 며칠~주를 투자해 한/글 호환
   리스크를 떠안는 것은 v0.1 마일스톤 범위를 벗어난다.

## 결정

수식은 **평문 마커 모드** 로 변환한다. `<hp:equation>` XML 은 emit 하지
않는다.

```
입력 (마크다운):  $$ \frac{a}{b} $$
출력 (HWPX):     <hp:p styleIDRef="0">           ← 본문 스타일 유지
                   <hp:run charPrIDRef="...">
                     <hp:t>[hnc 수식]<변환 결과>[/hnc 수식]</hp:t>
                   </hp:run>
                 </hp:p>
```

`<변환 결과>` 의 내용은 `convert_equation(latex, display)` 의 반환값이며,
LLM 사용 가능 여부에 따라 두 가지 모드를 갖는다.

| 모드 조건 | `<변환 결과>` | 사용자 동작 |
|---|---|---|
| `MAPSI_NO_LLM` 설정 OR API 키 없음 | LaTeX 원문 | 한/글에서 수식 편집기 열고 LaTeX 보면서 직접 입력 |
| `ANTHROPIC_API_KEY` 또는 `OPENAI_API_KEY` 있음 | HNC 수식 문법 (LLM 변환) | 마커 안 텍스트를 복사해 수식 편집기에 붙여넣기 → 즉시 렌더링 |

LLM 호출 우선순위는 **Anthropic → OpenAI → 폴백** (계약 7 규약). 변환
결과는 `~/.mapsi/equation_cache.json` 에 `sha256(latex + "|" + str(display))[:16]`
키로 캐시한다.

## 결과

### 코드 영향

- `mapsi/parser.py`: `mdit_py_plugins.dollarmath_plugin` 활성화. `math_inline`
  토큰은 paragraph 의 `meta["equation_marks"]` (offset+latex+display=False) 로
  보존, `math_block` 토큰은 단독 paragraph (`text=""`, `meta["equation_marks"]=
  [{"offset": 0, "latex": ..., "display": True}]`) 로 발급.
- `mapsi/ast_walker.py`: 수식은 흡수 규칙 없음. 그대로 통과.
- `mapsi/builder/elements.py`: 각주와 동일한 패턴으로 `_make_run_with_equations`
  헬퍼를 추가. 마커 위치를 기준으로 텍스트와 `convert_equation` 결과를
  교차 emit.
- `mapsi/math/converter.py`: 폴백 → Anthropic → OpenAI 분기 + 캐시 lookup/
  store. API 호출 실패 시 즉시 폴백 (예외 로깅 후 흡수).
- `mapsi/math/cache.py`: `~/.mapsi/equation_cache.json` 의 read/write
  헬퍼. 디렉토리 자동 생성, JSON corrupt 시 무시하고 빈 dict 사용.
- `mapsi/cli.py`: 실행 초입에 `python-dotenv` 로 `.env` 로드 (있을 때만).
- `tests/conftest.py`: 세션 시작 시 `MAPSI_NO_LLM=1` 강제. 기존 사용자
  환경의 키가 있어도 회귀 결과는 항상 폴백 경로.

### 골든 회귀

`tests/golden/09_equations/expected.yaml` 은 폴백 경로 결과로 작성한다
(예: `[hnc 수식]a^2 + b^2 = c^2[/hnc 수식]`). LLM 모드는 비결정적이므로
끝단 회귀로 검증할 수 없고, 단위 테스트에서 `monkeypatch` 로 API 분기를
검증한다.

### 사용자 경험

```
[LLM 키 없는 사용자]
한/글에서 본문에 "[hnc 수식]\frac{a}{b}[/hnc 수식]" 평문이 보인다.
→ 본인이 수식 편집기 (Ctrl+N, M) 열고 LaTeX 해석해서 다시 입력.

[LLM 키 있는 사용자]
한/글에서 본문에 "[hnc 수식]{a} over {b}[/hnc 수식]" 평문이 보인다.
→ "{a} over {b}" 를 복사해 수식 편집기에 붙여넣기 → 한/글이 자동
  렌더링.
```

LLM 의 가치는 "수식 객체를 자동 임베드" 가 아니라 "사용자의 재입력
수고를 복붙 1 회로 줄여주는 것" 이다.

## 대안 (각하)

### A. `<hp:equation>` XML 직접 emit

장점: 사용자가 한/글에서 즉시 렌더링된 수식을 본다. UX 가 가장 깔끔.
각하 사유: 한/글 호환 리스크 (1) + 작업량 (2) + A 도 못 한 영역 (3)
모두 합쳐 v0.1 범위 초과. v0.2 의 우선 후보로 ADR 별건 발급 예정.

### B. 미니 룰베이스 LaTeX→HNC 변환기

장점: API 키 없이도 단순 수식 (`\frac`, `\sqrt`, 위첨자/아래첨자) 정도는
HNC 로 자동 변환. 사용자 복붙도 줄일 수 있음.
각하 사유: 부분 변환은 부분 실패의 원인이 된다 (사용자가 어디까지 변환됐는지
판단해야 함). 또한 LaTeX 매크로/패키지/중첩 환경의 표면적이 너무 넓어,
"단순 케이스만" 의 경계가 모호. LLM 으로 한 방에 시키는 편이 더 깔끔.

### C. LLM 만 신뢰 (폴백 없이 에러)

각하 사유: 오프라인 환경, CI, API 키 없는 팀원에게 변환 자체가 실패함.
변환기의 가용성을 LLM 에 종속시키는 것은 본 도구의 정체성과 어긋남
(코어 변환은 LLM 무관하게 항상 동작해야 한다 — 계약 7 의 폴백 규약).

## v0.2 로 미루는 항목

- `<hp:equation>` 정복 (별도 ADR + Phase 로 진행)
- 미니 룰베이스 변환기 (필요성 재검토 후)
- `$` 이스케이프 규칙 (현재는 `samples/incremental/09_equations/09_equations.md`
  의 명세대로 "범위 외" 로 고정 — 본 ADR 도 동일)
