"""``mapsi.math.hnc`` (트리 → HNC 변환) 단위 테스트.

표기 규칙(첨자 공백·9 자 따옴표 등) 이 아직 없으므로 표본의 hp:script 와
정확히 일치하지는 않는다. 대표 입력 몇 개에 대해 HNC '구조' 가 의도대로
나오는지와, 미지원 명령어가 폴백 신호를 내는지를 확인한다.
"""

from __future__ import annotations

from mapsi.math import hnc


def _packed(latex: str) -> str:
    """공백을 모두 제거해 구조만 비교한다 (정밀 공백은 다음 단계)."""
    res = hnc.to_hnc(latex)
    assert res.ok, f"예상치 못한 실패: {res.unsupported} / {res.parse_error}"
    return res.hnc.replace(" ", "")


# ---------------------------------------------------------------------------
# 분수/근호
# ---------------------------------------------------------------------------


class TestFractionRoot:
    def test_frac(self) -> None:
        assert _packed(r"\frac{a}{b}") == "{a}over{b}"

    def test_dfrac_alias(self) -> None:
        assert _packed(r"\dfrac{a}{b}") == "{a}over{b}"

    def test_sqrt(self) -> None:
        assert _packed(r"\sqrt{x}") == "sqrt{x}"

    def test_nth_root_optional_arg(self) -> None:
        assert _packed(r"\sqrt[n]{x}") == "root{n}of{x}"


# ---------------------------------------------------------------------------
# 첨자 / 큰 연산자
# ---------------------------------------------------------------------------


class TestScriptsOperators:
    def test_superscript_preserved(self) -> None:
        assert _packed(r"x^{2}") == "x^{2}"

    def test_subscript_preserved(self) -> None:
        assert _packed(r"x_{i}") == "x_{i}"

    def test_sum_sub_sup(self) -> None:
        assert _packed(r"\sum_{i=1}^{n}") == "sum_{i=1}^{n}"

    def test_big_operator_mapping(self) -> None:
        assert _packed(r"\bigcup") == "union"
        assert _packed(r"\prod") == "prod"


# ---------------------------------------------------------------------------
# 기호 매핑 (그리스/관계/화살표/특수)
# ---------------------------------------------------------------------------


class TestSymbols:
    def test_greek_lower_and_variant(self) -> None:
        assert _packed(r"\alpha + \beta") == "alpha+beta"
        assert _packed(r"\varepsilon") == "epsilon"  # 변형 → 기본 글자

    def test_greek_upper(self) -> None:
        assert _packed(r"\Delta") == "Delta"

    def test_relations(self) -> None:
        assert _packed(r"\leq") == "leq"
        assert _packed(r"\pm") == "plusminus"
        assert _packed(r"\cup") == "union"

    def test_arrows(self) -> None:
        assert _packed(r"\rightarrow") == "rarrow"
        assert _packed(r"\to") == "rarrow"
        assert _packed(r"\Rightarrow") == "RARROW"

    def test_specials_and_delims(self) -> None:
        assert _packed(r"\infty") == "inf"
        assert _packed(r"\vert") == "vert"


# ---------------------------------------------------------------------------
# 장식 / 글꼴 / underbrace
# ---------------------------------------------------------------------------


class TestDecorationFont:
    def test_decoration(self) -> None:
        assert _packed(r"\hat{x}") == "hat{x}"
        assert _packed(r"\vec{v}") == "vec{v}"

    def test_font_bold_rm(self) -> None:
        assert _packed(r"\mathbf{x}") == "bold{x}"
        assert _packed(r"\boldsymbol{y}") == "bold{y}"
        assert _packed(r"\mathrm{d}") == "rm{d}"

    def test_text_wrapped_in_quotes(self) -> None:
        res = hnc.to_hnc(r"\text{abc}")
        assert res.ok
        assert res.hnc == '"abc"'

    def test_underbrace_special(self) -> None:
        assert _packed(r"\underbrace{x}_{y}") == "underbrace{y}{x}"


# ---------------------------------------------------------------------------
# 환경 변환
# ---------------------------------------------------------------------------


class TestEnvironments:
    def test_bmatrix(self) -> None:
        assert _packed(r"\begin{bmatrix}a & b \\ c & d\end{bmatrix}") == (
            "bmatrix{a&b#c&d}"
        )

    def test_pmatrix(self) -> None:
        assert _packed(r"\begin{pmatrix}1 & 2\end{pmatrix}") == "pmatrix{1&2}"

    def test_vmatrix_to_dmatrix(self) -> None:
        assert _packed(r"\begin{vmatrix}a & b\end{vmatrix}") == "dmatrix{a&b}"

    def test_Bmatrix_left_right_workaround(self) -> None:
        out = _packed(r"\begin{Bmatrix}a & b\end{Bmatrix}")
        assert out.startswith("leftlbracematrix{")
        assert out.endswith("}rightrbrace")

    def test_cases(self) -> None:
        out = _packed(r"\begin{cases} x & x>0 \\ -x & x<0 \end{cases}")
        assert out == "cases{x&x>0#-x&x<0}"

    def test_aligned_to_eqalign(self) -> None:
        out = _packed(r"\begin{aligned} a &= b \\ c &= d \end{aligned}")
        assert out == "eqalign{a&=b#c&=d}"

    def test_array_ignores_col_spec_in_body(self) -> None:
        # array 는 matrix 에 준해 처리, 열 지정자는 본문 셀에 섞이지 않음
        out = _packed(r"\begin{array}{cc} 1 & 2 \\ 3 & 4 \end{array}")
        assert out == "matrix{1&2#3&4}"

    def test_nested_environment(self) -> None:
        out = _packed(
            r"\begin{bmatrix}\begin{pmatrix}a\end{pmatrix} & b\end{bmatrix}"
        )
        assert out == "bmatrix{pmatrix{a}&b}"


# ---------------------------------------------------------------------------
# 미지원 / 폴백 신호 (요구 4)
# ---------------------------------------------------------------------------


class TestUnsupportedFallback:
    def test_unknown_command_signals_failure(self) -> None:
        res = hnc.to_hnc(r"\foobar{x}")
        assert res.ok is False
        assert "foobar" in res.unsupported

    def test_partial_does_not_raise(self) -> None:
        # 미지원이 섞여도 예외 없이 ok=False 로만 표시되어야 한다.
        res = hnc.to_hnc(r"\alpha + \weirdcmd")
        assert res.ok is False
        assert "weirdcmd" in res.unsupported

    def test_parse_failure_propagates(self) -> None:
        res = hnc.to_hnc("{a")  # 짝 안 맞는 중괄호 → 파싱 실패
        assert res.ok is False
        assert res.parse_error is not None
