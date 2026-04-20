"""``docs/hwpx_assembly.png`` 생성기 — PPT 슬라이드용 HWPX 조립 과정 다이어그램.

한 장에 다음 세 부분을 나란히 배치한다:

1. **입력 파일들** — 사용자 입력, 정책(styles.yaml), 정적 템플릿, 부트스트랩 자산.
2. **변환 파이프라인** — ``converter.md_to_hwpx()`` 의 5 단계.
3. **HWPX ZIP 내부 구조** — 최종 산출물인 ``.hwpx`` 안의 파일 트리.

실행::

    python scripts/make_hwpx_assembly_diagram.py

16:9 (1920 × 1080) PPT 표준 해상도로 저장된다. 한글 렌더링은
AppleSDGothicNeo / AppleGothic / NanumGothic / NotoSansCJK 중 가장 먼저
존재하는 폰트를 사용하며, 모두 없으면 RuntimeError 로 실패한다 (기본 폰트
폴백으로 tofu(□) 가 박히는 사고를 막기 위함).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


_ROOT = Path(__file__).resolve().parents[1]
_OUT = _ROOT / "docs" / "hwpx_assembly.png"


_FONT_CANDIDATES: tuple[str, ...] = (
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/Library/Fonts/AppleGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)


# ───── 팔레트 ──────────────────────────────────────────────────
BG = (255, 255, 255)
TITLE = (30, 64, 120)
SUB = (110, 125, 150)
TEXT = (50, 55, 70)
CODE = (70, 80, 100)
SEP = (220, 225, 235)

# 입력 카드 색상 (역할별로 구분)
USER_FILL, USER_STROKE = (255, 243, 224), (218, 135, 50)
POLICY_FILL, POLICY_STROKE = (252, 228, 236), (200, 70, 120)
TMPL_FILL, TMPL_STROKE = (225, 245, 220), (70, 150, 85)

# 중앙 파이프라인
PIPE_FILL, PIPE_STROKE = (230, 240, 255), (70, 130, 200)
STAGE_FILL, STAGE_STROKE = (210, 230, 255), (55, 115, 195)

# 출력 박스
OUT_FILL, OUT_STROKE = (236, 231, 252), (110, 82, 186)
DYNAMIC = (200, 80, 50)  # ★ (동적 산출물) 강조색

ARROW = (95, 125, 170)


def _resolve_font_path() -> str:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return path
    raise RuntimeError(
        "한글을 지원하는 시스템 폰트를 찾지 못했습니다: "
        + ", ".join(_FONT_CANDIDATES)
    )


_FONT_PATH = _resolve_font_path()


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_FONT_PATH, size=size)


def _box(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    fill: tuple[int, int, int],
    stroke: tuple[int, int, int],
    *,
    radius: int = 18,
    width: int = 3,
) -> None:
    draw.rounded_rectangle(rect, radius=radius, fill=fill, outline=stroke, width=width)


def _arrow(
    draw: ImageDraw.ImageDraw,
    x0: int,
    y: int,
    x1: int,
    *,
    color: tuple[int, int, int] = ARROW,
    width: int = 5,
    head: int = 18,
) -> None:
    shaft_x = x1 - head
    draw.line([(x0, y), (shaft_x, y)], fill=color, width=width)
    draw.polygon(
        [
            (x1, y),
            (shaft_x, y - head // 2 - 2),
            (shaft_x, y + head // 2 + 2),
        ],
        fill=color,
    )


def main() -> None:
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    title_f = _font(52)
    subtitle_f = _font(24)
    column_f = _font(30)
    card_hdr_f = _font(24)
    item_f = _font(22)
    tree_f = _font(19)
    stage_num_f = _font(28)
    stage_name_f = _font(26)
    stage_desc_f = _font(18)
    note_f = _font(17)

    # ───── 상단 타이틀 ─────
    draw.text((60, 40), "HWPX 파일은 이렇게 조립됩니다", font=title_f, fill=TITLE)
    draw.text(
        (60, 108),
        "필요한 입력  →  converter.md_to_hwpx()  →  .hwpx ZIP 패키지",
        font=subtitle_f,
        fill=SUB,
    )
    draw.line([(60, 172), (W - 60, 172)], fill=SEP, width=2)

    # ───── 컬럼 헤더 ─────
    col_y = 198
    draw.text((60, col_y), "①  필요한 입력 파일", font=column_f, fill=TITLE)
    draw.text((770, col_y), "②  변환", font=column_f, fill=TITLE)
    draw.text((1230, col_y), "③  HWPX ZIP 내부 구조", font=column_f, fill=TITLE)

    # ══════════════ LEFT — 입력 카드 4개 ══════════════
    lx, lw = 60, 620

    # Card 1: User input
    c1 = (lx, 258, lx + lw, 400)
    _box(draw, c1, USER_FILL, USER_STROKE)
    draw.text(
        (c1[0] + 22, c1[1] + 16),
        "사용자 입력 (Markdown + 이미지)",
        font=card_hdr_f,
        fill=USER_STROKE,
    )
    for i, line in enumerate(
        [
            "• input.md",
            "• images/*.png, *.jpg   (선택)",
        ]
    ):
        draw.text((c1[0] + 30, c1[1] + 60 + i * 30), line, font=item_f, fill=TEXT)

    # Card 2: Policy
    c2 = (lx, 420, lx + lw, 524)
    _box(draw, c2, POLICY_FILL, POLICY_STROKE)
    draw.text(
        (c2[0] + 22, c2[1] + 16),
        "정책 · Policy",
        font=card_hdr_f,
        fill=POLICY_STROKE,
    )
    draw.text(
        (c2[0] + 30, c2[1] + 56),
        "• spec/styles.yaml    (role → 한/글 스타일 이름)",
        font=item_f,
        fill=TEXT,
    )

    # Card 3: Templates (static truth sources)
    c3 = (lx, 544, lx + lw, 792)
    _box(draw, c3, TMPL_FILL, TMPL_STROKE)
    draw.text(
        (c3[0] + 22, c3[1] + 16),
        "정적 템플릿 · Templates (진실원)",
        font=card_hdr_f,
        fill=TMPL_STROKE,
    )
    for i, line in enumerate(
        [
            "templates/",
            "├─ mimetype",
            "├─ version.xml",
            "├─ META-INF/",
            "│    ├─ container.xml",
            "│    ├─ container.rdf",
            "│    └─ manifest.xml",
            "└─ Contents/",
            "      └─ header.xml     ← 스타일 진실원",
        ]
    ):
        draw.text(
            (c3[0] + 30, c3[1] + 58 + i * 22),
            line,
            font=tree_f,
            fill=CODE,
        )

    # Card 4: Bootstrap assets
    c4 = (lx, 812, lx + lw, 1000)
    _box(draw, c4, TMPL_FILL, TMPL_STROKE)
    draw.text(
        (c4[0] + 22, c4[1] + 16),
        "부트스트랩 · Bootstrap (동적 자산 출처)",
        font=card_hdr_f,
        fill=TMPL_STROKE,
    )
    for i, line in enumerate(
        [
            "samples/base/unpacked/",
            "├─ settings.xml",
            "└─ Contents/",
            "      └─ content.hpf    ← manifest 갱신 대상",
        ]
    ):
        draw.text(
            (c4[0] + 30, c4[1] + 58 + i * 26),
            line,
            font=tree_f,
            fill=CODE,
        )

    # ══════════════ CENTER — 파이프라인 ══════════════
    px, pw = 720, 460
    pt, pb = 258, 1000
    _box(draw, (px, pt, px + pw, pb), PIPE_FILL, PIPE_STROKE, radius=22)
    draw.text(
        (px + 22, pt + 18),
        "converter.md_to_hwpx()",
        font=card_hdr_f,
        fill=PIPE_STROKE,
    )
    draw.text(
        (px + 22, pt + 54),
        "5 단계 파이프라인",
        font=item_f,
        fill=SUB,
    )

    stages = [
        ("①", "부트스트랩", "templates/ + samples/base/  →  work_dir/"),
        ("②", "파싱", "parser.py  ·  markdown-it-py → Block 리스트"),
        ("③", "AST 워크", "ast_walker.py  ·  캡션/참고문헌/각주 규칙"),
        ("④", "빌드", "builder/  ·  section0 · BinData · manifest"),
        ("⑤", "패키징", "packager.py  ·  ZIP (mimetype 무압축 첫 엔트리)"),
    ]
    sx, sw = px + 22, pw - 44
    sy0, sh, gap = pt + 100, 115, 15
    for i, (num, name, desc) in enumerate(stages):
        y0 = sy0 + i * (sh + gap)
        y1 = y0 + sh
        _box(draw, (sx, y0, sx + sw, y1), STAGE_FILL, STAGE_STROKE, radius=14, width=2)
        draw.text((sx + 20, y0 + 18), num, font=stage_num_f, fill=STAGE_STROKE)
        draw.text((sx + 62, y0 + 20), name, font=stage_name_f, fill=STAGE_STROKE)
        draw.text((sx + 20, y0 + 64), desc, font=stage_desc_f, fill=CODE)

    # ══════════════ RIGHT — output tree ══════════════
    ox, ow = 1220, 640
    ot, ob = 258, 1000
    _box(draw, (ox, ot, ox + ow, ob), OUT_FILL, OUT_STROKE, radius=22)
    draw.text(
        (ox + 22, ot + 18),
        "output.hwpx   (ZIP 컨테이너)",
        font=card_hdr_f,
        fill=OUT_STROKE,
    )

    tree_out = [
        ("output.hwpx", ""),
        ("├─ mimetype", "★ 첫 엔트리, 무압축 (ZIP 규약)"),
        ("├─ version.xml", "정적 복사"),
        ("├─ META-INF/", ""),
        ("│    ├─ container.xml", "정적 복사"),
        ("│    ├─ container.rdf", "정적 복사"),
        ("│    └─ manifest.xml", "정적 복사"),
        ("├─ Contents/", ""),
        ("│    ├─ header.xml", "templates/ 에서 그대로 복사"),
        ("│    ├─ section0.xml", "★ 빌더가 새로 생성"),
        ("│    └─ content.hpf", "★ 이미지 등록 시 갱신"),
        ("├─ BinData/", "  (이미지가 있을 때만)"),
        ("│    ├─ image1.png", "★ 원본 복사"),
        ("│    └─ image2.jpg", "★ 원본 복사"),
        ("└─ settings.xml", "정적 복사"),
    ]
    ty = ot + 64
    for line, note in tree_out:
        draw.text((ox + 24, ty), line, font=tree_f, fill=CODE)
        if note:
            color = DYNAMIC if note.startswith("★") else SUB
            draw.text((ox + 290, ty + 2), note, font=note_f, fill=color)
        ty += 40

    # 범례
    legend_y = ob - 48
    draw.text(
        (ox + 24, legend_y),
        "★  =  변환 파이프라인이 새로 만들어 넣거나 갱신한 산출물",
        font=note_f,
        fill=DYNAMIC,
    )

    # ══════════════ 화살표 ══════════════
    _arrow(draw, lx + lw + 14, 628, px - 10)
    _arrow(draw, px + pw + 14, 628, ox - 10)

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(_OUT, format="PNG", optimize=True)
    print(f"written: {_OUT}  ({_OUT.stat().st_size:,} bytes)  font={_FONT_PATH}")


if __name__ == "__main__":
    main()
