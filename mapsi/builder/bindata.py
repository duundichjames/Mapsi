"""이미지 등록 (계약 3, C 영역).

원본 이미지를 work_dir/BinData/ 로 복사하고, hp:img / manifest 가 함께
참조할 binary_item_id 와 manifest entry 를 반환한다.
"""

from __future__ import annotations

import hashlib
import shutil
import unicodedata
from pathlib import Path


__all__ = ["register_image"]


_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
}


def register_image(src_path: str, work_dir: str) -> tuple[str, dict]:
    """이미지를 work_dir/BinData/ 로 복사하고 (binary_item_id, manifest_entry) 반환."""
    src = Path(src_path)
    if not src.is_file():
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없음: {src}")

    normalized_name = unicodedata.normalize("NFC", src.name)
    ext = Path(normalized_name).suffix.lower()
    media_type = _MEDIA_TYPES.get(ext)
    if media_type is None:
        raise ValueError(f"지원하지 않는 이미지 확장자: {src.suffix or '(없음)'}")

    bindata_dir = Path(work_dir) / "BinData"
    bindata_dir.mkdir(parents=True, exist_ok=True)

    source_hash = _sha256_file(src)

    # 같은 내용의 이미지가 이미 등록되어 있으면 기존 항목을 재사용한다.
    for existing in _iter_registered_images(bindata_dir):
        if _sha256_file(existing) == source_hash:
            binary_item_id = existing.stem
            return binary_item_id, _build_manifest_entry(
                binary_item_id=binary_item_id,
                filename=existing.name,
                media_type=_MEDIA_TYPES[existing.suffix.lower()],
            )

    next_number = _next_image_number(bindata_dir)
    binary_item_id = f"image{next_number}"
    dest_name = f"{binary_item_id}{ext}"
    dest_path = bindata_dir / dest_name

    shutil.copy2(src, dest_path)

    return binary_item_id, _build_manifest_entry(
        binary_item_id=binary_item_id,
        filename=dest_name,
        media_type=media_type,
    )


def _build_manifest_entry(binary_item_id: str, filename: str, media_type: str) -> dict:
    return {
        "id": binary_item_id,
        "href": f"BinData/{filename}",
        "media-type": media_type,
    }


def _iter_registered_images(bindata_dir: Path):
    files: list[Path] = []
    for path in bindata_dir.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in _MEDIA_TYPES:
            continue
        if not path.stem.startswith("image"):
            continue
        files.append(path)
    yield from sorted(files, key=lambda p: p.name)


def _next_image_number(bindata_dir: Path) -> int:
    max_number = 0
    for path in _iter_registered_images(bindata_dir):
        suffix = path.stem.removeprefix("image")
        if suffix.isdigit():
            max_number = max(max_number, int(suffix))
    return max_number + 1


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
