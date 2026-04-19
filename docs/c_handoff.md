# Mapsi 개발자 C 인수인계

본 문서는 주변 인프라(패키징, I/O, CLI, 이미지, 수식 LLM, 통합 테스트) 를
담당하는 개발자 C 에게 작업 착수에 필요한 정보를 전달하기 위한 온보딩
자료임. 프로젝트 전체 계획은 [project_plan.md](project_plan.md) 에,
B 의 인수인계는 [developer_handoff.md](developer_handoff.md) 에 있으며,
본 문서는 그 중 C 의 작업에 직결되는 부분만 발췌함.

---

## 1. 5 분 요약

### 1.1. 프로젝트가 하는 것

마크다운 문서를 한/글 HWPX 로 변환한다. 단, 변환기는 시각 속성(폰트/색/
들여쓰기) 을 결정하지 않는다. 변환기의 책임은 마크다운의 모든 구조 단위에
**올바른 HWPX 스타일 ID 이름표를 부착하는 것까지**이며, 시각 조정은
사용자가 한/글 스타일 편집창에서 수행한다.

### 1.2. 분업

- **B**: 코어 엔진(파서, 빌더, 디스패처). `mapsi/parser.py`, `mapsi/ast_walker.py`,
  `mapsi/styles.py`, `mapsi/converter.py`, `mapsi/builder/section.py`,
  `mapsi/builder/elements.py`, `mapsi/builder/header.py`, `mapsi/builder/equation.py`
- **C**: 주변 인프라. CLI, 패키저, 설정 로더, 이미지 등록, manifest 갱신,
  수식 LLM 호출, 통합 테스트 (= **본 문서의 주제**)

두 사람의 경계는 [`spec/interfaces.md`](../spec/interfaces.md) 의 7 개
함수 시그니처로 완전히 정의되어 있고, 이 계약은 0.1 릴리스까지 변경하지 않는다.

### 1.3. 현재 상태 (C 합류 시점)

- 체크포인트 1 통과 (빈 마크다운 → 한/글 오픈 확인)
- B 가 C 영역까지 임시로 모든 파일에 스텁 또는 동작 구현을 박아둠
- 작업 브랜치 `feature/core-engine` 에 누적 (heading/list/blockquote/code/
  table/figure/footnote/reference 까지 머지됨)
- 테스트 231/231 통과 (체크포인트 1 + 04_blockquote_code + 05_table +
  06_figure + 07_footnote + 08_references 까지)
- 그림은 2 단계로 분리 진행됐고 둘 다 완료:
  - **Phase 6a (완료)** — 파서/walker/빌더가 그림 단락과 캡션을 인식.
    이미지 바이너리 임베드 없음, `그림` 스타일의 자리표시 단락 + 별도
    `그림캡션` 단락 emit (단위 테스트 호환을 위해 `image_info=None` 경로
    로 보존됨)
  - **Phase 6b (완료)** — 실제 `hp:pic` XML + `BinData/` 복사 +
    `content.hpf` manifest 패치 모두 동작. 계약 3 `register_image` 와
    계약 4 `update_manifest` 가 B 임시 구현으로 채워져 있음
    (`mapsi/builder/bindata.py`, `mapsi/builder/manifest.py`). C 가
    프로덕션 품질로 재작성하면 됨 — 인터페이스만 같으면 코어 변경 없음
- 각주 (Pandoc 확장 `[^id]`): `mdit-py-plugins.footnote` 플러그인으로 파싱.
  본문 단락 안에 `hp:footNote` 노드를 인라인 임베드 (한/글 본가 출력과
  동일 구조). 원문 라벨은 무시되고 등장 순서로 1, 2, 3 ... 자동 부여.
  자세한 구조는 `mapsi/builder/elements.py` 의 `_build_footnote` docstring
  참고.
- 참고문헌 (Phase 8): 깊이 1 헤딩의 텍스트가 4 가지 후보 (`참고문헌`,
  `참고 문헌`, `References`, `REFERENCES`) 중 하나면 그 이후 `paragraph` /
  `bullet_list` / `ordered_list` 가 `참고문헌` 스타일로 재할당된다 (다음
  깊이 1 헤딩이 등장하기 전까지). 헤딩 자체의 스타일은 보존 (= 개요 1).
  구현은 `mapsi/ast_walker.py::_demote_in_reference_section`, 빌더는 추가
  변경 없이 `style_name(role="reference")` 룩업 1 번으로 처리됨.
- 결정 기록은 `docs/decisions/` (현재 `0001-table-caption-promotion.md` 1 건,
  그림 캡션 정책도 동일 ADR 의 일반화 적용)

---

## 2. 먼저 읽어야 할 자료 (권장 순서, 30 분)

1. `README.md` (5 분)
2. `docs/project_plan.md` 의 §"프로젝트 개요", §"팀 구성과 역할 원칙",
   §"모듈 구조 - C 담당 범위 상세" (10 분)
3. `spec/interfaces.md` 전체 (10 분, **★ 가장 중요 ★**)
4. `samples/base/unpacked/` 의 파일 구조 직접 둘러보기 (5 분)
   - mimetype, version.xml, META-INF/\*, Contents/{header,section0,content.hpf}
   - 한/글이 .hwpx 라고 부르지만 실체는 ZIP 파일임을 눈으로 확인

---

## 3. C 가 담당하는 파일

### 3.1. 이미 동작 중 (B 가 임시 구현, C 가 검토 후 인수)

C 가 와서 가장 먼저 할 일은 **본인 영역의 임시 구현을 검토하고 동의**
하는 것임. 구조나 네이밍이 마음에 안 들면 인터페이스(시그니처) 만 안 깨면서
내부 구현을 갈아엎어도 됨.

| 파일 | 책임 | 계약 | 상태 |
|------|------|------|------|
| `mapsi/cli.py` | argparse, 진입점 | 계약 5 | 동작 (기본 옵션만) |
| `mapsi/config.py` | styles.yaml 로더 | 계약 1 | 동작 (깊이 키 정수 정규화 포함) |
| `mapsi/packager.py` | ZIP 패키징 (mimetype STORED 보장) | 계약 2 | 동작 |

검토 시 체크 포인트:
- `cli.py`: `--style-map`, `--no-llm`, `--dry-run`, `--verbose` 옵션 정비 필요
- `packager.py`: `.DS_Store` 제외 처리만 들어있음, 다른 OS 부산물 추가 필요 시 확장
- `config.py`: 잘못된 YAML 입력 시의 에러 메시지 보강 검토

### 3.2. 본격 구현 필요 (현재는 NotImplementedError 또는 폴백 스텁)

| 파일 | 책임 | 계약 | 우선순위 |
|------|------|------|----------|
| `mapsi/builder/bindata.py` | 이미지의 BinData/ 복사, 고유 ID 발급, NFC 정규화 | 계약 3 | 중 |
| `mapsi/builder/manifest.py` | content.hpf 의 opf:manifest 항목 추가 | 계약 4 | 중 |
| `mapsi/math/converter.py` | LaTeX → HNC 수식 변환 (LLM 호출) | 계약 7 | 하 |
| `mapsi/math/cache.py` | 변환 결과 로컬 JSON 캐시 (I/O 헬퍼는 동작 중, 호출자만 붙이면 됨) | — | 하 |

### 3.3. 새로 작성 (테스트)

| 파일 | 내용 |
|------|------|
| `tests/test_packager.py` | mimetype 첫 엔트리 + STORED 검증, 다양한 work_dir 입력 |
| `tests/test_bindata.py` | 이미지 등록, NFC 정규화, 중복 등록 처리 |
| `tests/test_manifest.py` | content.hpf 항목 추가/덮어쓰기 |
| `tests/test_math.py` | 폴백 동작, 캐시 적중, API 키 우선순위 |
| `tests/test_integration.py` | 실제 학술 문서 분량의 통합 시나리오 (CP4 단계) |

---

## 4. 주의 사항 (이걸 모르면 시간 낭비)

### 4.1. mimetype 의 무압축 첫 엔트리 강제

HWPX(=ZIP) 의 첫 엔트리는 반드시 `mimetype` 이고, **무압축(STORED)** 이어야 함.
이게 깨지면 한/글이 파일을 못 엶 (개발자 핸드오프 §시나리오 4 의 95% 원인).
`packager.py` 의 임시 구현은 이 규칙을 지키도록 작성되어 있으므로 갈아엎을 때
이 동작을 보존할 것.

### 4.2. 한국어 파일명의 NFD 정규화

macOS 의 한국어 파일명은 NFD(분해형) 유니코드로 저장됨. 한/글의 파일명
기대 형식은 NFC(조합형) 가능성이 높음. `register_image()` 내부에서
`unicodedata.normalize("NFC", ...)` 적용 필수.

### 4.3. work_dir 의 수명주기 (= 호출자가 만들고 호출자가 정리)

- `cli.py` 가 `tempfile.TemporaryDirectory()` 로 만들고
- 함수 종료 시 `__exit__` 가 자동 정리
- `md_to_hwpx()` 와 `package_hwpx()` 는 work_dir 자체를 mkdir 하거나 rmtree 하지 않음
- 이 규약은 [`spec/interfaces.md`](../spec/interfaces.md) §0.2 에 명시

### 4.4. 수식 LLM 의 폴백 우선

API 호출이 실패하거나 키가 없으면 `[hnc 수식]<latex>[/hnc 수식]` 폴백을 무조건 반환.
변환기가 절대 도중에 죽지 않게 함. 사용자는 한/글에서 해당 위치를 찾아 수식 편집기로
직접 입력함.

### 4.5. ID 하드코딩 금지

코드 내에 `styleIDRef="4"` 같은 숫자 직접 사용 금지. 진실원은 한 곳:
`templates/Contents/header.xml`. `spec/styles.yaml` 은 역할 → *이름* 매핑만
정의하고, 정수 ID 는 런타임에 `builder.header.parse_style_table()` 이 추출.
이건 B 의 코어 영역 규칙이지만 C 가 작성하는 manifest 등도 동일 원칙을
따라야 함 (header.xml 이 갱신되면 자동으로 ID 가 따라옴).

---

## 5. B 와의 협업 방식

### 5.1. B 가 호출하는 C 의 함수

C 가 먼저 실구현해야 B 가 통합 가능한 함수들. 우선순위 순서:

1. `register_image(src_path, work_dir)` → 그림 빌더(B) 가 호출 예정
2. `update_manifest(content_hpf_path, entries)` → 그림 등록 후 호출
3. `convert_equation(latex, display)` → 수식 빌더(B) 가 호출

### 5.2. C 가 호출하는 B 의 함수

- `md_to_hwpx(md_path, output_path, style_map, work_dir)` (계약 6)
- C 의 `cli.py` 에서 인자 파싱 후 본 함수 호출

### 5.3. PR 단위와 브랜치 전략

- B 는 `feature/core-engine` 누적 작업 중
- C 는 `feature/c-infra` (또는 더 세분화된 `feature/c-bindata`,
  `feature/c-math` 등) 로 분기 권장
- 두 브랜치 모두 main 으로 PR 머지

### 5.4. 인터페이스 변경 절차

`spec/interfaces.md` §3 참조. 변경 사유와 영향 범위를 PR 본문에 명시,
양쪽 호출처를 동일 PR 에서 수정, 회귀 통과 후 머지.

### 5.5. 검증 도구 (`mapsi.inspect`)

C 의 `package_hwpx`, `register_image`, `update_manifest` 작업이
실제로 한/글이 인식 가능한 HWPX 를 만들었는지 확인할 때 사용한다.

```bash
python -m mapsi.inspect output/test.hwpx --styles
```

ZIP 구조가 깨졌거나 styleIDRef 가 header.xml 에 없는 경우 즉시 잡힌다.
B/C 공용 도구. 자세한 사용법은 [README](../README.md) "검증" 섹션 참조.

---

## 6. 작업 개시 체크리스트

- [ ] Python 3.11+ 환경 구축, `pip install -e ".[dev]"` 로 설치
- [ ] `pytest` 실행하여 36/36 통과 확인
- [ ] `mapsi samples/base/base.md -o output/test.hwpx` 로 변환 1 회 수행 후
      한/글에서 열어 보기 (CP1 의 의미 직접 체험)
- [ ] [`spec/interfaces.md`](../spec/interfaces.md) 정독, 7 개 계약 시그니처 숙지
- [ ] §3.1 의 임시 구현 3 파일(cli/config/packager) 검토, 필요 시 PR 로 갈아엎기
- [ ] §3.2 의 우선순위 따라 본 구현 진입
- [ ] B 와 작업 동기화 (현 시점 B 는 `parse_markdown` 실구현 중)

---

## 7. 추가 참고 자료

- 프로젝트 전체 계획, [project_plan.md](project_plan.md)
- B 의 인수인계, [developer_handoff.md](developer_handoff.md)
- 인터페이스 계약, [../spec/interfaces.md](../spec/interfaces.md)
- 스타일 카탈로그, [../spec/styles.yaml](../spec/styles.yaml)
- 한/글 파일 형식 공식 스펙, `../spec/references/` 아래 5 개 PDF
- 수식 변환 참조, `../spec/hnc_equation_spec.pdf`
- 레퍼런스 XML, `../samples/incremental/*/unpacked/Contents/`
