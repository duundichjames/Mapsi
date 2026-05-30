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

    def test_text_no_quotes(self) -> None:
        # \text 는 따옴표 없이 내용 그대로 (표본 경향)
        res = hnc.to_hnc(r"\text{abc}")
        assert res.ok
        assert res.hnc == "abc"

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


# ---------------------------------------------------------------------------
# 정밀 표기 규칙: 첨자 사이 공백 + 항 구분 공백
# ---------------------------------------------------------------------------


def _hnc(latex: str) -> str:
    res = hnc.to_hnc(latex)
    assert res.ok, f"실패: {res.unsupported} / {res.parse_error}"
    return res.hnc


class TestPreciseSpacing:
    def test_space_between_sub_and_sup(self) -> None:
        # 같은 base 에 sub·sup 모두 → 둘 사이 공백 (요구 1)
        assert _hnc(r"\sum_{i=1}^{n}") == "sum_{i=1} ^{n}"

    def test_lone_sub_no_extra_space(self) -> None:
        assert _hnc(r"x_{i}") == "x_{i}"

    def test_lone_sup_no_extra_space(self) -> None:
        assert _hnc(r"x^{2}") == "x^{2}"

    def test_operator_spacing(self) -> None:
        # 본문 연산자 좌우 공백 (요구 2) — 표본[*] a^2 + b^2 = c^2 경향
        assert _hnc(r"a^2 + b^2 = c^2") == "a^{2} + b^{2} = c^{2}"

    def test_word_operators_spaced(self) -> None:
        assert _hnc(r"A \times B \cdot C") == "A times B cdot C"

    def test_digits_stay_glued(self) -> None:
        # 숫자 항은 붙어야 한다 (1 0 0 처럼 깨지면 안 됨)
        assert _hnc(r"x \times 100") == "x times 100"

    def test_subscript_internal_glued(self) -> None:
        # 첨자 내부는 붙임 — 표본 _{t-1}, _{i,t} 경향
        assert _hnc(r"국고채_{t-1}") == "국고채_{t-1}"
        assert _hnc(r"w_{i,t}") == "w_{i,t}"

    def test_subscripted_word_not_split(self) -> None:
        # 첨자 붙은 한글 항 앞에 공백이 끼지 않아야 한다
        assert _hnc(r"대위변제율_t") == "대위변제율_{t}"


class TestTextAndSpacing:
    def test_text_without_space_no_quotes(self) -> None:
        # 공백 없는 \text 도 따옴표 없이 내용 그대로 (일관 규칙)
        assert _hnc(r"\text{premium}") == "premium"

    def test_text_with_space_becomes_tilde(self) -> None:
        # \text 내부의 의도된 공백 → 틸드
        assert _hnc(r"\text{여러 단어}") == "여러~단어"

    def test_bare_korean_term_not_quoted(self) -> None:
        out = _hnc("저신용자비율")
        assert out == "저신용자비율"
        assert '"' not in out

    def test_explicit_space_commands_become_tilde(self) -> None:
        # \, \; \: \  → 틸드 1 개, 양옆 항에 붙는다
        assert _hnc(r"a\,b") == "a~b"
        assert _hnc(r"a\;b") == "a~b"
        assert _hnc(r"a\ b") == "a~b"

    def test_quad_widths_use_multiple_tildes(self) -> None:
        # 넓은 간격: \quad → ~~, \qquad → ~~~~ (quad 의 2 배 폭)
        assert _hnc(r"a\quad b") == "a~~b"
        assert _hnc(r"a\qquad b") == "a~~~~b"

    def test_normal_space_has_no_tilde(self) -> None:
        # 일반 공백(a + b) 은 항 구분 공백만, 틸드 끼어들지 않음
        assert _hnc(r"a + b") == "a + b"
        assert "~" not in _hnc(r"\alpha + \beta")


class TestSampleLikeness:
    """표본 hp:script 의 대표 경향과 변환 결과를 비교 (완전 일치 아님)."""

    def test_sample04_industry_risk_index(self) -> None:
        # 표본[04]: 업종위험가중지수_t = sum_i w_{i,t} times r_i
        out = _hnc(r"R_t = \sum_i w_{i,t} \times r_i")
        assert " = " in out  # 항 구분 공백
        assert "sum" in out and "times" in out  # 매핑
        assert "w_{i,t}" in out  # 첨자 내부 붙임
        assert "1 0 0" not in out

    def test_sample26_sum_sub_then_sup(self) -> None:
        # 표본[26]: ... sum_{i=1} ^3 ... — sub 뒤 공백 후 sup
        out = _hnc(r"\frac{1}{3}\sum_{i=1}^{3}")
        assert "_{i=1} ^{3}" in out
        assert "{1} over {3}" in out
