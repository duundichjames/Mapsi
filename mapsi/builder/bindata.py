"""``BinData/`` 자산 등록기 (계약 3, C 영역).

C 부재 기간 동안 B 가 임시 구현. 그림 1 개당 ``register_image`` 가 1 회
호출되어 원본 파일을 ``work_dir/BinData/imageN.<ext>`` 로 복사하고
``hp:pic`` 의 ``hc:img binaryItemIDRef`` 가 참조할 ID 문자열을 발급한다.

계약 표면 (``spec/interfaces.md`` §계약 3):

.. code-block:: python

    def register_image(src_path: str, work_dir: str) -> tuple[str, dict]:
        ...

ID 발급 전략
-----------

여러 그림이 한 문서에 등장할 때 ID 가 충돌하지 않아야 한다. 호출간 상태를
주고받지 않기 위해 ``work_dir/BinData/`` 디렉토리를 매 호출마다 스캔해서
``image<N>.*`` 의 최대 N 을 찾고 ``image<N+1>`` 로 결정한다. 동시 호출이
없는 단일 스레드 변환 파이프라인 가정에서 안전하다.
"""

from __future__ import annotations

import mimetypes
import re
import shutil
from pathlib import Path


__all__ = ["register_image"]


_ID_PATTERN = re.compile(r"^image(\d+)\.")


def register_image(src_path: str | Path, work_dir: str | Path) -> tuple[str, dict]:
    """원본 이미지를 ``work_dir/BinData/`` 로 복사하고 ID + manifest 항목을 발급.

    Parameters
    ----------
    src_path:
        복사할 원본 이미지 파일 경로. 존재하지 않으면
        :class:`FileNotFoundError`.
    work_dir:
        ``mimetype``, ``Contents/`` 등이 부트스트랩된 변환 작업 디렉토리.
        ``BinData/`` 가 없으면 자동 생성된다.

    Returns
    -------
    (binary_item_id, manifest_entry)
        - ``binary_item_id``: ``"image1"``, ``"image2"`` 등 문서 내 유일한
          ID 문자열. ``hp:pic`` 의 ``hc:img binaryItemIDRef`` 가 참조한다.
        - ``manifest_entry``: ``content.hpf`` 의 ``opf:manifest`` 에 추가할
          항목 dict. 키는 ``id``, ``href``, ``media-type`` (계약 3 명시).

    Raises
    ------
    FileNotFoundError
        ``src_path`` 가 존재하지 않을 때.
    ValueError
        ``src_path`` 의 확장자로부터 media type 을 추정할 수 없을 때.

    Notes
    -----
    BinData 안의 파일명은 ``image<N><원본확장자>`` 로 통일한다 (확장자는
    소문자). 원본 파일명 자체는 보존하지 않는다 — 공백/한글/특수문자가
    HWPX 내부 경로에서 일으킬 수 있는 호환성 문제를 회피.
    """
    src = Path(src_path)
    if not src.is_file():
        raise FileNotFoundError(f"이미지 원본을 찾을 수 없음: {src}")

    work = Path(work_dir)
    bindata = work / "BinData"
    bindata.mkdir(parents=True, exist_ok=True)

    next_idx = _next_image_index(bindata)
    ext = src.suffix.lower()
    if not ext:
        raise ValueError(f"이미지 확장자 누락: {src}")
    media_type = _guess_media_type(ext)

    item_id = f"image{next_idx}"
    arc_name = f"{item_id}{ext}"
    dest = bindata / arc_name
    shutil.copy2(src, dest)

    manifest_entry = {
        "id": item_id,
        "href": f"BinData/{arc_name}",
        "media-type": media_type,
    }
    return item_id, manifest_entry


def _next_image_index(bindata_dir: Path) -> int:
    """``BinData/image<N>.*`` 중 최대 N 을 찾아 N+1 을 반환. 없으면 1."""
    max_n = 0
    for entry in bindata_dir.iterdir():
        if not entry.is_file():
            continue
        m = _ID_PATTERN.match(entry.name)
        if m is None:
            continue
        n = int(m.group(1))
        if n > max_n:
            max_n = n
    return max_n + 1


def _guess_media_type(ext: str) -> str:
    """확장자 (소문자, 점 포함) 로부터 IANA media type 추정.

    ``mimetypes`` stdlib 가 일부 (.bmp 등) 를 잘 못 추정하므로 명시적
    fallback 표를 둔다.
    """
    explicit = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".bmp": "image/bmp",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    if ext in explicit:
        return explicit[ext]
    guessed, _ = mimetypes.guess_type(f"x{ext}")
    if guessed and guessed.startswith("image/"):
        return guessed
    raise ValueError(f"확장자 {ext!r} 의 media type 을 추정할 수 없음")
