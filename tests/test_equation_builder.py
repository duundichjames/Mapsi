"""``mapsi.builder.equation.build_equation`` 단위 테스트.

한/글 실측 표본 기준의 고정 속성·자식 구조와, HNC 변환 성공/실패(폴백)
동작을 확인한다.
"""

from __future__ import annotations

from lxml import etree

from mapsi.builder.equation import build_equation


_HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def _child(eq: etree._Element, local: str) -> etree._Element:
    found = eq.find(f"{_HP}{local}")
    assert found is not None, f"자식 {local!r} 누락"
    return found


def _script_text(eq: etree._Element) -> str:
    return _child(eq, "script").text or ""


class TestStructure:
    def test_root_tag_and_children_order(self) -> None:
        eq = build_equation(r"\frac{a}{b}", False)
        assert etree.QName(eq).localname == "equation"
        assert [etree.QName(c).localname for c in eq] == [
            "sz",
            "pos",
            "outMargin",
            "script",
        ]

    def test_fixed_attrs_present(self) -> None:
        eq = build_equation(r"x^2", False)
        assert eq.get("numberingType") == "EQUATION"
        assert eq.get("textWrap") == "TOP_AND_BOTTOM"
        assert eq.get("textFlow") == "BOTH_SIDES"
        assert eq.get("lock") == "0"
        assert eq.get("dropcapstyle") == "None"
        assert eq.get("version") == "Equation Version 60"
        assert eq.get("textColor") == "#000000"
        assert eq.get("baseUnit") == "1000"
        assert eq.get("lineMode") == "CHAR"
        assert eq.get("font") == "HancomEQN"
        assert eq.get("baseLine") == "72"

    def test_child_attrs(self) -> None:
        eq = build_equation(r"x", False)
        sz = _child(eq, "sz")
        assert sz.get("width") == "4627"
        assert sz.get("height") == "1163"
        assert sz.get("widthRelTo") == "ABSOLUTE"
        assert sz.get("heightRelTo") == "ABSOLUTE"
        assert sz.get("protect") == "0"

        pos = _child(eq, "pos")
        assert pos.get("treatAsChar") == "1"
        assert pos.get("vertRelTo") == "PARA"
        assert pos.get("horzAlign") == "LEFT"

        om = _child(eq, "outMargin")
        assert (om.get("left"), om.get("right"), om.get("top"), om.get("bottom")) == (
            "56",
            "56",
            "0",
            "0",
        )

    def test_script_xml_space_preserve(self) -> None:
        eq = build_equation(r"x", False)
        assert _child(eq, "script").get(_XML_SPACE) == "preserve"

    def test_id_and_zorder_present(self) -> None:
        eq = build_equation(r"x", False)
        assert eq.get("id")  # 비어 있지 않음
        assert eq.get("zOrder") == "0"

    def test_ids_are_unique(self) -> None:
        a = build_equation(r"a", False)
        b = build_equation(r"b", False)
        assert a.get("id") != b.get("id")


class TestConversionAndFallback:
    def test_success_puts_hnc_in_script(self) -> None:
        eq = build_equation(r"\frac{a}{b}", False)
        assert _script_text(eq) == "{a} over {b}"

    def test_unsupported_falls_back_to_latex(self) -> None:
        # 미지원 명령어 → 폴백으로 LaTeX 원문 보존
        eq = build_equation(r"\foobar{x}", False)
        assert _script_text(eq) == r"\foobar{x}"

    def test_parse_failure_falls_back_to_latex(self) -> None:
        eq = build_equation("{a", True)  # 짝 안 맞는 중괄호 → 파싱 실패
        assert _script_text(eq) == "{a"


class TestDisplayUnused:
    def test_display_does_not_change_structure(self) -> None:
        # display 는 hp:equation 속성에 영향을 주지 않아야 한다 (단락 배치에서 처리).
        inline = build_equation(r"x^2", False)
        block = build_equation(r"x^2", True)

        def attrs_minus_id(el: etree._Element) -> dict[str, str]:
            return {k: v for k, v in el.attrib.items() if k not in ("id", "zOrder")}

        assert attrs_minus_id(inline) == attrs_minus_id(block)
        assert _script_text(inline) == _script_text(block)
