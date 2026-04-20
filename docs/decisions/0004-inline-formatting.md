# ADR 0004 — Phase 10 인라인 서식 정책

상태: Accepted (2026-04-21, `feature/core-engine` 시점)
관련: ADR 0001 (캡션 승격), ADR 0002 (수식 마커 모드), ADR 0003 (Team C 통합),
`spec/styles.yaml`, `templates/Contents/header.xml`,
`mapsi/parser.py`, `mapsi/builder/elements.py`

## 배경

Phase 1~9 까지 Mapsi 의 빌더는 **한 단락 = `<hp:run>` 1개** 만 emit
했다 (각주/수식 같은 ctrl/marker 가 끼어도 charPr 는 단일). 그래서
한 단락 안의 글자모양은 `styles.yaml` 의 단일 매핑 1 개 (예: `paragraph`
→ "본문" → charPrIDRef=7) 로 고정됐고, 마크다운의 인라인 서식
(`**bold**`, `*italic*`, `~~strike~~`, `` `code` ``, `[label](url)`) 은
**평문으로 흡수돼 사라졌다** (parser 의 `_inline_to_text_and_marks` 가
조용히 드롭).

Phase 10 은 인라인 서식을 살리는 작업인데, 한컴 HWPX 의 모델이
강제하는 4 가지 결정이 있어 본 ADR 로 못 박는다.

## 결정

### 결정 1 — 링크: 라벨 + URL 을 HYPERLINK 필드로 보존 (v0.1.2 갱신)

**v0.1 (초안)**: 라벨만 평문으로 보존, URL 폐기.
**v0.1.1 (2026-04-19)**: URL 을 `<hp:fieldBegin @name=URL>` 축약형으로 보존
(python-hwpx `add_hyperlink` 와 동일). → 한/글에서 열었을 때 **클릭이
활성화되지 않는 문제** 발견.
**v0.1.2 (현행, 2026-04-19)**: 한/글이 직접 저장한 정식 HWPX (참고:
`python-hwpx/shared/hwpx/fixtures/fields/10_fieldcodes_min.hwpx`) 에서
관찰되는 *파라미터 블록 형태* 로 교체. 외부 URL 클릭이 한/글 에디터 및
뷰어 모두에서 실제 동작하도록 보장한다.

최종 emit 구조 (v0.1.2)::

    <hp:run charPrIDRef="30">
      <hp:ctrl>
        <hp:fieldBegin id="<A>" type="HYPERLINK" name=""
                       editable="0" dirty="1"
                       zorder="-1" fieldid="<B>" metaTag="">
          <hp:parameters cnt="7" name="">
            <hp:integerParam name="Prop">0</hp:integerParam>
            <hp:stringParam name="Command"><ESC_URL>|<TT>;1;0;0;</hp:stringParam>
            <hp:stringParam name="Path"><URL></hp:stringParam>
            <hp:stringParam name="Category"><HWPHYPERLINK_TYPE_*></hp:stringParam>
            <hp:stringParam name="TargetType">HWPHYPERLINK_TARGET_BOOKMARK</hp:stringParam>
            <hp:stringParam name="DocOpenType">HWPHYPERLINK_JUMP_CURRENTTAB</hp:stringParam>
            <hp:stringParam name="ToolTip"><TT></hp:stringParam>
          </hp:parameters>
        </hp:fieldBegin>
      </hp:ctrl>
    </hp:run>
    <hp:run charPrIDRef="30"><hp:t>라벨</hp:t></hp:run>
    <hp:run charPrIDRef="30">
      <hp:ctrl><hp:fieldEnd beginIDRef="<A>" fieldid="<B>"/></hp:ctrl>
      <hp:t/>
    </hp:run>

- `id` (= fieldBegin 식별자) 와 `fieldid` (= 같은 필드의 instId) 는 각각
  독립 난수이지만 `fieldEnd/@beginIDRef` 와 `fieldEnd/@fieldid` 로 *두 쌍*
  모두 일치시켜야 한/글이 유효 필드로 인식한다.
- `Command` 값의 `:` 는 한/글 규약상 `\:` 로 escape (URL 의 스키마 구분자가
  필드 구분자 `|` 와 혼동되지 않도록). `Path` 에는 escape 하지 않은 원
  URL 을 그대로 둔다 (실제 열기에 사용되는 값).
- `Category` 는 URL 모양으로 결정: `#...` → `HWPHYPERLINK_TYPE_BOOKMARK`,
  그 외 → `HWPHYPERLINK_TYPE_URL`.
- `fieldEnd` 직후의 빈 `<hp:t/>` 는 한/글 파서 호환을 위해 필수.

`charPrIDRef="30"` 은 본 ADR 의 결정 4 항목과 별도로 추가한 **하이퍼링크
전용 charPr** (파란 글자 `#0563C1` + underline SOLID `#0563C1`) 이다.

처리 대상 링크 종류:

- 인라인 `[라벨](URL)`
- 베어 URL `https://...` (markdown-it `linkify` 확장으로 자동 링크)
- autolink `<https://...>`
- 이메일 `foo@bar.com` → `mailto:foo@bar.com` 으로 정규화됨
- 내부 앵커 `[라벨](#section)` — URL 은 그대로 보존하지만 **클릭 시 점프는
  구현하지 않는다**. 한/글이 `#section` 을 북마크로 해석하려면 별도
  `<hp:bookmark>` 앵커가 문서에 존재해야 하며, 자동 앵커 생성은 v0.3 로
  deferred.
- 상대 파일 링크 `[라벨](./foo.pdf)` — 동일하게 URL 보존만, 실동작 보증 X.

근거 (승격을 단행한 이유):

- Streamlit UI 통합 과정에서 *클릭 가능한 하이퍼링크* 가 학술문서 품질의
  최소 요구로 부상 (cp4_full 1 문서에만 외부 URL 6 개).
- `<hp:fieldBegin type="HYPERLINK">` + `<hp:fieldEnd beginIDRef="...">`
  구조가 한/글 본가 출력과 타 라이브러리 (python-hwpx) 에서 동일 형태로
  검증됨 → 필드 모델 마이그레이션이 초기 예상보다 가볍다 (ID 쌍 + 1 attr).
- 시각 (파랑+밑줄) 과 의미 (`fieldBegin/End`) 를 동시에 해결할 수 있어
  v0.2 에서 재작업을 피함.

링크 + 다른 인라인 마크 겹침 정책 (결정 4 와 구별):
**링크 charPr 가 이긴다.** `**[굵은링크](url)**` 같은 경우에도 해당 세그먼트는
`charPrIDRef=30` 단일로 emit 한다 (bold 시각 서식은 떨어뜨리고 클릭 가능성을
우선 보존). 이유는 클릭 가능성이 "굵게 + 파랑 밑줄" 을 동시에 그리는 조합
charPr 를 사전 등록하는 비용보다 훨씬 중요하기 때문 (결정 4 의 디그레이드
우선순위와 유사한 프래그마틱 선택).

side-effect 및 경계:

- 빈 라벨 `[](url)` 은 파서가 mark 등재 자체를 스킵 (start==end 이거나 url
  검증 실패) → 평문 0 자 처리 (현행 유지).
- URL 이 빈 문자열인 경우 빌더가 필드를 만들지 않고 평문만 emit (회귀
  방지용 가드; `test_empty_url_link_ignored`).

v0.2 이후 deferred:

- 내부 앵커 (`#section`) 점프: 문서 스캐너가 heading → `<hp:bookmark>` 자동
  등재 후 링크 `name` 을 북마크 이름과 매핑해야 함.
- 상대 파일 링크의 실제 리소스 임베드.

### 결정 2 — Inline code: 모노스페이스 폰트는 코드 블록 폰트 재사용

`` `code` `` 의 charPr 는 본문 charPr (id=7) 의 형틀에 다음만 변경:

- `fontRef`: `hangul="1" latin="2"` (코드 블록 charPr id=4 와 동일)
  — 이미 한/글 템플릿에 등록된 모노스페이스 fontface 인덱스이므로
  **새 fontface 추가 불필요**.
- `shadeColor="#F5F5F5"` (옅은 회색 음영, 코드 가독성 향상)

근거:

- 새 fontface 추가 시 `<hh:fontfaces lang="HANGUL">` / `lang="LATIN">`
  양쪽에 entry 추가 + `itemCnt` 갱신 + 기존 fontRef 인덱스 재계산
  필요 → 회귀 위험 큼.
- 이미 `templates/Contents/header.xml` 의 코드 블록이 채택한 한글/라틴
  모노스페이스 인덱스를 그대로 재사용하면 Phase 9 의 코드 블록 출력과
  inline code 의 시각적 일관성도 자연스럽게 확보된다.

비결정 (의도): `borderFillIDRef` 로 글자 박스를 두르는 옵션은 채택하지
않는다 (한/글이 inline 박스를 그릴 때 줄높이를 비균일하게 늘려 본문
줄간격을 흔들 수 있음). 음영만으로 충분한 가독성 확보.

### 결정 3 — 중첩 마크업: 조합 charPr 사전 등록

`***bold italic***` 처럼 마크가 겹치면 `<hh:bold/>` + `<hh:italic/>` 가
**둘 다** 들어간 단일 charPr 1 개를 사용한다 (런타임에 charPr 를 동적
조립하지 않음).

근거:

- `<hh:charPr>` 는 한/글 헤더의 정적 사전이고, 한 `<hp:run>` 의
  `charPrIDRef` 는 정수 1 개. 동적 조립 (예: bold 한 charPr 와 italic 한
  charPr 를 "겹치는" 의미) 은 HWPML 모델에 존재하지 않는다.
- 대신 **자주 쓰는 조합만 미리 등록** 하고, 빌더가 인라인 마크 집합을
  키로 lookup 한다. 등록 안 된 조합 (예: bold + strike + italic) 은
  *디그레이드 정책* 으로 가장 가까운 조합 charPr 로 매핑하거나
  (문서화된) 우선순위 (bold > italic > strike) 를 적용한다.
- v0.1 등록 대상 5 종 (결정 4 참조) 만으로 마크다운 사용 빈도 95%+ 커버.

### 결정 4 — charPr 사전 등록 5 종 (link 제외)

`templates/Contents/header.xml` 의 `<hh:charProperties>` 에 신규 5 개
추가, `itemCnt="25"` → `itemCnt="30"`.

| 신규 ID | 의미 | 베이스 | 변경점 |
|---|---|---|---|
| 25 | `bold` | charPr 7 (본문) | + `<hh:bold/>` |
| 26 | `italic` | charPr 7 | + `<hh:italic/>` |
| 27 | `bold_italic` | charPr 7 | + `<hh:bold/>` + `<hh:italic/>` |
| 28 | `strike` | charPr 7 | `<hh:strikeout shape="SOLID"/>` |
| 29 | `code_inline` | charPr 7 | fontRef latin/hangul 1·2, `shadeColor="#F5F5F5"` |

룩업 테이블은 신규 모듈 `mapsi/inline_styles.py` 에 dict 로 둔다 (코드
내부 상수). `spec/styles.yaml` 은 *문단* 역할 매핑 전용으로 유지
(인라인 글자 매핑까지 yaml 로 끌어올리면 사용자가 만지기 쉬워지나,
header.xml 의 신규 charPr ID 와 강결합되어 진실원 단일성 정책에 위배).

**디그레이드 정책 (등록 안 된 조합)**:

- 조합 키가 사전에 없으면 **마크 1 개씩 우선순위 (bold > italic > strike
  > code) 로 fallback**. 예: `{bold, italic, strike}` → `{bold, italic}`
  (=27) 사용. 시각적 손실은 strike 1 개. 평문이 **사라지지는 않는다**.
- link 마크는 조합 룩업 테이블에서 항상 제외 — 룩업 시 silent drop. 단
  빌더 경로는 link 를 별도로 인식해 하이퍼링크 charPr (id=30) 와
  `<hp:fieldBegin/fieldEnd>` 쌍으로 분리 처리 (결정 1 v0.1.1 참조).

## 영향

- `mapsi/parser.py`: `_inline_to_text_and_marks` 가 `strong` / `em` /
  `s` / `code_inline` / `link` 토큰을 수집해 `meta["inline_marks"]` 에
  `[{start, end, kind, [url]}, ...]` 로 저장. `link` 는 `url` 필드를 함께
  싣고, `MarkdownIt("commonmark", {"linkify": True}).enable("linkify")` 로
  베어 URL · 이메일도 link 로 자동 전환 (v0.1.1).
- `mapsi/inline_styles.py` (신규): `INLINE_CHARPR` dict + `resolve_charpr`
  함수. 빌더가 mark 집합 `frozenset({"bold", "italic"})` 를 키로 charPr ID
  문자열을 받아간다.
- `mapsi/builder/elements.py`: `_make_run_with_inline_marks` 신규
  추가. `build_paragraph` 의 디스패치 분기에 (`inline_marks` 가 있으면)
  새 함수 호출. equation/footnote 와 inline_marks 가 동시에 있는 경우는
  v0.1 범위 외 (현행 `NotImplementedError` 정책 유지).
- `templates/Contents/header.xml`: charPr 5 개 추가 + `itemCnt` 갱신.
  기존 charPr 0~24 는 한 글자도 건드리지 않는다 (회귀 안전).
- 골든: `samples/incremental/10_inline/10_inline.md` 신규 추가 + 동명
  `.hwpx` 골든. CP3 통합 픽스처 (`samples/base/base.md`) 도 인라인 마크
  몇 개 보강해 회귀 안전망 강화.

## 회피 (안 한 것 + 이유)

- **링크의 정식 hyperlink field 구현**: 본 ADR v0.1.1 에서 결정 1 로 승격
  완료 (별도 ADR 분리 불필요).
- **내부 앵커 점프**: v0.3 에서 heading → `<hp:bookmark>` 자동 등재와 함께
  구현. 현재는 URL fragment 를 메타로만 보존.
- **inline 박스 (borderFill)**: 결정 2 의 비결정 절 참조. 음영만 사용.
- **인라인 색상 / 형광펜**: v0.1 마크다운 표준 문법에 없음. 확장
  마크다운 (`==highlight==`) 은 v0.3 이후.
- **상첨자/하첨자 (`<sup>` / `<sub>`)**: 마크다운 표준 외 HTML. 본
  ADR 범위 외.
- **`<hp:fieldBegin>` 기반 메모/주석**: 메모 역할은 별도 단락
  (`role="memo"`) 으로 처리하는 기존 정책 유지.

## 결과

본 ADR 의 5 개 charPr 등록 + 룩업 테이블 + 파서/빌더 변경으로
v0.1 인라인 서식 5 종 (`**`, `*`, `~~`, `` ` ``, `[]()`) 이 한/글
본가 출력과 호환 가능한 수준으로 보존된다. 회귀는 0 건이어야 한다
(기존 charPr 0~24 불변, 단락에 인라인 마크가 없으면 신규 코드 경로
미진입).
