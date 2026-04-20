"""PPT 설명용 예시 차트 생성기 — ``분기별 매출 추이`` 막대 그래프.

"그림 + 캡션" 파이프라인 예시 (``md → parser → walker → builder → hwpx``) 를
설명하면서 ``chart.png`` 라는 가상 이미지가 어떻게 생겼을지 PPT 에서 보여주기
위한 단발성 일러스트. Pillow 만으로 막대 그래프를 그리며 외부 차트 라이브러리
의존성을 추가하지 않는다.

사용법::

    python scripts/make_chart_example.py

출력: ``samples/demo/images/chart.png``.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


_ROOT = Path(__file__).resolve().parents[1]
_OUT = _ROOT / "samples" / "demo" / "images" / "chart.png"


_FONT_CANDIDATES: tuple[str, ...] = (
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/Library/Fonts/AppleGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)


BG = (255, 255, 255)
AXIS = (180, 188, 200)
GRID = (230, 233, 240)
TEXT = (55, 62, 80)
SUB = (120, 130, 145)
BAR_TOP = (88, 140, 220)
BAR_BOT = (56, 100, 180)
BAR_EDGE = (40, 80, 150)
TITLE = (30, 60, 120)


def _resolve_font_path() -> str:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return path
    raise RuntimeError(
        "한글 TrueType 폰트를 찾지 못했다. 후보: " + ", ".join(_FONT_CANDIDATES)
    )


_FONT_PATH = _resolve_font_path()


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_FONT_PATH, size)


def _text_size(draw: ImageDraw.ImageDraw, s: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    l, t, r, b = draw.textbbox((0, 0), s, font=font)
    return r - l, b - t


def main() -> None:
    W, H = 900, 560
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    font_title = _font(26)
    font_axis = _font(16)
    font_value = _font(15)
    font_label = _font(17)

    # 제목
    title = "분기별 매출 추이 (2025)"
    tw, _ = _text_size(draw, title, font_title)
    draw.text(((W - tw) // 2, 28), title, fill=TITLE, font=font_title)

    # 차트 영역
    pad_l, pad_r, pad_t, pad_b = 90, 50, 90, 90
    plot_x0, plot_y0 = pad_l, pad_t
    plot_x1, plot_y1 = W - pad_r, H - pad_b
    plot_w = plot_x1 - plot_x0
    plot_h = plot_y1 - plot_y0

    # 데이터 — 오름세로 설계 (매출 추이라 시각적으로 보기 좋게)
    quarters = ["1분기", "2분기", "3분기", "4분기"]
    values = [120, 185, 230, 310]  # 단위: 백만원
    y_max = 400
    y_ticks = [0, 100, 200, 300, 400]

    # Y 축 그리드 + 라벨
    for tick in y_ticks:
        y = plot_y1 - (tick / y_max) * plot_h
        draw.line([(plot_x0, y), (plot_x1, y)], fill=GRID, width=1)
        label = str(tick)
        lw, lh = _text_size(draw, label, font_axis)
        draw.text((plot_x0 - 14 - lw, y - lh // 2), label, fill=SUB, font=font_axis)

    # Y 축 제목
    draw.text((plot_x0 - 70, plot_t := plot_y0 - 30), "매출(백만원)", fill=SUB, font=font_axis)

    # X / Y 축 선
    draw.line([(plot_x0, plot_y0), (plot_x0, plot_y1)], fill=AXIS, width=2)
    draw.line([(plot_x0, plot_y1), (plot_x1, plot_y1)], fill=AXIS, width=2)

    # 막대
    n = len(values)
    group_w = plot_w / n
    bar_w = group_w * 0.5
    for i, (q, v) in enumerate(zip(quarters, values)):
        cx = plot_x0 + group_w * (i + 0.5)
        bx0 = cx - bar_w / 2
        bx1 = cx + bar_w / 2
        by1 = plot_y1
        by0 = plot_y1 - (v / y_max) * plot_h

        # 세로 그라데이션으로 막대 채우기
        bar_h = int(by1 - by0)
        if bar_h > 0:
            for row in range(bar_h):
                t = row / bar_h
                r = int(BAR_TOP[0] * (1 - t) + BAR_BOT[0] * t)
                g = int(BAR_TOP[1] * (1 - t) + BAR_BOT[1] * t)
                b = int(BAR_TOP[2] * (1 - t) + BAR_BOT[2] * t)
                y = by0 + row
                draw.line([(bx0, y), (bx1, y)], fill=(r, g, b), width=1)
        draw.rectangle([(bx0, by0), (bx1, by1)], outline=BAR_EDGE, width=2)

        # 막대 위 값
        vlabel = f"{v}"
        vw, vh = _text_size(draw, vlabel, font_value)
        draw.text((cx - vw // 2, by0 - vh - 6), vlabel, fill=TEXT, font=font_value)

        # X 축 라벨 (분기)
        qw, qh = _text_size(draw, q, font_label)
        draw.text((cx - qw // 2, plot_y1 + 12), q, fill=TEXT, font=font_label)

    # 하단 캡션 — 이 이미지가 PPT 에서 참조될 때 한/글이 자동으로
    # "그림 1. 분기별 매출 추이" 로 렌더한다는 것을 암시
    foot = "출처: 예시 데이터"
    fw, _ = _text_size(draw, foot, font_axis)
    draw.text((W - pad_r - fw, H - 30), foot, fill=SUB, font=font_axis)

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(_OUT, format="PNG", optimize=True)
    print(f"written: {_OUT} ({_OUT.stat().st_size:,} bytes) font={_FONT_PATH}")


if __name__ == "__main__":
    main()
