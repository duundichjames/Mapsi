"""마크다운 파싱.

markdown-it-py 의 토큰 스트림을 Mapsi 의 중간 표현인 ``Block`` 평탄 리스트로
재구성한다. 본 모듈은 토큰 → Block 변환에만 집중하며, 표/그림 캡션
승격이나 참고문헌 섹션 감지 등의 문맥 의존 규칙은 ``ast_walker`` 가 담당한다.

지원 토큰 (점진 추가):
    - ``paragraph_open`` / ``paragraph_close`` -- ``role="paragraph"``
      (단, blockquote 내부에서는 ``role="blockquote"`` 로 승격)
    - ``heading_open`` / ``heading_close`` (h1~h6) -- ``role="heading"``,
      ``depth=1..6``
    - ``bullet_list_open`` / ``bullet_list_close`` + ``list_item_open`` /
      ``list_item_close`` -- ``role="bullet_list"``, ``depth=1..N``
    - ``ordered_list_open`` / ``ordered_list_close`` + 동일 -- ``role="ordered_list"``
    - ``blockquote_open`` / ``blockquote_close`` -- 컨테이너로만 동작.
      안의 ``paragraph_open`` 이 ``role="blockquote"`` Block 을 emit
    - ``fence`` / ``code_block`` -- 코드 블록 1 줄 = 1 Block
      (``role="code_block"``). 코드 안의 빈 줄도 1 Block 으로 보존.
    - ``table_open`` / ``table_close`` (+ ``thead`` / ``tbody`` / ``tr`` /
      ``th`` / ``td``) -- ``role="table"`` 단일 Block. 행/열은
      ``meta["rows"]`` 에 ``list[list[str]]`` 로 보관. 캡션은 파서가
      만들지 않으며 ``ast_walker.walk()`` 가 직전 단락을 검사해 승격함.
    - ``paragraph_open`` 의 inline 자식이 ``image`` 토큰 단 1 개일 때 --
      ``role="figure"`` Block. 이미지 정보는 ``text`` (alt) 와
      ``meta["src"]`` 에 보관하고 ``meta["caption"]`` 은 ``None`` 으로
      초기화. 그림 캡션 승격은 ``ast_walker.walk()`` 가 직후 단락을
      검사해 처리. 그림과 글이 섞인 단락은 figure 가 아니라 일반
      paragraph 로 처리되며, 이 경우 이미지 alt 텍스트만 평문으로 남는다
      (인라인 그림은 후속 픽스처에서 별도 처리).
    - ``footnote_ref`` (Pandoc 확장 ``[^id]``) -- 본문 paragraph 의 inline
      마크로 보관. paragraph Block 의 ``meta["footnote_marks"]`` 에
      ``[{"offset": int, "footnote_id": int}]`` 형식으로 추가. ``offset``
      은 ``Block.text`` 안의 문자 오프셋 (각주 마커 자체는 ``text`` 에
      포함되지 않음). ``footnote_id`` 는 markdown-it 의 footnote plugin 이
      등장 순서로 부여한 0-base 정수 (원문 ID 라벨은 무시됨; A 의 명세).
    - ``footnote_block_open`` ... ``footnote_close`` -- 정의 본문을
      ``role="footnote_def"`` Block 으로 변환. 본문 paragraph 와의 매칭
      (정의 본문을 본문 paragraph 의 마크에 흡수) 은 ``ast_walker`` 책임.
    - ``math_inline`` (``$ ... $``) -- 본문 paragraph 의 inline 마크로 보관.
      paragraph Block 의 ``meta["equation_marks"]`` 에
      ``[{"offset": int, "latex": str, "display": False}]`` 형식으로 추가.
      각주와 동일하게 ``offset`` 은 ``Block.text`` 에 마커 자체가
      *포함되지 않은* 평문 안의 위치이며, 빌더가 그 자리에 변환 결과를
      박는다. ``display=False`` 는 인라인 모드 표시.
    - ``math_block`` (``$$ ... $$``) -- 단독 paragraph Block 으로 발급.
      ``role="paragraph"``, ``text=""``, ``meta["equation_marks"]=
      [{"offset": 0, "latex": str, "display": True}]``. 단락 자체의 스타일은
      "본문" 을 그대로 유지하며 (A 명세 §스타일 매핑), 안에 마커 텍스트
      1 개만 들어간다.
    - ``fence`` with ``info="bibtex"`` -- 본문 출력에서 **억제** 된다.
      인라인 BibTeX 블록은 :func:`read_inline_bibtex` 로 별도 추출하며,
      section 빌더에는 전달되지 않는다.
    - ``citation_marks`` (인라인 텍스트 안의 ``[@key]`` / ``@key`` /
      ``-@key``) -- paragraph / blockquote / list_item Block 의
      ``meta["citation_marks"]`` 에 기록. 각 마크는
      ``{"cite_type": str, "raw": str, "offset": int}`` 형식.
      ``cite_type`` 은 ``"bracketed"`` | ``"bare"`` | ``"suppress_author"``.
      ``offset`` 은 인용이 제거된 평문에서의 삽입 위치 (문자 오프셋).
      ``raw`` 는 파서가 추출한 원시 인용 문자열 (``@key`` 또는
      ``@key, locator`` 또는 ``@a; @b``).

지원되지 않는 토큰을 만나면 :class:`NotImplementedError` 를 발생시켜
조용한 데이터 손실을 방지한다 (다음 픽스처에서 명시적으로 추가). 다만
``html_block`` / ``html_inline`` (원시 HTML) 은 예외로 **건너뛴다** — R
Markdown 산출물의 HTML 주석이나 ``<p class="caption">`` 같은 블록이 변환을
중단시키지 않도록 의도적으로 제외하며, 한/글 문서에는 넣지 않는다.

GFM 표 활성화: 기본 CommonMark 파서는 ``table_*`` 토큰을 emit 하지 않는다.
Pandoc 각주 활성화: ``mdit_py_plugins.footnote.footnote_plugin`` 을 use
하여 ``footnote_ref`` / ``footnote_block_open`` 등 토큰을 emit 하도록 한다.
달러 수식 활성화: ``mdit_py_plugins.dollarmath.dollarmath_plugin`` 을 use
하여 ``math_inline`` / ``math_block`` 토큰을 emit 하도록 한다.
:func:`parse_markdown` 은 ``MarkdownIt("commonmark").enable("table")
.use(footnote_plugin).use(dollarmath_plugin)`` 로 세 확장을 모두 활성화한다.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.amsmath import amsmath_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.texmath import texmath_plugin


__all__ = ["Block", "parse_markdown", "read_front_matter", "read_inline_bibtex"]


# ---------------------------------------------------------------------------
# 인용 패턴 정규식
# ---------------------------------------------------------------------------

_CITATION_RE = re.compile(
    r"\[(?P<br>@[^\]]+)\]"              # bracketed: [@key] / [@key, p.5; @b]
    r"|(?P<su>-@[\w:.\-]+\b)"           # suppress-author: -@key (단어 경계로 마침표 제외)
    r"|(?<![-\[])(?P<ba>@[\w:.\-]+\b)"  # bare: @key (앞이 - 또는 [ 가 아님)
)


@dataclass
class Block:
    """파서가 빌더에 전달하는 중간 표현 단위.

    Attributes:
        role: 블록의 의미 역할. ``spec/styles.yaml`` 의 최상위 키와 동일한
            영문 snake_case 키를 사용한다 (예: ``"paragraph"``,
            ``"heading"``, ``"bullet_list"``, ``"ordered_list"``,
            ``"blockquote"``, ``"code_block"``, ``"table"``,
            ``"figure"``, ``"footnote"``, ``"reference"``,
            ``"inline_equation"``, ``"display_equation"``).
        depth: 헤딩 레벨이나 목록 들여쓰기 깊이. 의미 없는 블록은 ``0``.
        text: 평문 본문이 있는 블록의 텍스트 (인라인 토큰 펼친 형태).
            인라인 서식은 ``children`` 에 별도 보관되며, 이 필드는
            서식 정보 없는 평문이다.
        children: 하위 Block 또는 인라인 노드 리스트.
        meta: 부가 정보. 표의 cell 배열, 코드블록의 ``info`` 문자열,
            이미지의 ``src``/``alt``, 각주 라벨 등 역할별 자유 슬롯.
    """

    role: str
    depth: int = 0
    text: str = ""
    children: list["Block"] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


def parse_markdown(md_path: str | Path) -> list[Block]:
    """마크다운 파일을 읽어 평탄 Block 리스트로 파싱한다.

    Args:
        md_path: 입력 ``.md`` 파일 경로.

    Returns:
        문서 순서대로 정렬된 Block 리스트 (평탄 구조).
        ``info="bibtex"`` 펜스 블록은 억제되어 출력에 포함되지 않는다.
    """
    text = Path(md_path).read_text(encoding="utf-8")
    _, body = _split_front_matter(text)
    md = (
        MarkdownIt("commonmark", {"linkify": True})
        .enable("table")
        .enable("strikethrough")
        .enable("linkify")
        .use(footnote_plugin)
        .use(dollarmath_plugin)
        .use(amsmath_plugin)
        # 백슬래시 수식 구문 \(...\) / \[...\] 인식. brackets 전용이라 달러는
        # dollarmath 가 그대로 맡고, texmath 는 core escape 보다 먼저 인라인
        # 규칙을 등록해 \( 가 평문화되기 전에 가로챈다. dollarmath 와 같은
        # math_inline/math_block 토큰을 내므로 _tokens_to_blocks 는 무변경.
        .use(texmath_plugin, delimiters="brackets")
    )
    tokens = md.parse(body)
    return _tokens_to_blocks(tokens)


def read_front_matter(md_path: str | Path) -> dict[str, Any]:
    """마크다운 파일의 YAML front matter 를 파싱해 딕셔너리로 반환한다.

    front matter 가 없거나 빈 경우 빈 딕셔너리 반환.
    YAML 파싱 오류는 ``ValueError`` 로 전파.

    Args:
        md_path: 입력 ``.md`` 파일 경로.

    Returns:
        YAML front matter 딕셔너리. front matter 없음 → ``{}``.
    """
    text = Path(md_path).read_text(encoding="utf-8")
    fm_text, _ = _split_front_matter(text)
    if not fm_text:
        return {}
    try:
        parsed = yaml.safe_load(fm_text)
    except yaml.YAMLError as exc:
        raise ValueError(
            f"front matter YAML 파싱 실패 ({md_path}): {exc}"
        ) from exc
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ValueError(
            f"front matter 는 매핑이어야 함 (type={type(parsed).__name__}): {md_path}"
        )
    return parsed


def read_inline_bibtex(md_path: str | Path) -> list[str]:
    """마크다운 파일의 ``bibtex`` 펜스 블록 내용 목록을 반환한다.

    Args:
        md_path: 입력 ``.md`` 파일 경로.

    Returns:
        각 ``bibtex`` 펜스 블록의 내용 문자열 목록 (등장 순). 없으면 빈 리스트.
    """
    text = Path(md_path).read_text(encoding="utf-8")
    _, body = _split_front_matter(text)
    md = (
        MarkdownIt("commonmark", {"linkify": True})
        .enable("table")
        .use(footnote_plugin)
        .use(dollarmath_plugin)
    )
    tokens = md.parse(body)
    result: list[str] = []
    for tok in tokens:
        if tok.type == "fence" and (tok.info or "").strip().lower() == "bibtex":
            if tok.content:
                result.append(tok.content)
    return result


def _split_front_matter(text: str) -> tuple[str, str]:
    """선행 YAML front matter 를 분리해 ``(fm_text, body)`` 로 반환한다.

    front matter 가 없으면 ``("", text)`` 반환.
    형식: 첫 줄이 정확히 ``---`` 이고, 이후 단독 ``---`` 또는 ``...`` 가
    다시 등장하면 그 사이를 메타로 간주.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            fm = "".join(lines[1:i])
            body = "".join(lines[i + 1 :])
            return fm, body
    return "", text


def _strip_front_matter(text: str) -> str:
    """선행 YAML front matter 가 있으면 제거하여 본문만 반환한다 (하위 호환)."""
    _, body = _split_front_matter(text)
    return body


_LIST_OPEN_TO_ROLE = {
    "bullet_list_open": "bullet_list",
    "ordered_list_open": "ordered_list",
}
_LIST_CLOSE_OF = {
    "bullet_list_open": "bullet_list_close",
    "ordered_list_open": "ordered_list_close",
}
_LIST_OPEN_TYPES = frozenset(_LIST_OPEN_TO_ROLE)
_LIST_CLOSE_TYPES = frozenset(_LIST_CLOSE_OF.values())


# amsmath 토큰 처리: 단일 수식 디스플레이 래퍼만 벗기고, 정렬/행렬 등
# 구조적 환경은 그대로 latex_parser 에 넘긴다. equation 은 HNC 에 대응하는
# 래퍼 구문이 없는 "한 줄 수식 번호 매기기" 용도이므로(별 변형 포함) 내부만
# 남긴다. align/gather/matrix 등은 latex_parser 가 eqalign/matrix 로 처리.
_DISPLAY_WRAPPER_ENVS = {"equation"}

_AMSMATH_RE = re.compile(
    r"\\begin\{(?P<name>[A-Za-z]+\*?)\}(?P<body>.*)\\end\{(?P=name)\}",
    re.DOTALL,
)


def _amsmath_latex(content: str) -> str:
    r"""amsmath 토큰 content 에서 equation_marks 에 담을 LaTeX 를 결정한다.

    ``equation``/``equation*`` 같은 디스플레이 래퍼는 ``\begin``/``\end`` 를
    벗기고 내부 수식만, 그 밖의 구조적 환경은 원문 전체를 돌려준다.
    """
    m = _AMSMATH_RE.search(content)
    if m is not None and m.group("name").rstrip("*") in _DISPLAY_WRAPPER_ENVS:
        return m.group("body").strip()
    return content.strip()


def _tokens_to_blocks(tokens: list[Token]) -> list[Block]:
    """markdown-it 토큰 스트림을 평탄 Block 리스트로 변환한다.

    목록은 중첩 가능하므로 ``list_stack`` 으로 현재 어떤 타입의 목록
    안에 있는지와 깊이를 추적한다 (스택 길이 = 깊이). 평탄 출력 전략 (Q1
    답변 (A) 평탄) 에 따라 각 list_item 은 자기 깊이만 ``Block.depth`` 에
    실어 동일 레벨로 emit 한다.
    """
    blocks: list[Block] = []
    list_stack: list[str] = []  # "bullet_list" or "ordered_list"
    blockquote_depth = 0
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]

        if tok.type == "heading_open":
            depth = int(tok.tag[1:])
            text = _inline_to_text(tokens[i + 1])
            blocks.append(Block(role="heading", depth=depth, text=text))
            i += 3
            continue

        if tok.type == "paragraph_open":
            inline = tokens[i + 1]
            figure = _extract_solo_figure(inline)
            if figure is not None and blockquote_depth == 0 and not list_stack:
                src, alt = figure
                blocks.append(
                    Block(
                        role="figure",
                        text=alt,
                        meta={"src": src, "caption": None},
                    )
                )
            else:
                text, footnote_marks, equation_marks, inline_marks, citation_marks = (
                    _inline_to_text_and_marks(inline)
                )
                if blockquote_depth > 0:
                    bq_meta: dict[str, Any] = {}
                    if footnote_marks:
                        bq_meta["footnote_marks"] = footnote_marks
                    if equation_marks:
                        bq_meta["equation_marks"] = equation_marks
                    if inline_marks:
                        bq_meta["inline_marks"] = inline_marks
                    if citation_marks:
                        bq_meta["citation_marks"] = citation_marks
                    blocks.append(
                        Block(role="blockquote", text=text, meta=bq_meta)
                    )
                elif not list_stack:
                    meta: dict[str, Any] = {}
                    if footnote_marks:
                        meta["footnote_marks"] = footnote_marks
                    if equation_marks:
                        meta["equation_marks"] = equation_marks
                    if inline_marks:
                        meta["inline_marks"] = inline_marks
                    if citation_marks:
                        meta["citation_marks"] = citation_marks
                    blocks.append(
                        Block(role="paragraph", text=text, meta=meta)
                    )
                # list 안의 paragraph 는 list_item_open 시점에 이미 처리됨
            i += 3
            continue

        if tok.type in _LIST_OPEN_TYPES:
            list_stack.append(_LIST_OPEN_TO_ROLE[tok.type])
            i += 1
            continue

        if tok.type in _LIST_CLOSE_TYPES:
            if not list_stack:
                raise ValueError(
                    f"닫는 list 토큰 {tok.type!r} 이 짝 없이 등장 (위치 line={tok.map})"
                )
            list_stack.pop()
            i += 1
            continue

        if tok.type == "list_item_open":
            if not list_stack:
                raise ValueError(
                    f"list_item_open 이 list 컨테이너 밖에서 등장 (위치 line={tok.map})"
                )
            role = list_stack[-1]
            depth = len(list_stack)
            text, foot_marks, eq_marks, inline_marks, cite_marks = _first_inline_in_item(
                tokens, i
            )
            meta: dict[str, Any] = {}
            if foot_marks:
                meta["footnote_marks"] = foot_marks
            if eq_marks:
                meta["equation_marks"] = eq_marks
            if inline_marks:
                meta["inline_marks"] = inline_marks
            if cite_marks:
                meta["citation_marks"] = cite_marks
            blocks.append(
                Block(role=role, depth=depth, text=text, meta=meta)
            )
            i += 1
            continue

        if tok.type == "list_item_close":
            i += 1
            continue

        if tok.type == "blockquote_open":
            blockquote_depth += 1
            i += 1
            continue

        if tok.type == "blockquote_close":
            if blockquote_depth <= 0:
                raise ValueError(
                    f"blockquote_close 가 짝 없이 등장 (위치 line={tok.map})"
                )
            blockquote_depth -= 1
            i += 1
            continue

        if tok.type in ("fence", "code_block"):
            # bibtex 펜스 블록은 본문 출력에서 억제 (read_inline_bibtex 로 별도 추출)
            if tok.type == "fence" and (tok.info or "").strip().lower() == "bibtex":
                i += 1
                continue
            blocks.extend(_emit_code_lines(tok))
            i += 1
            continue

        if tok.type == "table_open":
            table_block, consumed = _consume_table(tokens, i)
            blocks.append(table_block)
            i += consumed
            continue

        if tok.type == "footnote_block_open":
            # footnote_block 자체는 컨테이너만이며 emit 하지 않음.
            # 안의 footnote_open ... footnote_close 묶음을 각각 footnote_def
            # Block 으로 변환.
            i += 1
            continue

        if tok.type == "footnote_block_close":
            i += 1
            continue

        if tok.type == "footnote_open":
            def_block, consumed = _consume_footnote_def(tokens, i)
            blocks.append(def_block)
            i += consumed
            continue

        if tok.type == "math_block":
            latex = (tok.content or "").strip("\n")
            blocks.append(
                Block(
                    role="paragraph",
                    text="",
                    meta={
                        "equation_marks": [
                            {"offset": 0, "latex": latex, "display": True}
                        ]
                    },
                )
            )
            i += 1
            continue

        if tok.type == "amsmath":
            # AMS 수식 환경(\begin{...}...\end{...}) → 디스플레이 수식.
            # math_block($$) 과 동일한 형태의 독립 paragraph Block 으로 발급.
            latex = _amsmath_latex(tok.content or "")
            blocks.append(
                Block(
                    role="paragraph",
                    text="",
                    meta={
                        "equation_marks": [
                            {"offset": 0, "latex": latex, "display": True}
                        ]
                    },
                )
            )
            i += 1
            continue

        if tok.type in ("html_block", "html_inline"):
            # 원시 HTML 은 한/글 문서에 넣지 않고 건너뛴다 (의도된 제외).
            # R Markdown 산출물의 HTML 주석 <!-- ... --> 이나 <p class="caption">
            # 같은 블록이 변환을 중단시키지 않도록 한다. html_inline 은 본래
            # 인라인 처리에서 조용히 무시되지만, 의도를 분명히 하려 함께 둔다.
            i += 1
            continue

        raise NotImplementedError(
            f"마크다운 토큰 {tok.type!r} 은 아직 지원되지 않는다 "
            f"(다음 픽스처에서 추가). 위치 line={tok.map}"
        )

    if list_stack:
        raise ValueError(f"닫히지 않은 list 컨테이너가 남음: {list_stack}")
    if blockquote_depth != 0:
        raise ValueError(f"닫히지 않은 blockquote 가 {blockquote_depth} 개 남음")
    return blocks


def _split_citations(
    text: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    """텍스트에서 인용 패턴을 추출해 ``(segments, cite_marks)`` 로 반환한다.

    인용 패턴은 평문에서 *제거* 되며, 각 인용 위치는 마크로 기록된다.

    반환 구조
    ----------
    ``segments``:
        인용 사이사이의 평문 조각. 항상 ``len(segments) == len(cite_marks) + 1``.
    ``cite_marks``:
        ``{"cite_type": str, "raw": str}`` 리스트. 각 마크의 ``offset`` 은
        호출자가 ``cursor`` 를 더해 채운다 (절대 오프셋 미포함).

    ``cite_type`` 값:
        - ``"bracketed"``: ``[@key]`` / ``[@key, locator]`` / ``[@a; @b]``
        - ``"suppress_author"``: ``-@key``
        - ``"bare"``: ``@key``
    """
    segments: list[str] = []
    marks: list[dict[str, Any]] = []
    cursor_in = 0

    for m in _CITATION_RE.finditer(text):
        segments.append(text[cursor_in : m.start()])
        if m.group("br") is not None:
            marks.append({"cite_type": "bracketed", "raw": m.group("br")})
        elif m.group("su") is not None:
            raw = m.group("su")[1:]  # 선행 - 제거 (suppress = -@key → @key)
            marks.append({"cite_type": "suppress_author", "raw": raw})
        else:
            marks.append({"cite_type": "bare", "raw": m.group("ba")})
        cursor_in = m.end()

    segments.append(text[cursor_in:])
    return segments, marks


def _consume_table(tokens: list[Token], open_idx: int) -> tuple[Block, int]:
    """``table_open`` 부터 ``table_close`` 까지를 1 개의 Block 으로 묶는다.

    GFM 표는 ``table_open`` → (``thead_open`` → ``tr_open`` → ``th_open`` →
    ``inline`` → ``th_close`` ... ``thead_close``) → (``tbody_open`` →
    ``tr_open`` → ``td_open`` → ``inline`` → ``td_close`` ...
    ``tbody_close``) → ``table_close`` 의 순서로 등장한다. 행/열 구조는
    ``th`` 와 ``td`` 를 동일하게 다루어 ``rows: list[list[str]]`` 로 평탄화.

    헤더 행과 본문 행을 구분하지 않는 이유는 ADR 0001 의 결정 (가) — "셀
    스타일은 ``표내용`` 으로 통일, 헤더 시각 차별화는 표 서식의 첫 행
    배경/테두리에 위임" 에 따른다.

    Returns
    -------
    (Block, int)
        ``Block(role="table", meta={"rows": [...], "caption": None})`` 와
        ``table_close`` 다음 인덱스로 진행하기 위해 소비한 토큰 개수.
    """
    rows: list[list[str]] = []
    current_row: list[str] | None = None
    j = open_idx + 1
    n = len(tokens)
    while j < n:
        tok = tokens[j]
        if tok.type == "table_close":
            j += 1
            break
        if tok.type == "tr_open":
            current_row = []
            j += 1
            continue
        if tok.type == "tr_close":
            if current_row is not None:
                rows.append(current_row)
            current_row = None
            j += 1
            continue
        if tok.type in ("th_open", "td_open"):
            inline = tokens[j + 1] if j + 1 < n else None
            text = _inline_to_text(inline) if inline is not None else ""
            if current_row is None:
                raise ValueError(
                    f"셀 토큰 {tok.type!r} 이 tr 컨테이너 밖에서 등장 "
                    f"(위치 line={tok.map})"
                )
            current_row.append(text)
            j += 3  # th/td_open + inline + th/td_close
            continue
        # thead_open/close, tbody_open/close 는 스킵 (구조만 표시)
        if tok.type in ("thead_open", "thead_close", "tbody_open", "tbody_close"):
            j += 1
            continue
        raise NotImplementedError(
            f"표 안에서 예상치 못한 토큰 {tok.type!r} (위치 line={tok.map})"
        )

    block = Block(role="table", meta={"rows": rows, "caption": None})
    return block, j - open_idx


def _emit_code_lines(code_tok: Token) -> list[Block]:
    """``fence`` / ``code_block`` 토큰을 줄 단위 Block 리스트로 펼친다.

    한/글의 "코드" 스타일은 단락 단위로 적용되므로 코드 1 줄을
    1 Block 으로 매핑한다 (Q1 답 (A) 평탄과 일관). markdown-it 의 ``fence``
    토큰은 본문 끝에 항상 ``"\\n"`` 을 붙여 두므로 마지막 1개의 trailing
    개행만 제거하고 split 한다. 빈 줄은 텍스트 빈 Block 으로 보존한다.

    Code fence 의 ``info`` (언어 힌트, 예: ``python``) 는 첫 Block 의
    ``meta["info"]`` 에 기록한다. 후속 픽스처에서 신택스 하이라이트나
    캡션 표기로 활용 여지를 남긴다.
    """
    content = code_tok.content or ""
    if content.endswith("\n"):
        content = content[:-1]
    lines = content.split("\n") if content else [""]
    blocks: list[Block] = [Block(role="code_block", text=line) for line in lines]
    info = (code_tok.info or "").strip()
    if info and blocks:
        blocks[0].meta["info"] = info
    return blocks


def _first_inline_text_in_item(tokens: list[Token], item_open_idx: int) -> str:
    """``list_item_open`` 직후의 첫 inline 텍스트만 반환한다 (마크 정보 버림).

    중첩 list 가 시작되거나 ``list_item_close`` 를 만나면 그 이전까지만
    훑는다 (= 자기 자신의 텍스트만 가져오고 중첩 항목 텍스트는 무시).
    항목이 비어있거나 텍스트 없는 항목이면 빈 문자열 반환.

    인라인 마크 (Phase 10) 까지 함께 보존하고 싶으면
    :func:`_first_inline_in_item` 을 사용한다.
    """
    text, *_ = _first_inline_in_item(tokens, item_open_idx)
    return text


def _first_inline_in_item(
    tokens: list[Token], item_open_idx: int
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """``list_item_open`` 직후의 첫 inline 토큰을 5-tuple 로 분해해 반환한다.

    반환 형식과 의미는 :func:`_inline_to_text_and_marks` 와 동일:
    ``(text, footnote_marks, equation_marks, inline_marks, citation_marks)``.

    중첩 list 가 시작되거나 ``list_item_close`` 를 만나면 그 이전까지만
    훑는다. 항목이 비어 있으면 모두 빈 값 반환.
    """
    j = item_open_idx + 1
    while j < len(tokens):
        t = tokens[j]
        if t.type == "list_item_close" or t.type in _LIST_OPEN_TYPES:
            return "", [], [], [], []
        if t.type == "inline":
            return _inline_to_text_and_marks(t)
        j += 1
    return "", [], [], [], []


def _extract_solo_figure(inline_tok: Token) -> tuple[str, str] | None:
    """inline 토큰이 "그림 단독 단락" 인지 판정하고 (src, alt) 를 반환한다.

    판정 조건 (모두 만족):
      - ``inline_tok.type == "inline"``
      - ``inline_tok.children`` 가 정확히 image 토큰 1 개 (다른 텍스트/포맷
        토큰 동반 시 figure 가 아님)
      - image 토큰의 ``attrs["src"]`` 가 비어있지 않음

    alt 텍스트는 ``image.children`` (markdown-it 가 alt 를 inline 토큰으로
    재파싱) 의 평문 합. attrs 의 ``alt`` 는 흔히 빈 문자열이라 신뢰하지 않음.

    매치 실패 시 ``None`` 반환 → 호출처가 일반 paragraph 처리로 폴백.
    """
    if inline_tok.type != "inline" or not inline_tok.children:
        return None
    if len(inline_tok.children) != 1:
        return None
    child = inline_tok.children[0]
    if child.type != "image":
        return None
    # markdown-it 이 퍼센트 인코딩한 src 를 사람이 읽는 실제 경로로 디코드한다.
    # (한글/공백 경로 복원. % 없는 ASCII·상대 경로에는 무영향, 왕복 안전.)
    # 이렇게 해야 파일 조회·image_map 키·누락 보고가 모두 디코드된 경로로 일관된다.
    src = urllib.parse.unquote((child.attrs.get("src") or "").strip())
    if not src:
        return None
    alt_parts: list[str] = []
    for grandchild in child.children or []:
        if grandchild.type == "text":
            alt_parts.append(grandchild.content)
    alt = "".join(alt_parts)
    return src, alt


def _inline_to_text(inline_tok: Token) -> str:
    """``inline`` 토큰의 자식들에서 평문만 추출한다 (마크 정보 버림).

    굵게/기울임/링크 등의 인라인 서식은 무시하고 텍스트 컨텐츠만 모은다
    (인라인 서식 처리는 후속 픽스처에서 추가). footnote 마크도 무시.

    표 셀이나 list item 의 평문 텍스트가 필요한 곳에서 사용한다 — 이런
    위치에서는 인라인 마크가 필요 없거나 의미가 없다.
    """
    text, *_ = _inline_to_text_and_marks(inline_tok)
    return text


_INLINE_MARK_OPEN: dict[str, str] = {
    "strong_open": "bold",
    "em_open":     "italic",
    "s_open":      "strike",
}
"""``markdown-it`` 인라인 ``*_open`` 토큰 → Mapsi 마크 종류.

대응 ``*_close`` 는 자동으로 동일 prefix 로 매칭한다 (스택 기반).
``link_open`` 은 본 사전에 포함하지 않는다 — 라벨 텍스트만 평문에
흡수하고 시각 마크는 부여하지 않기 때문 (ADR 0004 결정 1).
"""


def _inline_to_text_and_marks(
    inline_tok: Token,
) -> tuple[
    str,
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """``inline`` 토큰을 평문 + 각주/수식/인라인-서식/인용 마크로 분해한다.

    Returns
    -------
    (text, footnote_marks, equation_marks, inline_marks, citation_marks)
        - ``text``: 평문. 각주/수식/인용 마커는 *제외* 되며, 그 외 인라인
          서식 (bold, em, strike, code, link) 은 라벨/내용 평문이 흡수.
        - ``footnote_marks``: ``[{"kind": "footnote_ref", "offset": int,
          "footnote_id": int}]``.
        - ``equation_marks``: ``[{"offset": int, "latex": str, "display": False}]``.
        - ``inline_marks``: ``[{"kind": str, "start": int, "end": int}]``.
        - ``citation_marks``: ``[{"cite_type": str, "raw": str, "offset": int}]``.
          ``cite_type`` 은 ``"bracketed"`` | ``"bare"`` | ``"suppress_author"``.
          인용은 평문에서 제거되며 빌더가 ``offset`` 위치에 포매팅된 텍스트를
          삽입한다.

    Notes
    -----
    citation 을 평문에서 제거하는 이유: walker 가 ``BibFormatter`` 로 resolve 해
    ``mark["formatted"]`` 를 채운 뒤, 빌더가 그 텍스트를 offset 위치에 삽입한다.
    inline_marks 의 start/end 오프셋은 인용 제거 후의 평문 기준으로 계산된다.
    """
    if inline_tok.type != "inline" or inline_tok.children is None:
        return inline_tok.content or "", [], [], [], []
    parts: list[str] = []
    footnote_marks: list[dict[str, Any]] = []
    equation_marks: list[dict[str, Any]] = []
    inline_marks: list[dict[str, Any]] = []
    citation_marks: list[dict[str, Any]] = []
    open_stack: list[tuple[str, int, dict[str, Any] | None]] = []
    cursor = 0
    children = inline_tok.children
    for idx, child in enumerate(children):
        ctype = child.type
        if ctype == "text":
            segs, cite_segs = _split_citations(child.content)
            for idx, seg in enumerate(segs):
                parts.append(seg)
                cursor += len(seg)
                if idx < len(cite_segs):
                    citation_marks.append({**cite_segs[idx], "offset": cursor})
        elif ctype == "softbreak":
            # 문단 내 단일 줄바꿈(소스에서 줄을 나눈 것) → 공백.
            parts.append(" ")
            cursor += 1
        elif ctype == "hardbreak":
            # 명시적 줄바꿈(줄 끝 공백 2개 또는 백슬래시) → 줄바꿈 유지.
            parts.append("\n")
            cursor += 1
        elif ctype == "footnote_ref":
            footnote_id = child.meta.get("id") if child.meta else None
            if footnote_id is None:
                continue
            footnote_marks.append(
                {
                    "kind": "footnote_ref",
                    "offset": cursor,
                    "footnote_id": int(footnote_id),
                }
            )
        elif ctype == "math_inline":
            equation_marks.append(
                {
                    "offset": cursor,
                    "latex": child.content or "",
                    "display": False,
                }
            )
        elif ctype in _INLINE_MARK_OPEN:
            open_stack.append((_INLINE_MARK_OPEN[ctype], cursor, None))
        elif ctype in ("strong_close", "em_close", "s_close"):
            expected = ctype.removesuffix("_close")
            kind = _INLINE_MARK_OPEN.get(f"{expected}_open")
            for idx in range(len(open_stack) - 1, -1, -1):
                if open_stack[idx][0] == kind:
                    _, start, _extra = open_stack.pop(idx)
                    if cursor > start:
                        inline_marks.append(
                            {"kind": kind, "start": start, "end": cursor}
                        )
                    break
        elif ctype == "code_inline":
            nxt = children[idx + 1] if idx + 1 < len(children) else None
            if (
                child.content
                and nxt is not None
                and nxt.type == "text"
                and (nxt.content or "").startswith("{=html}")
            ):
                # Pandoc raw HTML 인라인 (`<!-- 주석 -->`{=html}, <img/>{=html}):
                # code_inline 내용은 평문에 넣지 않고 버린다. 직후 text 에서는
                # {=html} 접두만 제거하고 나머지 평문은 다음 반복에서 정상 처리.
                # code_inline 을 건너뛰므로 cursor(offset) 도 증가하지 않는다.
                nxt.content = (nxt.content or "")[len("{=html}"):]
                continue
            content = child.content or ""
            if content:
                start = cursor
                parts.append(content)
                cursor += len(content)
                inline_marks.append(
                    {"kind": "code", "start": start, "end": cursor}
                )
        elif ctype == "link_open":
            href = child.attrGet("href") or ""
            open_stack.append(("link", cursor, {"url": href}))
        elif ctype == "link_close":
            for idx in range(len(open_stack) - 1, -1, -1):
                if open_stack[idx][0] == "link":
                    _, start, extra = open_stack.pop(idx)
                    url = (extra or {}).get("url", "")
                    if cursor > start and url:
                        inline_marks.append(
                            {
                                "kind": "link",
                                "start": start,
                                "end": cursor,
                                "url": url,
                            }
                        )
                    break
    return (
        "".join(parts),
        footnote_marks,
        equation_marks,
        inline_marks,
        citation_marks,
    )


def _consume_footnote_def(
    tokens: list[Token], open_idx: int
) -> tuple[Block, int]:
    """``footnote_open`` ... ``footnote_close`` 묶음을 1 개의 Block 으로 변환.

    Returns
    -------
    (block, consumed)
        block 은 ``role="footnote_def"`` 이며,
        ``meta["footnote_id"]`` 와 ``text`` (각주 본문 평문) 를 가진다.
        consumed 는 처리한 토큰 수.

    Raises
    ------
    ValueError
        ``footnote_open`` 에 ``id`` 메타가 없거나, ``footnote_close`` 가
        짝 없이 끝나는 경우.

    Notes
    -----
    각주 본문은 단일 paragraph 인 것이 거의 대부분이지만 markdown-it 의
    plugin 은 여러 paragraph 도 허용한다. 본 구현은 *모든* 내부 inline
    토큰의 평문을 ``"\\n"`` 으로 이어 붙여 보존한다 (단락 구분 표지).
    각주 안의 추가 footnote_ref 는 무시 (중첩 각주 미지원).

    토큰 ``footnote_anchor`` 는 본문으로의 백링크용이며 우리 모델에서는
    의미 없으므로 건너뛴다.
    """
    open_tok = tokens[open_idx]
    fid = open_tok.meta.get("id") if open_tok.meta else None
    if fid is None:
        raise ValueError(
            f"footnote_open 에 'id' meta 가 없음 (위치 line={open_tok.map})"
        )

    parts: list[str] = []
    j = open_idx + 1
    n = len(tokens)
    while j < n:
        t = tokens[j]
        if t.type == "footnote_close":
            return (
                Block(
                    role="footnote_def",
                    text="\n".join(parts).strip(),
                    meta={"footnote_id": int(fid)},
                ),
                j - open_idx + 1,
            )
        if t.type == "inline":
            text, *_ = _inline_to_text_and_marks(t)
            if text:
                parts.append(text)
        # paragraph_open / paragraph_close / footnote_anchor 등은 무시.
        j += 1
    raise ValueError(
        f"footnote_open 이 짝 없이 끝남 (위치 line={open_tok.map})"
    )
