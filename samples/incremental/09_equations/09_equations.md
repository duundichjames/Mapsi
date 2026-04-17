---
샘플명: 09_equations
이전: 08_references
도입 요소:
  - inline_equation
  - display_equation
스타일 매핑:
  "$...$":   본문 내 hp:equation 요소 (단락 스타일은 "본문" 유지)
  "$$...$$": 독립 단락 내부의 hp:equation 요소
테스트 관점:
  - 인라인 수식은 앵커 단락이 "본문" 스타일을 유지하고 수식만 hp:equation 으로 삽입되는가
  - 디스플레이 수식은 단독 단락으로 분리되는가
  - 환경 변수에 ANTHROPIC_API_KEY 또는 OPENAI_API_KEY 가 있으면 LaTeX 를 HNC 스크립트로 변환하는가
  - 두 키 모두 없으면 "[hnc 수식]...[/hnc 수식]" 태그와 함께 LaTeX 원문을 보존하는가
  - 동일 수식에 대한 변환 결과가 ~/.mapsi/equation_cache.json 에 캐시되는가
    (캐시 키는 LaTeX 원문의 SHA-256 해시 앞 16 자)
  - Anthropic 우선 OpenAI 차선 순서가 지켜지는가
  - $ 기호가 본문에 자연스럽게 사용될 경우(예를 들어 "$100") 에 대한 이스케이프 규칙은 본 샘플 범위 외로 고정
---

본문에서 $a^2 + b^2 = c^2$ 와 같이 인라인 수식을 쓸 수 있습니다.

다음은 디스플레이 수식입니다.

$$
\frac{1}{N} \sum_{n=1}^{N} x_n = \bar{x}
$$

수식 뒤의 평문 단락입니다.
