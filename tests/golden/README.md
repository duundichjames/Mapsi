# Golden Test Fixtures

본 디렉토리는 변환기 회귀 테스트에 사용되는 입력/기대 출력 쌍을 보관함.

## 왜 별도로 두는가

`samples/` 의 `*.md` 와 `*.hwpx` 는 **1:1 대응이 아님**. 그쪽은
A 가 한/글에서 직접 작성한 데모 문서로, 입력 마크다운에 없는 설명문,
폴더 트리, secPr 예시 등이 추가되어 있고 단락 수도 60+개에 이름.

따라서 "마크다운을 변환한 결과 == 그 샘플의 .hwpx" 같은 직접 비교는
성립하지 않음. 별도로 작은 1:1 픽스처를 우리가 직접 작성하여 회귀 테스트의
정답으로 사용함. `samples/` 는 시각적 참고 및 한/글 호환성 검증용으로만 보존.

## 디렉토리 규약

각 픽스처는 다음 두 파일을 포함:

- `input.md` - 변환기에 입력할 마크다운 (front matter 없음, 순수 본문)
- `expected.yaml` - 변환 결과의 기대 스타일/텍스트 시퀀스

```
tests/golden/
├── README.md                ← 본 파일
├── 01_headings/
│   ├── input.md
│   └── expected.yaml
├── 02_bullet_list/
│   └── ...
└── ...
```

## `expected.yaml` 형식

```yaml
description: 픽스처에 대한 한 줄 설명
style_sequence:               # 본문 단락이 가져야 할 스타일 이름 시퀀스
  - 본문                       # styleIDRef → header.xml 룩업 결과로 비교
  - 개요 1
  - 개요 2
  ...
text_sequence:                # 각 단락의 텍스트 (run 들의 t 노드 결합)
  - "본문 단락입니다."
  - "제목1"
  - "제목2"
  ...
```

두 시퀀스의 길이는 같아야 함. 비교는 인덱스별로 짝지어 검증.

표나 그림 같은 비단락 요소가 들어가는 픽스처는 차후 필드를 확장 정의함
(예: `tables`, `pictures`, `equations`).

## 비교 메커니즘 (스타일 ID 충돌 회피)

각 .hwpx 파일은 자신만의 header.xml 을 가지며, 그 안의 스타일에 부여되는
정수 ID 는 문서마다 다름 (예: 같은 "개요 1" 이 한 문서에서는 ID 2,
다른 문서에서는 ID 4). 따라서 styleIDRef 의 raw 정수값 비교는 무의미함.

회귀 테스트는 `tests/_golden.py` 의 `extract_paragraph_sequence()` 헬퍼를
사용하여 .hwpx 의 styleIDRef → 그 .hwpx 자신의 header.xml 룩업 →
스타일 이름 (예: "개요 1") 으로 정규화한 뒤 `expected.yaml` 과 비교함.

## 픽스처 추가/수정 절차

1. `tests/golden/<NN_name>/` 디렉토리 생성
2. `input.md` 작성 (front matter 없이 순수 본문만)
3. 입력을 머릿속(또는 스펙)으로 따라가며 `expected.yaml` 작성
4. `tests/test_golden.py` 또는 신규 테스트 추가, `pytest -k <NN_name>` 으로 통과 확인
5. 통과 후 PR 머지
