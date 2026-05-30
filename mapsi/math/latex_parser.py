"""LaTeX 수식 → 구문 트리 파서 (HNC 변환 전 단계, C 영역).

본 모듈은 LaTeX 수식 문자열을 **토크나이저** → **파서** 로 처리해 구문
트리(AST) 로 세우는 골격만 담당한다. 한/글 HNC 수식 문법으로의 *변환*
(매핑) 은 후속 단계의 책임이며, 이 모듈은 변환을 일절 수행하지 않는다.

설계 요약
---------
* 토큰 종류 (:class:`TokenKind`):

  ``COMMAND``  ``\\frac`` ``\\alpha`` 등 백슬래시로 시작하는 토큰 (값은
               백슬래시를 뗀 이름). ``\\,`` 처럼 백슬래시 + 비문자 1 자도
               단일 문자 이름의 명령어로 본다.
  ``LBRACE`` / ``RBRACE``  중괄호 ``{`` ``}``.
  ``SUP`` / ``SUB``        위첨자 ``^`` / 아래첨자 ``_``.
  ``ALIGN``                정렬 기호 ``&``.
  ``ROWSEP``               행 구분 ``\\\\``.
  ``CHAR``                 그 외 일반 문자 1 자 (영숫자·한글·연산자 등).
                           수식 공백은 LaTeX 관례대로 토큰화 단계에서 버린다.

* 트리 노드 (모두 :class:`Node` 하위):

  :class:`Text`     문자 1 자 원자.
  :class:`Group`    ``{...}`` 그룹 및 루트 시퀀스 (자식 노드 묶음).
  :class:`Command`  명령어 + 인자 목록 (``\\frac`` 은 인자 2 개 등).
  :class:`Script`   기준 원자에 위/아래 첨자를 붙인 노드.
  :class:`Align` / :class:`RowSep`  구조적 구분 기호.

* 실패 정책 (요구 4): 파싱 불가능한 입력에서도 **예외를 호출자에게 던지지
  않는다**. :func:`parse` 는 항상 :class:`ParseResult` 를 돌려주며, 실패
  시 ``ok=False`` 와 ``error`` 메시지를 담되 ``source`` 에 원본 문자열을
  보존한다. 후속 폴백에서 LaTeX 원문을 그대로 쓰기 위함이다.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


__all__ = [
    "TokenKind",
    "Token",
    "Node",
    "Text",
    "Group",
    "Command",
    "Script",
    "Align",
    "RowSep",
    "ParseResult",
    "LatexParseError",
    "tokenize",
    "parse",
]


class LatexParseError(Exception):
    """파서 내부에서 발생하는 구문 오류. :func:`parse` 경계에서 흡수된다."""


# ---------------------------------------------------------------------------
# 토크나이저
# ---------------------------------------------------------------------------


class TokenKind(enum.Enum):
    COMMAND = "command"
    LBRACE = "lbrace"
    RBRACE = "rbrace"
    SUP = "sup"
    SUB = "sub"
    ALIGN = "align"
    ROWSEP = "rowsep"
    CHAR = "char"


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    value: str


def tokenize(latex: str) -> list[Token]:
    """LaTeX 수식 문자열을 토큰 리스트로 끊는다.

    Args:
        latex: ``$``/``$$`` delimiter 가 제거된 LaTeX 수식 본문.

    Returns:
        :class:`Token` 리스트. 수식 공백은 버려진다.

    Raises:
        LatexParseError: 문자열이 백슬래시로 끝나는 등 토큰화 불가 시.
    """
    tokens: list[Token] = []
    i = 0
    n = len(latex)
    while i < n:
        c = latex[i]
        if c == "\\":
            if i + 1 < n and latex[i + 1] == "\\":
                tokens.append(Token(TokenKind.ROWSEP, "\\\\"))
                i += 2
                continue
            j = i + 1
            if j >= n:
                raise LatexParseError("문자열이 백슬래시로 끝남")
            if latex[j].isalpha():
                k = j
                while k < n and latex[k].isalpha():
                    k += 1
                tokens.append(Token(TokenKind.COMMAND, latex[j:k]))
                i = k
            else:
                # \, \{ \% 등 백슬래시 + 비문자 1 자 → 단일 문자 명령어
                tokens.append(Token(TokenKind.COMMAND, latex[j]))
                i = j + 1
        elif c == "{":
            tokens.append(Token(TokenKind.LBRACE, c))
            i += 1
        elif c == "}":
            tokens.append(Token(TokenKind.RBRACE, c))
            i += 1
        elif c == "^":
            tokens.append(Token(TokenKind.SUP, c))
            i += 1
        elif c == "_":
            tokens.append(Token(TokenKind.SUB, c))
            i += 1
        elif c == "&":
            tokens.append(Token(TokenKind.ALIGN, c))
            i += 1
        elif c.isspace():
            i += 1  # 수식 내 공백은 LaTeX 관례대로 무시
        else:
            tokens.append(Token(TokenKind.CHAR, c))
            i += 1
    return tokens


# ---------------------------------------------------------------------------
# 트리 노드
# ---------------------------------------------------------------------------


@dataclass
class Node:
    """모든 트리 노드의 베이스. ``pretty`` 로 들여쓰기 표시를 낸다."""

    def pretty(self, indent: int = 0) -> str:  # pragma: no cover - 추상
        raise NotImplementedError


def _ind(level: int) -> str:
    return "  " * level


@dataclass
class Text(Node):
    """문자 1 자 원자 (영숫자·한글·연산자 등)."""

    value: str

    def pretty(self, indent: int = 0) -> str:
        return f"{_ind(indent)}Text {self.value!r}"


@dataclass
class Group(Node):
    """``{...}`` 그룹 또는 루트 시퀀스. 자식 노드를 순서대로 묶는다."""

    children: list[Node] = field(default_factory=list)

    def pretty(self, indent: int = 0) -> str:
        lines = [f"{_ind(indent)}Group"]
        for child in self.children:
            lines.append(child.pretty(indent + 1))
        return "\n".join(lines)


@dataclass
class Command(Node):
    """명령어와 그 인자들. ``\\frac{a}{b}`` → ``Command('frac', [..,..])``."""

    name: str
    args: list[Node] = field(default_factory=list)

    def pretty(self, indent: int = 0) -> str:
        lines = [f"{_ind(indent)}Command \\{self.name}"]
        for k, arg in enumerate(self.args):
            lines.append(f"{_ind(indent + 1)}arg[{k}]:")
            lines.append(arg.pretty(indent + 2))
        return "\n".join(lines)


@dataclass
class Script(Node):
    """기준 원자에 위/아래 첨자를 붙인 노드. ``x^2`` → ``Script(Text, sup)``."""

    base: Node
    sup: Node | None = None
    sub: Node | None = None

    def pretty(self, indent: int = 0) -> str:
        lines = [f"{_ind(indent)}Script"]
        lines.append(f"{_ind(indent + 1)}base:")
        lines.append(self.base.pretty(indent + 2))
        if self.sup is not None:
            lines.append(f"{_ind(indent + 1)}sup:")
            lines.append(self.sup.pretty(indent + 2))
        if self.sub is not None:
            lines.append(f"{_ind(indent + 1)}sub:")
            lines.append(self.sub.pretty(indent + 2))
        return "\n".join(lines)


@dataclass
class Align(Node):
    """정렬 기호 ``&``."""

    def pretty(self, indent: int = 0) -> str:
        return f"{_ind(indent)}Align '&'"


@dataclass
class RowSep(Node):
    r"""행 구분 ``\\``."""

    def pretty(self, indent: int = 0) -> str:
        return f"{_ind(indent)}RowSep '\\\\'"


# ---------------------------------------------------------------------------
# 파서
# ---------------------------------------------------------------------------

# 인자를 받는 명령어의 인자 개수(arity). 표에 없으면 0 (= 기호 명령어).
# HNC 매핑이 아니라 트리 구조 결정만을 위한 최소 표이며, 확장 가능하다.
_COMMAND_ARITY: dict[str, int] = {
    "frac": 2,
    "dfrac": 2,
    "tfrac": 2,
    "binom": 2,
    "sqrt": 1,
    "overline": 1,
    "underline": 1,
    "hat": 1,
    "bar": 1,
    "vec": 1,
    "tilde": 1,
    "text": 1,
    "mathbf": 1,
    "mathrm": 1,
}


class _Parser:
    """토큰 리스트를 트리로 세우는 재귀 하향 파서 (내부용)."""

    def __init__(self, tokens: list[Token]) -> None:
        self._toks = tokens
        self._pos = 0

    def _peek(self) -> Token | None:
        if self._pos < len(self._toks):
            return self._toks[self._pos]
        return None

    def _advance(self) -> Token:
        tok = self._toks[self._pos]
        self._pos += 1
        return tok

    def parse_root(self) -> Group:
        children = self._parse_sequence(stop=None)
        leftover = self._peek()
        if leftover is not None:
            raise LatexParseError(f"짝이 맞지 않는 토큰: {leftover.value!r}")
        return Group(children)

    def _parse_sequence(self, stop: TokenKind | None) -> list[Node]:
        children: list[Node] = []
        while True:
            tok = self._peek()
            if tok is None:
                if stop is not None:
                    raise LatexParseError("닫는 중괄호 '}' 가 누락됨")
                break
            if stop is not None and tok.kind == stop:
                break
            if tok.kind == TokenKind.RBRACE:
                # stop 이 None 인데 } 를 만남 → 여는 괄호 없는 }
                raise LatexParseError("여는 중괄호 없는 '}'")
            if tok.kind == TokenKind.ALIGN:
                self._advance()
                children.append(Align())
                continue
            if tok.kind == TokenKind.ROWSEP:
                self._advance()
                children.append(RowSep())
                continue
            atom = self._parse_atom()
            children.append(self._maybe_scripts(atom))
        return children

    def _maybe_scripts(self, base: Node) -> Node:
        sup: Node | None = None
        sub: Node | None = None
        while True:
            tok = self._peek()
            if tok is None:
                break
            if tok.kind == TokenKind.SUP:
                if sup is not None:
                    raise LatexParseError("위첨자 '^' 가 중복됨")
                self._advance()
                sup = self._parse_argument("^")
            elif tok.kind == TokenKind.SUB:
                if sub is not None:
                    raise LatexParseError("아래첨자 '_' 가 중복됨")
                self._advance()
                sub = self._parse_argument("_")
            else:
                break
        if sup is None and sub is None:
            return base
        return Script(base=base, sup=sup, sub=sub)

    def _parse_atom(self) -> Node:
        tok = self._peek()
        if tok is None:
            raise LatexParseError("원자를 기대했으나 수식이 끝남")
        if tok.kind == TokenKind.LBRACE:
            self._advance()
            children = self._parse_sequence(stop=TokenKind.RBRACE)
            self._advance()  # RBRACE 소비 (_parse_sequence 가 존재를 보장)
            return Group(children)
        if tok.kind == TokenKind.CHAR:
            self._advance()
            return Text(tok.value)
        if tok.kind == TokenKind.COMMAND:
            self._advance()
            arity = _COMMAND_ARITY.get(tok.value, 0)
            args = [self._parse_argument(f"\\{tok.value}") for _ in range(arity)]
            return Command(tok.value, args)
        if tok.kind in (TokenKind.SUP, TokenKind.SUB):
            raise LatexParseError("첨자 기호 앞에 기준 원자가 없음")
        raise LatexParseError(f"예상치 못한 토큰: {tok.value!r}")

    def _parse_argument(self, who: str) -> Node:
        """명령어 인자 / 첨자 본문 1 개를 읽는다 (그룹 또는 단일 원자)."""
        tok = self._peek()
        if tok is None:
            raise LatexParseError(f"{who} 의 인자가 없음")
        if tok.kind in (TokenKind.LBRACE, TokenKind.CHAR, TokenKind.COMMAND):
            return self._parse_atom()
        raise LatexParseError(f"{who} 의 인자로 부적절한 토큰: {tok.value!r}")


# ---------------------------------------------------------------------------
# 공개 진입점
# ---------------------------------------------------------------------------


@dataclass
class ParseResult:
    """파싱 결과. 실패해도 ``source`` 에 원본을 보존한다 (요구 4)."""

    ok: bool
    source: str
    tree: Group | None = None
    error: str | None = None

    def pretty(self) -> str:
        """트리(성공) 또는 실패 표시(실패) 를 사람이 읽을 문자열로 낸다."""
        if not self.ok:
            return f"<파싱 실패: {self.error}>\n원본: {self.source!r}"
        assert self.tree is not None
        return self.tree.pretty()


def parse(latex: str) -> ParseResult:
    """LaTeX 수식 문자열을 구문 트리로 파싱한다.

    예외를 던지지 않는다 (요구 4). 파싱 불가능한 입력은
    ``ParseResult(ok=False, ..., source=latex)`` 로 돌려준다.

    Args:
        latex: ``$``/``$$`` delimiter 가 제거된 LaTeX 수식 본문.

    Returns:
        :class:`ParseResult`. 성공 시 ``ok=True`` 와 루트 :class:`Group`.
    """
    try:
        tokens = tokenize(latex)
        tree = _Parser(tokens).parse_root()
    except LatexParseError as exc:
        return ParseResult(ok=False, source=latex, tree=None, error=str(exc))
    return ParseResult(ok=True, source=latex, tree=tree, error=None)
