"""``mapsi.math.latex_parser`` 단위 테스트.

이번 단계의 목표는 토크나이저 + 파서 골격이 간단한 입력에서 올바른 트리를
세우는지, 그리고 파싱 불가 입력에서 예외 대신 원본을 보존한 실패 결과를
돌려주는지 확인하는 것이다. HNC 변환은 아직 다루지 않는다.
"""

from __future__ import annotations

from mapsi.math import latex_parser as lp


# ---------------------------------------------------------------------------
# 토크나이저
# ---------------------------------------------------------------------------


class TestTokenize:
    def test_command_groups_scripts(self) -> None:
        kinds = [t.kind for t in lp.tokenize("\\frac{a}{b}")]
        assert kinds == [
            lp.TokenKind.COMMAND,
            lp.TokenKind.LBRACE,
            lp.TokenKind.CHAR,
            lp.TokenKind.RBRACE,
            lp.TokenKind.LBRACE,
            lp.TokenKind.CHAR,
            lp.TokenKind.RBRACE,
        ]
        assert lp.tokenize("\\frac")[0].value == "frac"

    def test_script_and_rowsep_and_align(self) -> None:
        toks = lp.tokenize("a^2 & b \\\\ c")
        kinds = [t.kind for t in toks]
        assert lp.TokenKind.SUP in kinds
        assert lp.TokenKind.ALIGN in kinds
        assert lp.TokenKind.ROWSEP in kinds

    def test_whitespace_is_dropped(self) -> None:
        assert [t.value for t in lp.tokenize("a   b")] == ["a", "b"]


# ---------------------------------------------------------------------------
# 파서 — 간단한 트리
# ---------------------------------------------------------------------------


class TestParseSimple:
    def test_superscript_atom(self) -> None:
        # x^2 → Group[ Script(base=Text 'x', sup=Text '2') ]
        res = lp.parse("x^2")
        assert res.ok
        assert res.tree is not None
        assert len(res.tree.children) == 1
        node = res.tree.children[0]
        assert isinstance(node, lp.Script)
        assert isinstance(node.base, lp.Text) and node.base.value == "x"
        assert isinstance(node.sup, lp.Text) and node.sup.value == "2"
        assert node.sub is None

    def test_frac_two_args(self) -> None:
        # \frac{a}{b} → Command('frac', [Group[Text a], Group[Text b]])
        res = lp.parse("\\frac{a}{b}")
        assert res.ok
        node = res.tree.children[0]
        assert isinstance(node, lp.Command)
        assert node.name == "frac"
        assert len(node.args) == 2
        for arg, expected in zip(node.args, ("a", "b")):
            assert isinstance(arg, lp.Group)
            assert len(arg.children) == 1
            assert isinstance(arg.children[0], lp.Text)
            assert arg.children[0].value == expected

    def test_sum_with_sub_and_sup(self) -> None:
        # \sum_{i=1}^{n} → Script(base=Command 'sum', sub=Group{i=1}, sup=Group{n})
        res = lp.parse("\\sum_{i=1}^{n}")
        assert res.ok
        node = res.tree.children[0]
        assert isinstance(node, lp.Script)
        assert isinstance(node.base, lp.Command)
        assert node.base.name == "sum"
        assert node.base.args == []  # \sum 은 arity 0
        assert isinstance(node.sub, lp.Group)
        assert [c.value for c in node.sub.children] == ["i", "=", "1"]
        assert isinstance(node.sup, lp.Group)
        assert [c.value for c in node.sup.children] == ["n"]

    def test_command_single_char_argument(self) -> None:
        # \sqrt x → Command('sqrt', [Text 'x'])  (그룹 없이 단일 원자 인자)
        res = lp.parse("\\sqrt x")
        assert res.ok
        node = res.tree.children[0]
        assert isinstance(node, lp.Command)
        assert node.name == "sqrt"
        assert len(node.args) == 1
        assert isinstance(node.args[0], lp.Text)
        assert node.args[0].value == "x"

    def test_pretty_runs_without_error(self) -> None:
        out = lp.parse("\\frac{a}{b}").pretty()
        assert "Command \\frac" in out
        assert "Text 'a'" in out


# ---------------------------------------------------------------------------
# 파서 — 실패 보존 (요구 4)
# ---------------------------------------------------------------------------


class TestParseFailure:
    def test_unbalanced_brace_preserves_source(self) -> None:
        res = lp.parse("{a")
        assert res.ok is False
        assert res.tree is None
        assert res.source == "{a"
        assert res.error  # 메시지 존재

    def test_stray_closing_brace(self) -> None:
        res = lp.parse("a}")
        assert res.ok is False
        assert res.source == "a}"

    def test_failure_does_not_raise(self) -> None:
        # 어떤 깨진 입력에서도 예외가 호출자로 새지 않아야 한다.
        for bad in ["{", "}", "\\", "x^", "\\frac{a}"]:
            res = lp.parse(bad)
            assert res.ok is False
            assert res.source == bad

    def test_pretty_on_failure_shows_source(self) -> None:
        out = lp.parse("{a").pretty()
        assert "파싱 실패" in out
        assert "{a" in out


# ---------------------------------------------------------------------------
# 환경 처리 (방향 A)
# ---------------------------------------------------------------------------


def _cell_text(cell: lp.Group) -> str:
    """셀(Group) 안 Text 원자들을 이어붙여 비교용 문자열로 만든다."""
    assert isinstance(cell, lp.Group)
    return "".join(c.value for c in cell.children if isinstance(c, lp.Text))


class TestEnvironment:
    def test_bmatrix_2x2(self) -> None:
        res = lp.parse(r"\begin{bmatrix}a & b \\ c & d\end{bmatrix}")
        assert res.ok
        env = res.tree.children[0]
        assert isinstance(env, lp.Environment)
        assert env.name == "bmatrix"
        assert env.col_spec is None
        assert len(env.rows) == 2
        assert all(len(row) == 2 for row in env.rows)
        grid = [[_cell_text(c) for c in row] for row in env.rows]
        assert grid == [["a", "b"], ["c", "d"]]

    def test_cases_splits_rows(self) -> None:
        res = lp.parse(r"\begin{cases} x & x>0 \\ -x & x<0 \end{cases}")
        assert res.ok
        env = res.tree.children[0]
        assert isinstance(env, lp.Environment)
        assert env.name == "cases"
        assert len(env.rows) == 2
        # 각 행은 2 칸 (조건식 & 범위)
        assert [len(r) for r in env.rows] == [2, 2]
        assert _cell_text(env.rows[0][0]) == "x"
        assert _cell_text(env.rows[1][0]) == "-x"

    def test_array_col_spec_separated(self) -> None:
        res = lp.parse(r"\begin{array}{ccc} 1 & 2 & 3 \\ 4 & 5 & 6 \end{array}")
        assert res.ok
        env = res.tree.children[0]
        assert isinstance(env, lp.Environment)
        assert env.name == "array"
        assert env.col_spec == "ccc"  # 열 지정자가 셀과 섞이지 않고 분리됨
        assert len(env.rows) == 2
        assert [len(r) for r in env.rows] == [3, 3]
        assert [_cell_text(c) for c in env.rows[0]] == ["1", "2", "3"]

    def test_array_col_spec_with_pipe(self) -> None:
        res = lp.parse(r"\begin{array}{c|c} a & b \end{array}")
        assert res.ok
        env = res.tree.children[0]
        assert env.col_spec == "c|c"

    def test_star_variant_stripped(self) -> None:
        res = lp.parse(r"\begin{align*} a &= b \end{align*}")
        assert res.ok
        env = res.tree.children[0]
        assert isinstance(env, lp.Environment)
        assert env.name == "align"  # 별표 제거

    def test_nested_environment(self) -> None:
        res = lp.parse(
            r"\begin{bmatrix} \begin{pmatrix} a \end{pmatrix} & b \\ c & d \end{bmatrix}"
        )
        assert res.ok
        outer = res.tree.children[0]
        assert isinstance(outer, lp.Environment)
        assert outer.name == "bmatrix"
        inner_cell = outer.rows[0][0]
        inner_env = inner_cell.children[0]
        assert isinstance(inner_env, lp.Environment)
        assert inner_env.name == "pmatrix"
        assert _cell_text(inner_env.rows[0][0]) == "a"

    def test_cell_subtree_is_parsed(self) -> None:
        # 셀 내용이 평탄 문자열이 아니라 다시 파싱된 트리여야 한다.
        res = lp.parse(r"\begin{matrix} \frac{a}{b} & x^2 \end{matrix}")
        assert res.ok
        env = res.tree.children[0]
        cell0, cell1 = env.rows[0]
        assert isinstance(cell0.children[0], lp.Command)
        assert cell0.children[0].name == "frac"
        assert isinstance(cell1.children[0], lp.Script)

    def test_pretty_shows_env_structure(self) -> None:
        out = lp.parse(r"\begin{bmatrix}a & b\end{bmatrix}").pretty()
        assert "Environment 'bmatrix'" in out
        assert "row[0]:" in out
        assert "cell[1]:" in out


class TestEnvironmentFallback:
    def test_unsupported_env_falls_back(self) -> None:
        # 목록에 없는 환경 → ok=False, 원본 보존 (평탄 트리 금지) (요구 4)
        src = r"\begin{tikzpicture} \draw (0,0); \end{tikzpicture}"
        res = lp.parse(src)
        assert res.ok is False
        assert res.tree is None
        assert res.source == src

    def test_missing_end_falls_back(self) -> None:
        src = r"\begin{bmatrix} a & b"
        res = lp.parse(src)
        assert res.ok is False
        assert res.source == src

    def test_mismatched_end_falls_back(self) -> None:
        src = r"\begin{bmatrix} a \end{pmatrix}"
        res = lp.parse(src)
        assert res.ok is False
        assert res.source == src

    def test_stray_end_falls_back(self) -> None:
        src = r"a \end{bmatrix}"
        res = lp.parse(src)
        assert res.ok is False
        assert res.source == src
