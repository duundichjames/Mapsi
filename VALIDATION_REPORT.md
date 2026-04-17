# XML 검증 리포트

**파일**: `templates/Contents/header.xml`  
**소스**: `samples/incremental/09_equations/unpacked/Contents/header.xml`  
**검증 도구**: lxml (Python XML 라이브러리)  
**검증 일시**: 2026-04-18

---

## 📊 파일 정보

| 항목 | 값 |
|------|-----|
| 파일 크기 | 97,228 bytes |
| 인코딩 | UTF-8 |
| XML 선언 | `<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>` |
| 루트 요소 | `hh:head` |
| 버전 | 1.5 |

---

## 🔗 네임스페이스 (15개)

| 접두어 | URI |
|-------|-----|
| `ha` | http://www.hancom.co.kr/hwpml/2011/app |
| `hp` | http://www.hancom.co.kr/hwpml/2011/paragraph |
| `hp10` | http://www.hancom.co.kr/hwpml/2016/paragraph |
| `hs` | http://www.hancom.co.kr/hwpml/2011/section |
| `hc` | http://www.hancom.co.kr/hwpml/2011/core |
| `hh` | http://www.hancom.co.kr/hwpml/2011/head |
| `hhs` | http://www.hancom.co.kr/hwpml/2011/history |
| `hm` | http://www.hancom.co.kr/hwpml/2011/master-page |
| `hpf` | http://www.hancom.co.kr/schema/2011/hpf |
| `dc` | http://purl.org/dc/elements/1.1/ |
| `opf` | http://www.idpf.org/2007/opf/ |
| `ooxmlchart` | http://www.hancom.co.kr/hwpml/2016/ooxmlchart |
| `hwpunitchar` | http://www.hancom.co.kr/hwpml/2016/HwpUnitChar |
| `epub` | http://www.idpf.org/2007/ops |
| `config` | urn:oasis:names:tc:opendocument:xmlns:config:1.0 |

---

## 🏗️ 문서 구조

### 요소 통계

| 요소 타입 | 개수 | 용도 |
|----------|------|------|
| margin | 90 | 여백 설정 |
| font | 48 | 글꼴 정의 |
| paraPr | 45 | 단락 속성 |
| charPr | 25 | 문자 속성 |
| style | 37 | 스타일 정의 |
| borderFill | 6 | 테두리/채우기 |
| numbering | 2 | 번호 매기기 |
| tabProperties | 3 | 탭 속성 |

**총 요소 타입**: 62개

### 주요 섹션 검증

| 섹션 | 선언 | 실제 | 상태 |
|------|------|------|------|
| hh:fontfaces | 7 | 7 | ✓ |
| hh:borderFills | 6 | 6 | ✓ |
| hh:charProperties | 25 | 25 | ✓ |
| hh:tabProperties | 3 | 3 | ✓ |
| hh:numberings | 2 | 2 | ✓ |
| hh:paraProperties | 45 | 45 | ✓ |
| hh:styles | 37 | 37 | ✓ |

---

## 📈 스타일 정의

| 항목 | 값 |
|------|-----|
| **총 스타일 수** | **37개** |
| PARA 타입 | 33개 |
| CHAR 타입 | 4개 |

### 스타일 분류

**단락 스타일 (PARA)**:
- 기본 스타일: 바탕글, 본문, 머리말, 각주, 미주
- 개요 스타일: 개요 1-7
- 특수 스타일: 차례 제목, 차례 1-3, 캡션, 메모

**문자 스타일 (CHAR)**:
- 쪽 번호

---

## ✅ 검증 결과

### 파싱 검증
- ✓ XML 구문 유효
- ✓ 인코딩 정상
- ✓ 네임스페이스 정의 완전

### 구조 검증
- ✓ 루트 요소 정상
- ✓ 모든 자식 요소 접근 가능
- ✓ 속성 값 일치
  - itemCnt와 실제 요소 수 일치 확인됨
- ✓ 중첩 구조 정상

### 콘텐츠 검증
- ✓ 37개 스타일 (기본 22개 + 증분 15개)
- ✓ 45개 단락 속성
- ✓ 25개 문자 속성
- ✓ 6개 테두리/채우기 정의
- ✓ 2개 번호 매기기 정의

---

## 📝 결론

**`templates/Contents/header.xml`은 완전히 유효합니다.**

이 파일은 증분 사슬의 최종 단계(09_equations)를 기준으로하며, 모든 마크다운 요소에 필요한 스타일 정의가 누적되어 있습니다:

- ✓ 모든 네임스페이스 정의됨
- ✓ XML 문법 오류 없음
- ✓ 모든 요소의 속성 일치
- ✓ 계층 구조 정상
- ✓ 스타일 정의 완전

이 파일은 **템플릿 기반 문서 변환의 마스터 헤더**로 사용 가능합니다.

