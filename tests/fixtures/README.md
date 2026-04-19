# tests/fixtures/

테스트가 사용하는 정적 자산. `tests/golden/` 의 픽스처와 달리 `.md` /
`expected.yaml` 짝이 아니라 **단일 자산 파일** 만 둠.

## 현재 자산

| 파일 | 용도 |
|---|---|
| `sample_figure.png` | 그림 임베드 (Phase 6b) 골든 테스트용. 200×120 RGB, 약 1 KB. |

## 자산 추가 시

- 가능한 작게 (수 KB) 만들 것 — git 비대화 방지
- 바이너리는 가급적 코드로 재생성 가능한 형태로 (e.g. PNG 는
  `Pillow` 의 `Image.new()` 1 줄로 만들 수 있음)
