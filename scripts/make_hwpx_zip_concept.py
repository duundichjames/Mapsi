"""``docs/hwpx_zip_concept.png`` 생성기 — PPT 슬라이드용 작은 개념도.

"HWPX 는 어떻게 만들어질까요?" 슬라이드에서 쓰는 **한 컷짜리** 그림.

왼쪽에 HWPX 구성 파일들의 디렉토리 트리를 얹고, 가운데에 "ZIP 압축" 화살표,
오른쪽에 ``output.hwpx`` 컨테이너를 둔다. ``Contents/section0.xml`` 한 줄은
노란 pill 과 주석으로 강조되어 **"우리가 직접 만드는 부분"** 임을 즉시 드러낸다.

재생성::

    python scripts/make_hwpx_zip_concept.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


_ROOT = Path(__file__).resolve().parents[1]
_OUT = _ROOT / "docs" / "hwpx_zip_concept.png"


_FONT_CANDIDATES: tuple[str, ...] = (
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/Library/Fonts/AppleGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)


# ───── 팔레트 ─────────────────────────────────────────────
BG = (255, 255, 255)
TITLE = (30, 64, 120)
SUB = (110, 125, 150)
TEXT = (55, 65, 85)

DIR = (60, 115, 185)
FILE = (95, 105, 125)

TREE_BG = (250, 251, 253)
TREE_BORDER = (210, 218, 228)

HI_FILL = (255, 243, 196)
HI_STROKE = (228, 160, 50)
HI_TEXT = (170, 85, 15)

ARROW = (70, 125, 190)

HWPX_FILL = (235, 228, 250)
HWPX_STROKE = (120, 85, 190)
HWPX_TEXT = (85, 55, 155)


def _resolve_font_path() -> str:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return path
    raise RuntimeError(
        "한글 지원 시스템 폰트를 찾지 못했습니다: " + ", ".join(_FONT_CANDIDATES)
    )


_FONT_PATH = _resolve_font_path()


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_FONT_PATH, size=size)


def _folder_icon(draw: ImageDraw.ImageDraw, x: int, y: int, *, size: int = 18) -> None:
    """간단한 폴더 아이콘 (탭 달린 사각형)."""
    tab_w = size * 2 // 5
    tab_h = 4
    body_top = y + tab_h
    draw.rectangle([x, y, x + tab_w, body_top + 2], fill=DIR, outline=DIR)
    draw.rectangle(
        [x, body_top, x + size * 13 // 10, body_top + size - tab_h],
        fill=DIR,
        outline=DIR,
    )


def _file_icon(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    *,
    size: int = 18,
    color: tuple[int, int, int] = FILE,
) -> None:
    """간단한 파일 아이콘 (우상단 접힌 모서리 + 몸통)."""
    fold = size // 3
    poly = [
        (x, y),
        (x + size - fold, y),
        (x + size, y + fold),
        (x + size, y + size),
        (x, y + size),
    ]
    draw.polygon(poly, outline=color, width=2)
    draw.line(
        [(x + size - fold, y), (x + size - fold, y + fold), (x + size, y + fold)],
        fill=color,
        width=1,
    )


def main() -> None:
    W, H = 1400, 720
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    title_f = _font(40)
    sub_f = _font(22)
    tree_f = _font(22)
    label_f = _font(24)
    big_label_f = _font(30)
    note_f = _font(19)
    small_f = _font(17)

    draw.text(
        (60, 40),
        "HWPX 는 어떻게 만들어질까요?",
        font=title_f,
        fill=TITLE,
    )
    draw.text(
        (60, 98),
        "여러 XML · 리소스 파일을 한 디렉토리로 모은 뒤, ZIP 으로 묶으면 .hwpx 가 된다.",
        font=sub_f,
        fill=SUB,
    )

    # ══════════════ 왼쪽 — 디렉토리 트리 ══════════════
    lx, ly, lw, lh = 60, 180, 620, 500
    draw.rounded_rectangle(
        (lx, ly, lx + lw, ly + lh),
        radius=16,
        fill=TREE_BG,
        outline=TREE_BORDER,
        width=2,
    )

    # 트리 루트 라벨
    _folder_icon(draw, lx + 22, ly + 28)
    draw.text(
        (lx + 52, ly + 22),
        "work_dir/   (.hwpx 로 묶이기 직전의 디렉토리)",
        font=label_f,
        fill=TITLE,
    )

    # 트리 항목: (텍스트, 들여쓰기 깊이, 종류, 강조 여부)
    # 종류: "dir" / "file"
    items: list[tuple[str, int, str, bool]] = [
        ("BinData/", 0, "dir", False),
        ("image1.png", 1, "file", False),
        ("Contents/", 0, "dir", False),
        ("content.hpf", 1, "file", False),
        ("header.xml", 1, "file", False),
        ("section0.xml", 1, "file", True),  # ★ 강조
        ("META-INF/", 0, "dir", False),
        ("container.rdf", 1, "file", False),
        ("container.xml", 1, "file", False),
        ("manifest.xml", 1, "file", False),
        ("mimetype", 0, "file", False),
        ("settings.xml", 0, "file", False),
        ("version.xml", 0, "file", False),
    ]

    ty = ly + 72
    line_h = 30
    base_x = lx + 44
    indent_px = 40

    for i, (name, depth, kind, highlight) in enumerate(items):
        x = base_x + depth * indent_px

        # 트리 연결선 (├─ / └─)
        last_at_depth = all(
            nd > depth or nk != kind or False
            for (_, nd, nk, _) in items[i + 1 :]
            if nd <= depth
        )
        # 위 체크는 간단히 재계산: 같은 depth 의 다음 형제가 있는지
        has_sibling_below = any(
            nd == depth for (_, nd, _, _) in items[i + 1 :]
        ) and any(
            nd < depth
            for (_, nd, _, _) in items[i + 1 :]
        ) is False
        # 더 단순하게: 같은 depth 로 이어지는 다음 항목이 있는가?
        same_depth_after = any(
            nd == depth
            for (_, nd, _, _) in items[i + 1 :]
            if nd <= depth
        )
        # 하지만 루트(depth=0) 에선 마지막 두 개 (settings.xml, version.xml) 의
        # 분기 처리를 위해 "같은 depth 0 의 다음 항목이 있는지" 만 보면 된다.
        next_same = False
        for _, nd, _, _ in items[i + 1 :]:
            if nd < depth:
                break
            if nd == depth:
                next_same = True
                break
        branch = "├─" if next_same else "└─"

        # 라인 본체
        line_x = x + 22
        icon_x = line_x + 32

        draw.text((line_x, ty), branch, font=tree_f, fill=FILE)

        if kind == "dir":
            _folder_icon(draw, icon_x, ty + 4)
            text_color = DIR
        else:
            _file_icon(draw, icon_x, ty + 4)
            text_color = FILE

        text_x = icon_x + 28
        text_y = ty

        if highlight:
            text_w = draw.textlength(name, font=tree_f)
            pill = (
                text_x - 10,
                text_y - 5,
                text_x + text_w + 14,
                text_y + line_h - 8,
            )
            draw.rounded_rectangle(
                pill,
                radius=8,
                fill=HI_FILL,
                outline=HI_STROKE,
                width=2,
            )
            draw.text((text_x, text_y), name, font=tree_f, fill=HI_TEXT)
            draw.text(
                (pill[2] + 14, text_y + 2),
                "←  우리가 직접 만드는 부분",
                font=note_f,
                fill=HI_TEXT,
            )
        else:
            draw.text((text_x, text_y), name, font=tree_f, fill=text_color)

        ty += line_h

    # ══════════════ 가운데 — ZIP 압축 화살표 ══════════════
    mx = lx + lw + 40
    mw = 260
    mid_cx = mx + mw // 2
    mid_cy = ly + lh // 2

    draw.text(
        (mid_cx - 60, mid_cy - 90),
        "ZIP 압축",
        font=big_label_f,
        fill=ARROW,
    )

    # 굵은 화살표
    ax0 = mx + 10
    ax1 = mx + mw - 10
    draw.line([(ax0, mid_cy), (ax1 - 26, mid_cy)], fill=ARROW, width=8)
    draw.polygon(
        [(ax1, mid_cy), (ax1 - 30, mid_cy - 18), (ax1 - 30, mid_cy + 18)],
        fill=ARROW,
    )

    draw.text(
        (mid_cx - 90, mid_cy + 28),
        "mimetype 이 맨 앞,",
        font=note_f,
        fill=SUB,
    )
    draw.text(
        (mid_cx - 90, mid_cy + 54),
        "첫 엔트리는 무압축",
        font=note_f,
        fill=SUB,
    )

    # ══════════════ 오른쪽 — output.hwpx ══════════════
    rx = mx + mw + 20
    rw = W - rx - 60
    rh = 320
    ry = ly + (lh - rh) // 2
    draw.rounded_rectangle(
        (rx, ry, rx + rw, ry + rh),
        radius=22,
        fill=HWPX_FILL,
        outline=HWPX_STROKE,
        width=3,
    )

    # 중앙에 .hwpx 파일 아이콘
    icon_size = 72
    icon_x = rx + (rw - icon_size) // 2
    icon_y = ry + 36
    _file_icon(draw, icon_x, icon_y, size=icon_size, color=HWPX_STROKE)
    # ZIP 표식 (아이콘 위에 "ZIP" 작게)
    zip_f = _font(16)
    zw = draw.textlength("ZIP", font=zip_f)
    draw.text(
        (icon_x + (icon_size - zw) // 2, icon_y + icon_size // 2 - 10),
        "ZIP",
        font=zip_f,
        fill=HWPX_STROKE,
    )

    # 파일명
    name_text = "output.hwpx"
    nw = draw.textlength(name_text, font=big_label_f)
    draw.text(
        (rx + (rw - nw) // 2, icon_y + icon_size + 20),
        name_text,
        font=big_label_f,
        fill=HWPX_TEXT,
    )

    cap = "(내부는 ZIP 이라 unzip 가능)"
    cw = draw.textlength(cap, font=small_f)
    draw.text(
        (rx + (rw - cw) // 2, icon_y + icon_size + 62),
        cap,
        font=small_f,
        fill=SUB,
    )

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(_OUT, format="PNG", optimize=True)
    print(f"written: {_OUT}  ({_OUT.stat().st_size:,} bytes)  font={_FONT_PATH}")


if __name__ == "__main__":
    main()
