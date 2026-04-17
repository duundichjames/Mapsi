---
샘플명: 08_references
이전: 07_footnote
도입 요소:
  - reference
스타일 매핑:
  "# 참고문헌" 또는 "# References" 제목:     개요 1 (기존 규칙 유지)
  해당 제목 아래 모든 단락 (다른 제목 전까지): 참고문헌
테스트 관점:
  - 참고문헌 섹션 판정은 제목 텍스트로만 수행하는가
    (허용 변형은 "참고문헌", "참고 문헌", "References", "REFERENCES" 네 가지로 고정)
  - heading_2 이하 하위 제목이 중간에 나와도 참고문헌 섹션은 유지되는가
    (설계 선택, heading_1 이 다시 나오기 전까지는 모두 reference 로 처리)
  - 빈 줄로 구분된 각 항목이 독립된 문단으로 보존되는가
  - 참고문헌 섹션 내부에는 글머리 기호/번호가 없어야 함 (원문에 "- " 가 있어도 리스트로 처리하지 않음)
---

본문 단락입니다.

# 참고 문헌

Mazzucato, Mariana. 2015. Building the Entrepreneurial State. Anthem Press.

Cumming, Douglas. 2007. "Government Policy Towards Entrepreneurial Finance." Journal of Business Venturing.

OECD. 2021. Venture Capital and Start-Ups in OECD Countries. OECD Publishing.
