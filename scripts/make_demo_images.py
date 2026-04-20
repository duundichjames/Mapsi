"""``samples/demo/images/`` 의 데모용 다이어그램 (pipeline / truth-source-separation) 생성기.

두 PNG 는 ``samples/demo/demo.md`` 가 figure 로 참조하는 단발성 일러스트인데,
초기 생성 시 한글을 지원하지 않는 폰트가 잡혀 글자가 ``□`` (tofu) 로 깨져 있었다.
이 스크립트는 한글 TrueType 폰트를 직접 찾아 주입해 두 그림을 재생성한다.

사용법::

    python scripts/make_demo_images.py

로컬 Pillow + 시스템 한글 폰트 (AppleSDGothicNeo → AppleGothic → NanumGothic
→ NotoSansCJK 우선 순위) 만으로 동작한다. 폰트 후보를 모두 못 찾으면
``RuntimeError`` 로 명확하게 실패시킨다 — 기본 폰트로 떨어뜨려 다시 tofu 가
박히는 것을 방지하기 위함.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


_ROOT = Path(__file__).resolve().parents[1]
_OUT_DIR = _ROOT / "samples" / "demo" / "images"


# 한글을 포함하는 시스템 폰트 후보 (우선순위 순). 첫 번째로 존재하는 것을 사용.
_FONT_CANDIDATES: tuple[str, ...] = (
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/Library/Fonts/AppleGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)


# 디자인 팔레트 — 기존 broken 이미지의 톤(옅은 파랑) 을 유지
BG = (255, 255, 255)
BLUE_STROKE = (76, 142, 204)
BLUE_FILL = (224, 239, 253)
BLUE_TITLE = (38, 95, 175)
TEXT = (50, 55, 70)
SUB = (140, 150, 165)
ARROW = (90, 125, 170)


def _resolve_font_path() -> str:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return path
    raise RuntimeError(
        "한글을 지원하는 시스템 폰트를 찾지 못했습니다. "
        "다음 중 하나를 설치하거나 _FONT_CANDIDATES 에 경로를 추가하세요: "
        + ", ".join(_FONT_CANDIDATES)
    )


_FONT_PATH = _resolve_font_path()


def _font(size: int) -> ImageFont.FreeTypeFont:
    """한글 지원 폰트를 ``size`` 에 맞게 로드.

    ``.ttc`` 는 첫 번째 face (index 0) 만 사용한다. AppleSDGothicNeo 의 경우
    index 0 이 Regular 이고, 볼드는 별도 face 라 index 를 바꿔야 하지만 face
    구성은 OS 버전에 따라 달라서 사이즈만 키우는 방식이 더 견고하다.
    """
    return ImageFont.truetype(_FONT_PATH, size=size)


def _text_size(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont
) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def _draw_arrow(
    draw: ImageDraw.ImageDraw,
    x0: int,
    y: int,
    x1: int,
    *,
    color: tuple[int, int, int] = ARROW,
    width: int = 3,
    head: int = 10,
) -> None:
    """``(x0, y) → (x1, y)`` 수평 화살표. 머리는 단색 삼각형."""
    shaft_x1 = x1 - head
    draw.line([(x0, y), (shaft_x1, y)], fill=color, width=width)
    draw.polygon(
        [(x1, y), (shaft_x1, y - head // 2 - 1), (shaft_x1, y + head // 2 + 1)],
        fill=color,
    )


def _draw_box(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    radius: int = 14,
    fill: tuple[int, int, int] = BLUE_FILL,
    outline: tuple[int, int, int] = BLUE_STROKE,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def make_pipeline() -> Path:
    """5 단계 파이프라인 다이어그램 생성. 제목 + 5개 박스 + 화살표."""
    W, H = 1400, 360
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    title_f = _font(40)
    sub_f = _font(20)
    name_f = _font(26)
    path_f = _font(18)

    draw.text((60, 34), "Mapsi Pipeline", font=title_f, fill=BLUE_TITLE)
    draw.text(
        (60, 92),
        "Markdown → HWPX  |  5 단계 파이프라인",
        font=sub_f,
        fill=SUB,
    )

    stages = [
        ("Parse", "mapsi/parser.py"),
        ("Map", "spec/styles.yaml"),
        ("Build", "mapsi/builder/"),
        ("Pack", "mapsi/packager.py"),
        ("Inspect", "mapsi/inspect.py"),
    ]

    margin = 60
    gap = 30
    box_h = 130
    total_w = W - 2 * margin
    box_w = (total_w - gap * (len(stages) - 1)) // len(stages)
    box_y = 175

    for i, (name, path) in enumerate(stages):
        x0 = margin + i * (box_w + gap)
        x1 = x0 + box_w
        y0 = box_y
        y1 = box_y + box_h
        _draw_box(draw, (x0, y0, x1, y1))

        name_w, name_h = _text_size(draw, name, name_f)
        draw.text(
            (x0 + (box_w - name_w) // 2, y0 + 28),
            name,
            font=name_f,
            fill=BLUE_TITLE,
        )

        path_w, _ = _text_size(draw, path, path_f)
        draw.text(
            (x0 + (box_w - path_w) // 2, y0 + 78),
            path,
            font=path_f,
            fill=TEXT,
        )

        if i < len(stages) - 1:
            _draw_arrow(
                draw,
                x1 + 4,
                (y0 + y1) // 2,
                x1 + gap - 4,
            )

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = _OUT_DIR / "pipeline.png"
    img.save(out, format="PNG", optimize=True)
    return out


def make_truth_source() -> Path:
    """정책(styles.yaml) ↔ 사실(header.xml) 분리를 보여주는 다이어그램."""
    W, H = 1400, 560
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    title_f = _font(32)
    sub_f = _font(18)
    hdr_f = _font(20)
    code_f = _font(17)
    small_f = _font(14)

    draw.text((50, 28), "Truth-Source Separation", font=title_f, fill=BLUE_TITLE)
    draw.text(
        (50, 72),
        "Policy (role → 스타일 이름)  vs.  Fact (스타일 이름 → ID)  — 이름(NAME) 으로 조인",
        font=sub_f,
        fill=SUB,
    )

    # 좌측 2개 박스 (policy / fact)
    left_x = 50
    left_w = 460

    box1 = (left_x, 130, left_x + left_w, 290)
    _draw_box(draw, box1)
    draw.text(
        (left_x + 18, box1[1] + 14),
        "spec/styles.yaml   (policy)",
        font=hdr_f,
        fill=BLUE_TITLE,
    )
    for i, line in enumerate(
        [
            "heading:  1   →   개요 1",
            "paragraph    →   본문",
            "blockquote   →   인용",
            "code_block   →   코드",
        ]
    ):
        draw.text(
            (left_x + 24, box1[1] + 54 + i * 24),
            line,
            font=code_f,
            fill=TEXT,
        )

    box2 = (left_x, 320, left_x + left_w, 500)
    _draw_box(draw, box2)
    draw.text(
        (left_x + 18, box2[1] + 14),
        "templates/Contents/header.xml   (fact)",
        font=hdr_f,
        fill=BLUE_TITLE,
    )
    for i, line in enumerate(
        [
            "<hh:style name='개요 1'  paraPrIDRef='20'",
            "          charPrIDRef='12' />",
            "<hh:style name='본문'    paraPrIDRef='18'",
            "          charPrIDRef='7'  />",
        ]
    ):
        draw.text(
            (left_x + 24, box2[1] + 54 + i * 26),
            line,
            font=code_f,
            fill=TEXT,
        )

    # 중앙 Builder 박스
    mid_x = left_x + left_w + 70
    mid_w = 320
    mid_top = 220
    mid_bot = 420
    mid_box = (mid_x, mid_top, mid_x + mid_w, mid_bot)
    _draw_box(draw, mid_box)
    draw.text(
        (mid_x + 18, mid_top + 14),
        "Builder",
        font=hdr_f,
        fill=BLUE_TITLE,
    )
    builder_lines: list[tuple[str, ImageFont.FreeTypeFont]] = [
        ("for each Block:", code_f),
        ("    role → 이름", code_f),
        ("            (styles.yaml)", small_f),
        ("    이름 → IDs", code_f),
        ("            (header.xml)", small_f),
        ("    emit <hp:p …>", code_f),
    ]
    for i, (line, fnt) in enumerate(builder_lines):
        draw.text(
            (mid_x + 24, mid_top + 54 + i * 22),
            line,
            font=fnt,
            fill=TEXT,
        )

    # 우측 출력 박스
    right_x = mid_x + mid_w + 70
    right_w = W - right_x - 50
    right_box = (right_x, 130, right_x + right_w, 500)
    _draw_box(draw, right_box)
    draw.text(
        (right_x + 18, right_box[1] + 14),
        "Contents/section0.xml   (output)",
        font=hdr_f,
        fill=BLUE_TITLE,
    )
    for i, line in enumerate(
        [
            "<hp:p paraPrIDRef='20'",
            "      styleIDRef='4'>",
            "  <hp:run charPrIDRef='12'>",
            "    <hp:t>3.2. 섹션 제목</hp:t>",
            "  </hp:run>",
            "</hp:p>",
        ]
    ):
        draw.text(
            (right_x + 28, right_box[1] + 60 + i * 28),
            line,
            font=code_f,
            fill=TEXT,
        )

    # 화살표: policy → Builder, fact → Builder, Builder → output
    _draw_arrow(draw, box1[2] + 4, (box1[1] + box1[3]) // 2, mid_x - 4)
    _draw_arrow(draw, box2[2] + 4, (box2[1] + box2[3]) // 2, mid_x - 4)
    _draw_arrow(
        draw,
        mid_box[2] + 4,
        (mid_box[1] + mid_box[3]) // 2,
        right_box[0] - 4,
    )

    out = _OUT_DIR / "truth-source-separation.png"
    img.save(out, format="PNG", optimize=True)
    return out


def main() -> None:
    p1 = make_pipeline()
    p2 = make_truth_source()
    print(f"written: {p1}  ({p1.stat().st_size:,} bytes)  font={_FONT_PATH}")
    print(f"written: {p2}  ({p2.stat().st_size:,} bytes)  font={_FONT_PATH}")


if __name__ == "__main__":
    main()
