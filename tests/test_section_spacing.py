"""표 뒤·헤딩 앞 빈 줄 삽입(항목 1·2) 과 제목 1 크기·정렬(항목 4) 테스트.

- 빈 줄은 ``filter_nonempty`` 로 골든에서 걸러지므로, 여기서는 *필터 없이*
  ``extract_paragraph_sequence`` 로 빈 단락이 실제로 emit 되는지 직접 본다.
- 제목 1 의 크기/정렬은 변환 산출물의 header.xml 에서 charPr 23·paraPr 44 를
  직접 확인한다.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from lxml import etree

from mapsi.config import load_style_map
from mapsi.converter import md_to_hwpx
from mapsi.inspect import extract_paragraph_sequence


HH = "{http://www.hancom.co.kr/hwpml/2011/head}"


@pytest.fixture(scope="module")
def style_map(spec_dir: Path):
    return load_style_map(spec_dir / "styles.yaml")


def _convert(tmp_path: Path, style_map, md_text: str) -> Path:
    md = tmp_path / "in.md"
    md.write_text(md_text, encoding="utf-8")
    out = tmp_path / "out.hwpx"
    work = tmp_path / "work"
    work.mkdir()
    md_to_hwpx(md, out, style_map, work)
    return out


# ---------------------------------------------------------------------------
# 항목 1 — 표 뒤 빈 줄
# ---------------------------------------------------------------------------


def _is_blank(p) -> bool:
    """삽입한 간격용 빈 줄인지(본문 스타일 + 빈 텍스트). secPr 호스트(바탕글)와 구분."""
    return p.text == "" and p.style_name == "본문"


def test_blank_paragraph_after_table(tmp_path: Path, style_map) -> None:
    """표(wrapper) 단락 바로 뒤에 빈 본문 단락이 하나 들어간다."""
    md = "| A | B |\n| - | - |\n| 1 | 2 |\n\n표 다음 서술 문단.\n"
    seq = extract_paragraph_sequence(_convert(tmp_path, style_map, md))
    texts = [p.text for p in seq]
    # "표 다음 서술 문단." 직전에 빈 본문 단락이 있어야 한다.
    idx = texts.index("표 다음 서술 문단.")
    assert _is_blank(seq[idx - 1]), "표 뒤 빈 단락이 없다"


# ---------------------------------------------------------------------------
# 항목 2 — 헤딩 앞 빈 줄 (첫 헤딩 제외)
# ---------------------------------------------------------------------------


def test_no_blank_before_first_heading(tmp_path: Path, style_map) -> None:
    """문서 첫 헤딩 앞에는 빈 줄을 넣지 않는다."""
    md = "# 첫째 장\n\n내용.\n\n# 둘째 장\n\n내용2.\n"
    seq = extract_paragraph_sequence(_convert(tmp_path, style_map, md))
    texts = [p.text for p in seq]
    first = texts.index("첫째 장")
    # 첫 헤딩 앞에 삽입형 빈 본문 단락이 없어야 한다 (secPr 호스트 바탕글은 무관).
    assert not any(_is_blank(p) for p in seq[:first]), "첫 헤딩 앞에 빈 줄이 생겼다"


def test_blank_before_later_headings(tmp_path: Path, style_map) -> None:
    """둘째 이후 헤딩 앞에는 빈 본문 단락이 들어간다."""
    md = "# 첫째 장\n\n내용.\n\n# 둘째 장\n\n내용2.\n"
    seq = extract_paragraph_sequence(_convert(tmp_path, style_map, md))
    texts = [p.text for p in seq]
    idx = texts.index("둘째 장")
    assert _is_blank(seq[idx - 1]), "둘째 헤딩 앞에 빈 줄이 없다"


def test_heading_right_after_title_has_no_blank(tmp_path: Path, style_map) -> None:
    """front matter title 만 앞서면 그 뒤 첫 헤딩 앞에는 빈 줄이 없다."""
    md = "---\ntitle: 문서 제목\n---\n\n# 첫째 장\n\n내용.\n"
    seq = extract_paragraph_sequence(_convert(tmp_path, style_map, md))
    texts = [p.text for p in seq]
    h = texts.index("첫째 장")
    # 제목 단락과 헤딩 사이에 삽입형 빈 본문 단락이 없어야 한다.
    title_idx = texts.index("문서 제목")
    assert not any(
        _is_blank(p) for p in seq[title_idx + 1 : h]
    ), "title 뒤 첫 헤딩 앞에 빈 줄이 생겼다"


# ---------------------------------------------------------------------------
# 항목 4 — 제목 1 크기(24pt)·정렬(가운데)
# ---------------------------------------------------------------------------


def test_title_style_is_24pt_centered(tmp_path: Path, style_map) -> None:
    """변환 산출물 header.xml 에서 제목 1(charPr 23·paraPr 44) 이 24pt·CENTER."""
    out = _convert(tmp_path, style_map, "---\ntitle: 문서 제목\n---\n\n본문.\n")
    with zipfile.ZipFile(out) as z:
        hdr = etree.fromstring(z.read("Contents/header.xml"))
    char23 = next(c for c in hdr.iter(f"{HH}charPr") if c.get("id") == "23")
    para44 = next(p for p in hdr.iter(f"{HH}paraPr") if p.get("id") == "44")
    assert char23.get("height") == "2400"  # 24pt
    assert para44.find(f"{HH}align").get("horizontal") == "CENTER"


# ---------------------------------------------------------------------------
# 참고문헌 제목 (CSL 블록 앞 빈 줄 + "참고문헌" 제목, 번호 없는 새 스타일)
# ---------------------------------------------------------------------------


_CSL_MD = (
    "서론 문단.\n\n"
    "::::::: {#refs .references .csl-bib-body .hanging-indent}\n"
    "::: {#ref-a .csl-entry}\n"
    "Athey, S. 2019. *The Annals of Statistics* 47 (2).\n"
    ":::\n\n"
    "::: {#ref-b .csl-entry}\n"
    "Chernozhukov, V. 2018. *The Econometrics Journal* 21 (1).\n"
    ":::\n"
    ":::::::\n"
)


def test_bib_heading_prepended_before_references(tmp_path: Path, style_map) -> None:
    """참고문헌 항목들 앞에 빈 줄 + "참고문헌" 제목이 순서대로 들어간다."""
    seq = extract_paragraph_sequence(_convert(tmp_path, style_map, _CSL_MD))
    titles = [p for p in seq if p.text == "참고문헌"]
    assert len(titles) == 1
    idx = seq.index(titles[0])
    # 제목 직전은 빈 본문 단락(삽입형), 직후는 참고문헌 항목.
    assert _is_blank(seq[idx - 1]), "참고문헌 제목 앞에 빈 줄이 없다"
    assert seq[idx + 1].style_name == "참고문헌"
    assert seq[idx + 1].text.startswith("Athey")


def test_bib_heading_uses_no_number_style(tmp_path: Path, style_map) -> None:
    """제목 "참고문헌" 은 참고문헌제목 스타일이며 자동 번호가 없다."""
    out = _convert(tmp_path, style_map, _CSL_MD)
    seq = extract_paragraph_sequence(out)
    title = next(p for p in seq if p.text == "참고문헌")
    assert title.style_name == "참고문헌제목"
    # 해당 스타일의 charPr 는 개요 1(charPr 12) 과 동일, paraPr heading 은 NONE.
    with zipfile.ZipFile(out) as z:
        hdr = etree.fromstring(z.read("Contents/header.xml"))
    st = next(s for s in hdr.iter(f"{HH}style") if s.get("name") == "참고문헌제목")
    assert st.get("charPrIDRef") == "12"  # 개요 1 글씨체 재사용
    pp = next(p for p in hdr.iter(f"{HH}paraPr") if p.get("id") == st.get("paraPrIDRef"))
    assert pp.find(f"{HH}heading").get("type") == "NONE"  # 번호 없음
