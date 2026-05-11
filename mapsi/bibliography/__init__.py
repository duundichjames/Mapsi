"""BibTeX 서지 처리 패키지.

BibTeX 파일과 인라인 bibtex 코드 블록을 파싱하고,
[@citekey] 인용 마크를 한국어/영문 학술 형식 문자열로 포매팅한다.

공개 API:
    load_bibliography: .bib 파일 + 인라인 블록 → citekey 사전
    BibFormatter: 인용 포매팅 + 참고문헌 목록 생성
"""

from .formatter import BibFormatter
from .parser import load_bibliography

__all__ = ["load_bibliography", "BibFormatter"]
