"""LaTeX 구문 트리 → 한/글 HNC 수식 문자열 변환 (매핑 + 기본 변환 단계).

:mod:`mapsi.math.latex_parser` 가 세운 트리를 HNC 문자열로 옮긴다. 명령어
대응은 **데이터 테이블(딕셔너리)** 로 분리해 두어 항목 추가가 쉽도록 했다
(요구 1). 이번 단계는 매핑과 기본 구조 변환까지만 수행하며, 첨자 사이
공백·항 구분 정밀 공백·9 자 따옴표 등 세밀한 표기 규칙은 다음 단계로
미룬다(요구 5).

미지원 명령어(테이블에 없는 명령어) 를 만나면 예외를 던지지 않고
:attr:`HncResult.unsupported` 에 수집 + 로그를 남긴 뒤 ``ok=False`` 신호를
실어, 호출자가 LaTeX 원문 보존 폴백으로 갈 수 있게 한다(요구 4).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .latex_parser import (
    Align,
    Command,
    Environment,
    Group,
    Node,
    RowSep,
    Script,
    Text,
    parse,
)


__all__ = ["HncResult", "to_hnc", "convert_tree"]

_LOG = logging.getLogger(__name__)


# ===========================================================================
# 매핑 테이블 (코드와 분리된 데이터; 항목 추가만으로 확장 가능)
# ===========================================================================

# -- 인자 0: 기호로 치환되는 명령어 -----------------------------------------

#: 큰 연산자.
_BIG_OPERATORS = {
    "sum": "sum",
    "prod": "prod",
    "int": "int",
    "oint": "oint",
    "lim": "lim",
    "bigcup": "union",
    "bigcap": "inter",
}

#: 그리스 소문자 (var- 변형은 기본 글자에 합류).
_GREEK_LOWER = {
    "alpha": "alpha",
    "beta": "beta",
    "gamma": "gamma",
    "delta": "delta",
    "epsilon": "epsilon",
    "varepsilon": "epsilon",
    "zeta": "zeta",
    "eta": "eta",
    "theta": "theta",
    "vartheta": "theta",
    "iota": "iota",
    "kappa": "kappa",
    "varkappa": "kappa",
    "lambda": "lambda",
    "mu": "mu",
    "nu": "nu",
    "xi": "xi",
    "pi": "pi",
    "varpi": "pi",
    "rho": "rho",
    "varrho": "rho",
    "sigma": "sigma",
    "varsigma": "sigma",
    "tau": "tau",
    "upsilon": "upsilon",
    "phi": "phi",
    "varphi": "phi",
    "chi": "chi",
    "psi": "psi",
    "omega": "omega",
}

#: 그리스 대문자.
_GREEK_UPPER = {
    "Gamma": "Gamma",
    "Delta": "Delta",
    "Theta": "Theta",
    "Lambda": "Lambda",
    "Xi": "Xi",
    "Pi": "Pi",
    "Sigma": "Sigma",
    "Upsilon": "Upsilon",
    "Phi": "Phi",
    "Psi": "Psi",
    "Omega": "Omega",
}

#: 연산·관계 기호.
_RELATIONS = {
    "times": "times",
    "cdot": "cdot",
    "div": "div",
    "leq": "leq",
    "le": "leq",
    "geq": "geq",
    "ge": "geq",
    "neq": "neq",
    "ne": "neq",
    "approx": "approx",
    "equiv": "equiv",
    "in": "in",
    "subseteq": "subseteq",
    "cup": "union",
    "cap": "inter",
    "pm": "plusminus",
}

#: 화살표.
_ARROWS = {
    "rightarrow": "rarrow",
    "to": "rarrow",
    "leftarrow": "larrow",
    "Rightarrow": "RARROW",
    "leftrightarrow": "lrarrow",
}

#: 특수 기호 및 구분기호 (인자 0).
_SPECIALS = {
    "infty": "inf",
    "partial": "partial",
    "cdots": "cdots",
    "ldots": "ldots",
    "left": "left",
    "right": "right",
    "lvert": "vert",
    "rvert": "vert",
    "vert": "vert",
}

#: 인자 0 명령어 통합 테이블 (위 분류들을 합친 것).
_SYMBOLS: dict[str, str] = {
    **_BIG_OPERATORS,
    **_GREEK_LOWER,
    **_GREEK_UPPER,
    **_RELATIONS,
    **_ARROWS,
    **_SPECIALS,
}

# -- 인자 1 이상: 구조를 동반하는 명령어 ------------------------------------

#: 분수 계열 (인자 2) → ``{a} over {b}``.
_FRACTIONS = {"frac", "dfrac", "tfrac"}

#: 장식 계열 (인자 1) → ``<hnc> {x}``.
_DECORATIONS = {
    "hat": "hat",
    "bar": "bar",
    "vec": "vec",
    "dot": "dot",
    "tilde": "tilde",
}

#: 글꼴 계열 (인자 1) → ``<hnc> {x}``.
_FONTS = {
    "mathbf": "bold",
    "boldsymbol": "bold",
    "mathrm": "rm",
}

# -- 환경 → HNC 래퍼 --------------------------------------------------------

#: 행렬 계열 중 그대로 매칭되는 래퍼 (array 는 matrix 에 준함).
_ENV_MATRIX_WRAP = {
    "matrix": "matrix",
    "pmatrix": "pmatrix",
    "bmatrix": "bmatrix",
    "array": "matrix",
    "vmatrix": "dmatrix",
}

#: 정렬 계열 → ``eqalign{}``.
_ENV_ALIGN = {
    "aligned",
    "align",
    "alignat",
    "gathered",
    "gather",
    "split",
    "eqnarray",
}

#: 분기 계열 → ``cases{}``.
_ENV_CASES = {"cases", "dcases"}


# ===========================================================================
# 결과 컨테이너
# ===========================================================================


@dataclass
class HncResult:
    """변환 결과. ``ok=False`` 면 호출자는 LaTeX 원문 폴백으로 가야 한다."""

    ok: bool
    hnc: str
    unsupported: list[str] = field(default_factory=list)
    parse_error: str | None = None


# ===========================================================================
# 변환기
# ===========================================================================


class _HncConverter:
    """트리를 HNC 문자열로 옮기며 미지원 명령어를 수집한다 (내부용)."""

    def __init__(self) -> None:
        self.unsupported: list[str] = []

    # -- 시퀀스/인자 헬퍼 --------------------------------------------------

    def render_seq(self, children: list[Node]) -> str:
        """노드 리스트를 최소 공백(한 칸) 으로 이어 붙인다 (요구 5)."""
        return " ".join(self._render(c) for c in children)

    def _arg(self, node: Node | None) -> str:
        """인자 렌더링: ``Group`` 은 바깥 중괄호를 벗겨 내용만 돌려준다."""
        if node is None:
            return ""
        if isinstance(node, Group):
            return self.render_seq(node.children)
        return self._render(node)

    # -- 노드 디스패치 ------------------------------------------------------

    def _render(self, node: Node) -> str:
        if isinstance(node, Text):
            return node.value
        if isinstance(node, Group):
            return "{" + self.render_seq(node.children) + "}"
        if isinstance(node, Script):
            return self._render_script(node)
        if isinstance(node, Command):
            return self._render_command(node)
        if isinstance(node, Environment):
            return self._render_env(node)
        if isinstance(node, Align):
            return "&"
        if isinstance(node, RowSep):
            return "#"
        # 알 수 없는 노드 종류 — 보수적으로 빈 문자열
        return ""

    def _render_script(self, node: Script) -> str:
        base = node.base
        # 특수: \underbrace{x}_{y} → underbrace {y} {x}
        if (
            isinstance(base, Command)
            and base.name == "underbrace"
            and node.sub is not None
        ):
            inner = self._arg(base.args[0]) if base.args else ""
            under = self._arg(node.sub)
            out = "underbrace {" + under + "} {" + inner + "}"
            if node.sup is not None:
                out += "^{" + self._arg(node.sup) + "}"
            return out
        out = self._render(base)
        # 첨자 구조는 LaTeX 와 공유: 아래첨자 → 위첨자 순 (요구 2)
        if node.sub is not None:
            out += "_{" + self._arg(node.sub) + "}"
        if node.sup is not None:
            out += "^{" + self._arg(node.sup) + "}"
        return out

    def _render_command(self, cmd: Command) -> str:
        name = cmd.name
        if name in _FRACTIONS:
            a = self._arg(cmd.args[0]) if len(cmd.args) > 0 else ""
            b = self._arg(cmd.args[1]) if len(cmd.args) > 1 else ""
            return "{" + a + "} over {" + b + "}"
        if name == "sqrt":
            x = self._arg(cmd.args[0]) if cmd.args else ""
            if cmd.opt is not None:  # \sqrt[n]{x} → root {n} of {x}
                return "root {" + self._arg(cmd.opt) + "} of {" + x + "}"
            return "sqrt {" + x + "}"
        if name == "text":
            return '"' + self._literal(cmd.args[0]) + '"' if cmd.args else '""'
        if name == "underbrace":  # 첨자 없이 단독으로 온 경우
            return "underbrace {" + (self._arg(cmd.args[0]) if cmd.args else "") + "}"
        if name in _DECORATIONS:
            return _DECORATIONS[name] + " {" + (
                self._arg(cmd.args[0]) if cmd.args else ""
            ) + "}"
        if name in _FONTS:
            return _FONTS[name] + " {" + (
                self._arg(cmd.args[0]) if cmd.args else ""
            ) + "}"
        if name in _SYMBOLS:
            return _SYMBOLS[name]
        # 미지원 (요구 4): 수집 + 로그, 부분 결과엔 원문 표기만 남긴다.
        self.unsupported.append(name)
        _LOG.warning("미지원 LaTeX 명령어: \\%s", name)
        return "\\" + name

    def _render_env(self, env: Environment) -> str:
        body = self._render_grid(env.rows)
        name = env.name
        if name in _ENV_MATRIX_WRAP:
            return _ENV_MATRIX_WRAP[name] + "{" + body + "}"
        if name in _ENV_ALIGN:
            return "eqalign{" + body + "}"
        if name in _ENV_CASES:
            return "cases{" + body + "}"
        # HNC 전용 명령이 없는 환경은 left/right 묶음으로 우회 (요구 3)
        if name == "Bmatrix":
            return "left lbrace matrix{" + body + "} right rbrace"
        if name == "Vmatrix":
            return "left Vert matrix{" + body + "} right Vert"
        # 파서가 지원 목록만 통과시키므로 여기 도달은 이론상 없음.
        self.unsupported.append("env:" + name)
        return ""

    def _render_grid(self, rows: list[list[Group]]) -> str:
        """행 → ``#``, 칸 → ``&`` 로 직렬화 (요구 3)."""
        row_strs = []
        for row in rows:
            row_strs.append(" & ".join(self.render_seq(cell.children) for cell in row))
        return " # ".join(row_strs)

    def _literal(self, node: Node) -> str:
        """``\\text{...}`` 내용은 공백 없이 글자만 잇는다 (따옴표 규칙은 다음 단계)."""
        if isinstance(node, Group):
            return "".join(
                c.value for c in node.children if isinstance(c, Text)
            )
        if isinstance(node, Text):
            return node.value
        return ""


def _normalize_spaces(text: str) -> str:
    """최소 공백 정리: 연속 공백을 한 칸으로, 양끝 공백 제거 (요구 5)."""
    return re.sub(r"\s+", " ", text).strip()


# ===========================================================================
# 공개 진입점
# ===========================================================================


def convert_tree(tree: Group) -> HncResult:
    """파싱된 트리(루트 :class:`Group`) 를 HNC 문자열로 변환한다."""
    conv = _HncConverter()
    rendered = _normalize_spaces(conv.render_seq(tree.children))
    ok = not conv.unsupported
    return HncResult(ok=ok, hnc=rendered, unsupported=list(conv.unsupported))


def to_hnc(latex: str) -> HncResult:
    """LaTeX 수식 문자열을 파싱→변환하여 HNC 결과를 돌려준다.

    파싱 실패 또는 미지원 명령어가 있으면 ``ok=False`` 로 표시해, 호출자가
    LaTeX 원문 보존 폴백을 선택할 수 있게 한다. 예외는 던지지 않는다.
    """
    pr = parse(latex)
    if not pr.ok:
        return HncResult(ok=False, hnc="", unsupported=[], parse_error=pr.error)
    assert pr.tree is not None
    return convert_tree(pr.tree)
