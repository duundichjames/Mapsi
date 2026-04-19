# Mapsi 개발자 핸드오프

본 문서는 Mapsi 의 본격 코드 개발을 담당하는 개발자 B 에게 작업 착수 전 필요한 정보를 전달하기 위한 온보딩 자료임. 프로젝트 전체 계획은 [project_plan.md](project_plan.md) 에 기술되어 있으며, 본 문서는 그 중 B 의 작업에 직결되는 내용을 발췌 및 보강한 것임.

---

## 1. 사전 준비된 자산

개발 시작 시점에 다음 자산이 리포지토리에 준비되어 있음.

### 1.1. 디렉토리별 자산

- `templates/`, 정적 파일 세트(mimetype, META-INF, version.xml, Contents/header.xml) 의 완비
- `samples/`, 10 개 레퍼런스 HWPX 와 unpacked 디렉토리, 그리고 각 HWPX 와 쌍을 이루는 10 개 마크다운 입력 예제(base.md, 01_headings.md 등)
- `spec/extracted/styles.csv`, 각 샘플별 스타일 ID 매핑
- `spec/references/`, 한/글 공식 스펙 문서 5 종
- `spec/hnc_equation_spec.pdf`, 수식 변환용 참조 문서
- `docs/project_plan.md`, 전체 프로젝트 계획

각 샘플 폴더의 `NN_xxx.md` 는 변환기의 기대 입력이며, 같은 폴더의 `NN_xxx.hwpx` 는 그 입력이 생성해야 할 정답 출력이다. 각 md 파일 상단 YAML front matter 에 도입 요소, 스타일 매핑, 테스트 관점, 경계 조건이 명시되어 있어 B 가 별도 문서를 참조하지 않고도 테스트 케이스를 추출할 수 있다.

### 1.2. 확정된 스타일 ID 테이블

`templates/Contents/header.xml` 은 `samples/incremental/09_equations` 의 header.xml 을 그대로 복사한 것이며, 다음 ID 매핑이 확정된 상태로 고정됨.

| 역할 | 스타일 이름 | ID |
|------|-------------|-----|
| paragraph | 본문 | 3 |
| heading_1 | 개요 1 | 4 |
| heading_2 | 개요 2 | 5 |
| heading_3 | 개요 3 | 6 |
| heading_4 | 개요 4 | 7 |
| heading_5 | 개요 5 | 17 |
| heading_6 | 개요 6 | 18 |
| bullet_list_1 | 네모 | 14 |
| bullet_list_2 | 동그라미 | 15 |
| bullet_list_3 | 줄 | 16 |
| ordered_list_1 | 번호1 | 10 |
| ordered_list_2 | 번호2 | 12 |
| ordered_list_3 | 번호3 | 13 |
| blockquote | 인용 | 8 |
| code_block | 코드 | 9 |
| table_cell | 표내용 | 33 |
| table_caption | 표캡션 | 11 |
| figure | 그림 | 2 |
| figure_caption | 그림캡션 | 1 |
| footnote | 각주 | 25 |
| reference | 참고문헌 | 36 |
| memo | 메모 | 27 |

---

## 2. 개발자 B 의 착수 작업

### 2.1. 스타일 매핑 YAML 작성

- 파일 경로, `spec/styles.yaml`
- 역할, 위 ID 테이블의 YAML 형태 직렬화
- 사용처, `config.py`(C 담당) 의 `스타일매핑로드()` 에 의해 딕셔너리로 로드
- 변환기 전 모듈에서 이 파일의 매핑을 통해 ID 참조

### 2.2. 인터페이스 계약 문서 확정

- 파일 경로, `spec/interfaces.md`
- 내용, B 와 C 사이의 6 개 함수 시그니처와 docstring
- 확정 시점, 1 일차 오전 체크포인트 이전
- 변경 가능 시점, 2 일차 오후 마지막 2 시간 이후

### 2.3. 프로젝트 스캐폴드 구축

- `pyproject.toml` 생성 및 의존성 명시(markdown-it-py, lxml, pyyaml, Pillow)
- 패키지 디렉토리 구조(`mapsi/`, `mapsi/builder/`, `mapsi/math/`) 의 초기화
- 각 디렉토리의 `__init__.py` 생성

### 2.4. 코어 파일 뼈대 커밋

다음 파일들의 함수 시그니처와 docstring 만 담은 뼈대 커밋.

- `mapsi/converter.py`, `마크다운toHWPX()` 의 시그니처
- `mapsi/parser.py`, `파싱()` 의 시그니처 및 Block 데이터클래스 정의
- `mapsi/ast_walker.py`, `블록순회()` 의 시그니처
- `mapsi/styles.py`, `스타일ID()` 의 시그니처
- `mapsi/builder/section.py`, `섹션빌더()` 의 시그니처
- `mapsi/builder/elements.py`, 요소별 빌더 시그니처

이 뼈대가 커밋된 뒤에 C 가 `cli.py`, `packager.py`, `config.py`, `builder/manifest.py`, `builder/bindata.py` 의 병렬 구현을 시작함.

---

## 3. 핵심 설계 원칙

### 3.1. header.xml 의 불변성

- `templates/Contents/header.xml` 은 **읽기 전용** 자산
- 변환기가 이 파일을 동적으로 조립하지 않으며, 출력 HWPX 에 그대로 복사하여 포함
- 스타일 ID 가 불규칙하게 매겨진 상태 그대로 유지
- ID 재할당 금지(paraPrIDRef, charPrIDRef 가 참조하는 ID 이므로 재할당 시 참조 무결성 파괴)

### 3.2. 변환기의 본질적 책임

- section0.xml 생성이 변환기의 유일한 본질적 작업
- 그 외 파일(mimetype, header.xml, META-INF 등) 은 템플릿 복사로 처리
- 이미지 등록과 manifest 갱신은 C 의 모듈에 위임

### 3.3. section0.xml 구조의 참조처

- 모든 요소를 포함한 완성본, `samples/incremental/09_equations/unpacked/Contents/section0.xml`
- 특정 요소의 XML 패턴 확인 시 이 파일에서 해당 요소 발췌
- 공식 스펙 문서(`spec/references/`) 참조보다 샘플 직접 관찰이 우선

### 3.4. 증분 샘플 기반 XML 패턴 추출

각 요소가 처음 등장하는 증분 샘플과 직전 샘플의 diff 를 통한 최소 XML 패턴 확인 가능.

| 요소 | 샘플 | 비교 대상 |
|------|------|-----------|
| 헤딩 | 01_headings | base |
| 순서 없는 목록 | 02_bullet_list | 01_headings |
| 순서 있는 목록 | 03_ordered_list | 02_bullet_list |
| 인용 및 코드 | 04_blockquote_code | 03_ordered_list |
| 표 | 05_table | 04_blockquote_code |
| 그림 | 06_figure | 05_table |
| 각주 | 07_footnote | 06_figure |
| 참고문헌 | 08_references | 07_footnote |
| 수식 | 09_equations | 08_references |

사용 예시,

```zsh
diff samples/incremental/04_blockquote_code/unpacked/Contents/section0.xml \
     samples/incremental/05_table/unpacked/Contents/section0.xml
```

각 샘플 폴더에는 해당 증분이 도입하는 요소만을 담은 최소 md 입력 파일이 쌍으로 존재한다. B 의 TDD 루프는 다음 형태로 구성 가능하다.

```python
from pathlib import Path
import subprocess

샘플루트 = Path("samples/incremental")
for 폴더 in sorted(샘플루트.iterdir()):
    if not 폴더.is_dir():
        continue
    md파일 = 폴더 / f"{폴더.name}.md"
    정답파일 = 폴더 / f"{폴더.name}.hwpx"
    출력파일 = Path(f"/tmp/{폴더.name}_out.hwpx")
    subprocess.run(["mapsi", str(md파일), "-o", str(출력파일)], check=True)
    # 비교, section0.xml 의 styleIDRef 시퀀스 일치 여부
```

초기 단계에는 styleIDRef 시퀀스 비교만으로 충분하며, 후반에 텍스트 내용과 특수 요소(tbl, pic, equation) 의 존재 여부까지 확장하면 된다.

### 3.5. ID 하드코딩 금지 (이름 기반 룩업 원칙)

- 빌더 코드 내의 ID 숫자 직접 사용 금지
- `spec/styles.yaml` 은 *이름* 매핑만 정의 (역할 → "본문" / "개요 1" 등)
- 정수 ID 는 `templates/Contents/header.xml` 이 단일 진실원
- 빌더는 다음 두 단계로 ID 를 얻음:
  1. `style_name(style_map, role, depth)` → 한/글 스타일 *이름*
  2. `parse_style_table(header_xml)[name]` → `StyleEntry(id, paraPrIDRef, charPrIDRef)`
- 예시, `styleIDRef="4"` 대신 `styleIDRef=entry.id` (entry 는 위 룩업 결과)

---

## 4. 개발자 C 와의 협업 지점

### 4.1. B 가 호출하는 C 의 함수

C 가 먼저 구현해야 B 가 통합 가능한 함수들.

- `config.py` 의 `스타일매핑로드(yaml경로)`, styles.yaml 의 딕셔너리 반환
- `packager.py` 의 `HWPX패키징(작업디렉토리, 출력경로)`, 작업 디렉토리의 ZIP 패키징
- `builder/bindata.py` 의 `이미지등록(원본경로, 작업디렉토리)`, 이미지의 BinData 복사 및 ID 발급
- `builder/manifest.py` 의 `manifest갱신(content_hpf경로, 추가항목)`, content.hpf 의 manifest 항목 추가
- `math/converter.py` 의 `수식변환(latex, display)`, LaTeX 의 HNC 수식 변환

이 함수들의 시그니처는 `spec/interfaces.md` 에 B 가 확정 후 불변.

### 4.2. C 가 호출하는 B 의 함수

- `converter.py` 의 `마크다운toHWPX(md경로, 출력경로, 스타일맵, 작업디렉토리)`
- 전체 변환 파이프라인의 엔트리포인트
- C 의 `cli.py` 에서 인자 파싱 후 본 함수 호출

---

## 5. 주의 사항

### 5.1. section0.xml 의 secPr 블록 보존

- section0.xml 의 시작부에 있는 `hp:secPr` 블록은 쪽번호, 용지, 여백 등 문서 전역 설정의 보관소
- base.hwpx 로부터 그대로 복사 필요
- 변환기가 생성하는 영역은 hp:secPr 이후의 본문(hp:p, hp:tbl 등) 에 국한
- 구체적 방식, `templates/Contents/section0.xml` 에 빈 본문 상태의 뼈대(secPr 블록 포함) 배치 후, 변환기의 본문 영역 교체 방식

### 5.2. 한국어 파일명의 NFD 정규화

- macOS 의 한국어 파일명 저장 방식, NFD(분해형) 유니코드
- 한/글의 파일명 기대 형식, NFC(조합형) 가능성
- 대응, `이미지등록()` 내부의 `unicodedata.normalize("NFC", ...)` 적용
- 담당, C

### 5.3. 회귀 테스트 기준점

- 기준 샘플, `samples/incremental/09_equations/unpacked/Contents/section0.xml`
- 대응 마크다운 픽스처, `tests/fixtures/` 아래에 모든 요소를 포함한 마크다운 파일 배치
- 비교 방식, lxml 의 C14N 정규화 후 의미적 동일성 판정
- 담당, C(픽스처 작성) 및 B(빌더 정확성 보장)

### 5.4. 순서 목록의 번호 보존 원칙

- 한/글의 문단 자동 번호매김 기능은 순서 있는 목록(번호1/2/3) 에서 사용하지 않음
- 이유, 개요 1 - 6 의 번호 체계와의 카운터 간섭 회피
- 대응, 마크다운 원문의 "1. ", "2. " 등의 번호 텍스트를 hp:t 에 그대로 보존
- 번호1/2/3 스타일의 역할, 깊이별 들여쓰기만 제공
- 결과, md 원문이 "1. / 1. / 1." 이면 세 항목 모두 "1." 로 출력되고, "1. / 2. / 3." 이면 그대로 출력됨

### 5.5. 표/그림 캡션의 접두사 제거 원칙

- 순서 목록의 번호 보존 원칙과 방향이 반대임. 혼동 주의
- 변환기가 표 직전 또는 그림 직후의 단락이 정규식 "^(표|Table|그림|Figure)\s+\d+\.\s*" 로 시작하면 캡션으로 승격
- 승격 시 접두사("표 N. ", "그림 N. " 등) 를 파싱 후 제거하고 뒤쪽 본문만 캡션 슬롯에 저장
  예시, "표 1. 주요 재정 융자 사업 비교" → 캡션 텍스트는 "주요 재정 융자 사업 비교"
- 번호 자리는 한/글의 autoNum 에 위임하며 변환기는 번호를 기록하지 않음
- 사용자가 md 에서 쓴 번호 값은 무시됨. 한/글이 문서 내 표/그림 등장 순서대로 1, 2, 3... 재부여
- 두 원칙의 근거 차이, hwpx 의 표와 그림은 autoNum 메커니즘을 기본 제공하는 반면 번호1/2/3 스타일에는 자동 번호 메커니즘이 없음. 따라서 전자는 위임하고 후자는 원문에 책임을 둠

---

## 6. 작업 개시 체크리스트

- [ ] `samples/incremental/09_equations/unpacked/Contents/` 아래의 section0.xml 및 header.xml 관찰
- [ ] `samples/base/base.md` 와 `samples/incremental/*/*.md` 파일 10 개의 front matter 숙지
- [ ] `spec/extracted/styles.csv` 의 09_equations 행 숙지
- [ ] `docs/project_plan.md` 의 "모듈 구조" 및 "인터페이스 계약" 섹션 정독
- [ ] Python 3.11 환경 구축 및 markdown-it-py, lxml, pyyaml 설치
- [ ] `spec/styles.yaml` 작성(위 ID 테이블 기반)
- [ ] 프로젝트 스캐폴드(pyproject.toml, 패키지 디렉토리) 생성
- [ ] `spec/interfaces.md` 의 6 개 계약 확정 및 커밋
- [ ] 코어 파일 뼈대 커밋(converter.py, parser.py 등)
- [ ] C 에게 인터페이스 계약 확정 알림

---

## 7. 추가 참고 자료

- 프로젝트 전체 계획, [project_plan.md](project_plan.md)
- 한/글 파일 형식 공식 스펙, `spec/references/` 아래의 5 개 PDF
- 수식 변환 참조, `spec/hnc_equation_spec.pdf`
- 레퍼런스 XML, `samples/incremental/*/unpacked/Contents/`
