"""``mapsi/assets/image_not_found.png`` placeholder 이미지 생성기.

converter 가 ``allow_missing_images=True`` 모드에서 Markdown 이 참조한
원본 이미지를 찾지 못했을 때 대신 삽입할 번들 PNG 를 만든다.

사용자가 Markdown 에 ``![alt](src)`` 로 가리키는 파일이 없을 때 HWPX 문서
안의 그림 자리에 "이미지를 불러올 수 없습니다." 메시지가 적힌 미니멀 박스가
대신 렌더링되도록 한다. 디자인은 브라우저에서 이미지 로드 실패 시 보이는
'broken image' 표식을 의도적으로 모사해 사용자에게 익숙한 시그널을 준다.

단발성 스크립트 — 폰트/레이아웃 조정이 필요하면 재실행해서 PNG 를 덮어쓴다.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_ROOT = Path(__file__).resolve().parents[1]
_OUTPUT = _ROOT / "mapsi" / "assets" / "image_not_found.png"

_WIDTH = 640
_HEIGHT = 480

_BORDER_COLOR = (158, 158, 158)
_BORDER_WIDTH = 2

_ICON_OUTLINE = (90, 90, 90)
_ICON_FILL_PAPER = (255, 255, 255)
_ICON_BLUE = (60, 90, 153)
_ICON_GREEN = (72, 138, 80)
_ICON_RED = (210, 60, 60)

_TEXT_COLOR = (60, 90, 153)
_TEXT = "이미지를 불러올 수 없습니다."

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _draw_broken_icon(draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 36) -> None:
    """좌상단 'broken image' 아이콘 (종이 + 산/태양 + X) 를 그린다."""
    fold = max(6, size // 5)

    paper_poly = [
        (x, y),
        (x + size - fold, y),
        (x + size, y + fold),
        (x + size, y + size),
        (x, y + size),
    ]
    draw.polygon(paper_poly, fill=_ICON_FILL_PAPER, outline=_ICON_OUTLINE)
    draw.line(
        [(x + size - fold, y), (x + size - fold, y + fold), (x + size, y + fold)],
        fill=_ICON_OUTLINE,
        width=1,
    )

    # 내부 작은 산 실루엣 (아래쪽)
    base_y = y + size - 4
    mountain = [
        (x + 4, base_y),
        (x + size // 2 - 2, y + size // 2 + 2),
        (x + size - 6, base_y),
    ]
    draw.polygon(mountain, fill=_ICON_GREEN, outline=_ICON_GREEN)

    # 태양/원 (좌상단 안쪽)
    sun_r = max(2, size // 10)
    sun_cx = x + size // 3
    sun_cy = y + size // 2 - 2
    draw.ellipse(
        [sun_cx - sun_r, sun_cy - sun_r, sun_cx + sun_r, sun_cy + sun_r],
        fill=_ICON_BLUE,
        outline=_ICON_BLUE,
    )

    # 우상단 X (깨짐 표시)
    x0 = x + size - fold - 2
    y0 = y + 2
    x1 = x + size - 2
    y1 = y + fold + 4
    draw.line([(x0, y0), (x1, y1)], fill=_ICON_RED, width=2)
    draw.line([(x0, y1), (x1, y0)], fill=_ICON_RED, width=2)


def main() -> None:
    img = Image.new("RGB", (_WIDTH, _HEIGHT), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    pad = 40
    draw.rectangle(
        [pad, pad, _WIDTH - pad, _HEIGHT - pad],
        outline=_BORDER_COLOR,
        width=_BORDER_WIDTH,
    )

    icon_x = pad + 18
    icon_y = pad + 18
    icon_size = 36
    _draw_broken_icon(draw, icon_x, icon_y, size=icon_size)

    font = _load_font(22)
    text_x = icon_x + icon_size + 10
    text_y = icon_y + (icon_size // 2) - 12
    draw.text((text_x, text_y), _TEXT, font=font, fill=_TEXT_COLOR)

    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(_OUTPUT, format="PNG", optimize=True)
    print(f"written: {_OUTPUT}  ({_OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
