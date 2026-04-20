---
샘플명: 10_inline
이전: 09_equations
도입 요소:
  - inline_bold
  - inline_italic
  - inline_strikethrough
  - inline_code
  - inline_link
스타일 매핑:
  "**굵게**":      본문 단락 + charPrIDRef=25
  "*기울임*":      본문 단락 + charPrIDRef=26
  "***굵+기울***": 본문 단락 + charPrIDRef=27
  "~~취소~~":      본문 단락 + charPrIDRef=28 (strikeout shape="SOLID")
  "`코드`":        본문 단락 + charPrIDRef=29 (모노 폰트 + 회색 음영)
  "[label](url)":  라벨 텍스트만 평문에 흡수, URL 폐기 (v0.2 hyperlink field 마이그)
테스트 관점:
  - 한 단락 안에서 글자모양이 바뀔 때마다 hp:run 이 분리되는가
  - 동일 charPrIDRef 가 인접하면 한 run 으로 합쳐지는가
  - bold + italic 동범위는 charPr 27 한 개로 매핑되는가
  - 사전에 없는 조합 (예: bold+italic+strike) 은 우선순위 디그레이드로 가까운 charPr 로 매핑되는가
  - 링크는 라벨만 평문에 흡수되고 URL 은 폐기되는가
  - 인라인 마크가 없는 단락은 기존 단일 hp:run 경로를 그대로 따르는가
---

# 인라인 서식 데모

문장 안에서 **굵은 글씨** 와 *기울인 글씨* 그리고 ~~취소선~~ 을 섞어 쓸 수 있습니다.

함수 `parse_markdown()` 은 인라인 코드를 모노스페이스로 보여 줍니다.

***굵고 기울인*** 조합도 한 단어로 묶을 수 있습니다.

링크는 [한컴 사이트](https://www.hancom.com) 처럼 라벨만 보존됩니다.

본문 평문 단락으로 마무리합니다.
