# HWPX 템플릿 파일 비교 리포트

## 📊 비교 결과 요약

### ✅ 동일한 파일들 (templates/ 폴더에 복사됨)

| 파일명 | 상태 | 위치 |
|--------|------|------|
| `mimetype` | 모든 10개 샘플에서 동일 | `templates/mimetype` |
| `META-INF/container.xml` | 모든 10개 샘플에서 동일 | `templates/META-INF/container.xml` |
| `META-INF/container.rdf` | 모든 10개 샘플에서 동일 | `templates/META-INF/container.rdf` |
| `META-INF/manifest.xml` | 모든 10개 샘플에서 동일 | `templates/META-INF/manifest.xml` |
| `version.xml` | 모든 10개 샘플에서 동일 | `templates/version.xml` |

### ✗ 차이가 있는 파일

#### `settings.xml`
- **base 샘플**: `<ha:CaretPosition listIDRef="0" paraIDRef="33" pos="18"/>`
- **모든 incremental 샘플**: 다른 `paraIDRef`와 `pos` 속성값

**상세 차이:**

| 샘플명 | paraIDRef | pos | 설명 |
|--------|-----------|-----|------|
| base | 33 | 18 | 기본 템플릿 |
| 01_headings | 20 | 0 | 제목 기능 추가 |
| 02_bullet_list | 9 | 0 | 글머리 목록 추가 |
| 03_ordered_list | 3 | 0 | 번호 목록 추가 |
| 04_blockquote_code | 5 | 21 | 인용문/코드 추가 |
| 05_table | 2 | 141 | 표 추가 |
| 06_figure | 47 | 0 | 그림 추가 |
| 07_footnote | 0 | 24 | 각주 추가 |
| 08_references | 2 | 52 | 참고문헌 추가 |
| 09_equations | 0 | 383 | 수식 추가 |

### 🔎 분석

`settings.xml`은 **문서의 마지막 열린 위치(Caret Position)**를 저장합니다:
- `paraIDRef`: 단락(paragraph) ID
- `pos`: 단락 내 위치

각 샘플의 내용이 서로 다르기 때문에 이 값들이 달라집니다. 이는 정상적인 현상입니다.

## 📁 templates 디렉토리 구조

```
templates/
├── mimetype
├── version.xml
└── META-INF/
    ├── container.xml
    ├── container.rdf
    └── manifest.xml
```

## ✅ 작업 완료

- ✓ 10개 HWPX 파일 모두 unpacked 완료
- ✓ 파일 비교 분석 완료
- ✓ 동일한 파일 5개를 templates 폴더로 복사
- ✓ settings.xml 차이점 상세 분석

