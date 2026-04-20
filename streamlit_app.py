from __future__ import annotations

import io
import os
import re
import tempfile
import zipfile
from pathlib import Path

import streamlit as st

from mapsi.config import load_style_map
from mapsi.converter import md_to_hwpx


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_STYLE_MAP = REPO_ROOT / "spec" / "styles.yaml"


st.set_page_config(
    page_title="Mapsi UI",
    page_icon="📝",
    layout="wide",
)

st.title("Mapsi")
st.caption("Markdown 파일을 한/글 HWPX 로 변환하는 Streamlit UI")


def _render_sidebar() -> tuple[Path, bool]:
    st.sidebar.header("변환 설정")

    style_map_path = st.sidebar.text_input(
        "스타일 매핑 경로",
        value=str(DEFAULT_STYLE_MAP),
        help="기본값은 spec/styles.yaml 입니다.",
    )

    disable_llm = st.sidebar.checkbox(
        "수식 변환에서 LLM 비활성화",
        value=False,
        help="체크하면 수식은 폴백 문자열로 처리됩니다.",
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "이 UI는 `mapsi.converter.md_to_hwpx()`를 직접 호출합니다."
    )

    return Path(style_map_path), disable_llm


def _read_uploaded_markdown(uploaded_file) -> str:
    return uploaded_file.getvalue().decode("utf-8")


def _sanitize_markdown(markdown_text: str) -> str:
    """Mapsi 가 아직 지원하지 않는 Markdown 구문을 안전한 형태로 바꾼다.

    현재는 standalone horizontal rule (`---`, `***`, `___`) 을 빈 줄로 치환한다.
    """
    sanitized = re.sub(
        r"(?m)^[ \t]*([-*_])(?:[ \t]*\1){2,}[ \t]*$",
        "",
        markdown_text,
    )
    return sanitized



def _convert_markdown_to_hwpx(
    markdown_text: str,
    input_name: str,
    style_map_path: Path,
    disable_llm: bool,
) -> tuple[bytes, str, list[str]]:
    """Markdown 텍스트를 HWPX 로 변환해 ``(bytes, filename, missing_images)`` 반환.

    UI 는 업로드된 Markdown *텍스트* 만 다루므로, 상대경로로 참조된 그림
    원본은 tempdir 기준으로 해석되지 않는다. 이런 누락 이미지는
    ``allow_missing_images=True`` 로 placeholder PNG 로 대체되며 누락 목록은
    호출자에게 반환되어 경고 배너로 노출된다.
    """
    if not markdown_text.strip():
        raise ValueError("입력된 Markdown 내용이 비어 있습니다.")

    markdown_text = _sanitize_markdown(markdown_text)

    if not style_map_path.is_file():
        raise FileNotFoundError(
            f"스타일 매핑 파일을 찾을 수 없습니다: {style_map_path}"
        )

    style_map = load_style_map(style_map_path)

    with tempfile.TemporaryDirectory(prefix="mapsi-ui-") as temp_dir:
        temp_root = Path(temp_dir)
        input_path = temp_root / input_name
        output_path = temp_root / f"{Path(input_name).stem}.hwpx"
        work_dir = temp_root / "work"

        input_path.write_text(markdown_text, encoding="utf-8")

        missing_images: list[str] = []
        with _temporary_no_llm(disable_llm):
            md_to_hwpx(
                md_path=input_path,
                output_path=output_path,
                style_map=style_map,
                work_dir=work_dir,
                allow_missing_images=True,
                missing_images_report=missing_images,
            )

        return output_path.read_bytes(), output_path.name, missing_images


class _temporary_no_llm:
    """``MAPSI_NO_LLM`` 환경변수를 일시적으로 덮어쓰는 컨텍스트 매니저."""

    def __init__(self, disable: bool) -> None:
        self._disable = disable
        self._previous: str | None = None

    def __enter__(self) -> "_temporary_no_llm":
        self._previous = os.environ.get("MAPSI_NO_LLM")
        if self._disable:
            os.environ["MAPSI_NO_LLM"] = "1"
        else:
            os.environ.pop("MAPSI_NO_LLM", None)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._previous is None:
            os.environ.pop("MAPSI_NO_LLM", None)
        else:
            os.environ["MAPSI_NO_LLM"] = self._previous


def _extract_md_bundle(zip_bytes: bytes, extract_dir: Path) -> Path:
    """ZIP 바이트를 ``extract_dir`` 에 풀고 대표 Markdown 파일 경로를 돌려준다.

    - Zip slip (``..``, 절대경로) 을 차단해 ``extract_dir`` 바깥으로
      빠져나가는 엔트리는 거부한다.
    - 디렉터리 엔트리/맥OS 메타데이터 (``__MACOSX``, ``.DS_Store``) 는 건너뛴다.
    - 대표 Markdown 은 "경로가 가장 얕고, 그 중 파일명이 사전순으로 앞선" 것을
      고른다. ``.md`` 가 없으면 ``.markdown`` 도 허용한다.
    """
    extract_dir = extract_dir.resolve()
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise ValueError("올바른 ZIP 파일이 아닙니다.") from exc

    with zf:
        for info in zf.infolist():
            name = info.filename
            if not name or name.endswith("/"):
                continue
            if name.startswith("__MACOSX/") or name.endswith("/.DS_Store"):
                continue
            if os.path.isabs(name) or ".." in Path(name).parts:
                raise ValueError(f"안전하지 않은 ZIP 엔트리 경로: {name}")
            target = (extract_dir / name).resolve()
            try:
                target.relative_to(extract_dir)
            except ValueError as exc:
                raise ValueError(
                    f"ZIP 엔트리가 추출 루트를 벗어납니다: {name}"
                ) from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())

    candidates: list[Path] = []
    for ext in ("*.md", "*.markdown"):
        candidates.extend(
            p for p in extract_dir.rglob(ext) if "__MACOSX" not in p.parts
        )
    if not candidates:
        raise ValueError(
            "ZIP 안에 .md / .markdown 파일이 없습니다. "
            "ZIP 루트 근처에 변환할 Markdown 파일을 포함시켜 주세요."
        )

    candidates.sort(key=lambda p: (len(p.relative_to(extract_dir).parts), p.name))
    return candidates[0]


def _convert_zip_to_hwpx(
    zip_bytes: bytes,
    style_map_path: Path,
    disable_llm: bool,
) -> tuple[bytes, str, Path, str]:
    """ZIP (Markdown + 이미지) 를 HWPX 로 변환.

    ZIP 을 임시 디렉터리에 풀어 원본 디렉터리 구조를 보존하므로, Markdown 이
    상대경로로 참조하는 이미지가 ``md_to_hwpx`` 에서 그대로 해석된다. 따라서
    파일 업로드 경로와 달리 placeholder 대체가 필요 없고
    ``allow_missing_images=False`` 를 유지한다.

    Returns
    -------
    (hwpx_bytes, hwpx_filename, md_rel_path, md_preview_text)
        ``md_rel_path`` / ``md_preview_text`` 는 UI 미리보기 용도.
    """
    if not style_map_path.is_file():
        raise FileNotFoundError(
            f"스타일 매핑 파일을 찾을 수 없습니다: {style_map_path}"
        )

    style_map = load_style_map(style_map_path)

    with tempfile.TemporaryDirectory(prefix="mapsi-ui-zip-") as temp_dir:
        temp_root = Path(temp_dir)
        extract_dir = temp_root / "extract"
        extract_dir.mkdir()

        md_path = _extract_md_bundle(zip_bytes, extract_dir)
        md_rel = md_path.relative_to(extract_dir)

        raw_text = md_path.read_text(encoding="utf-8")
        sanitized = _sanitize_markdown(raw_text)
        if sanitized != raw_text:
            md_path.write_text(sanitized, encoding="utf-8")

        output_path = temp_root / f"{md_path.stem}.hwpx"
        work_dir = temp_root / "work"

        with _temporary_no_llm(disable_llm):
            md_to_hwpx(
                md_path=md_path,
                output_path=output_path,
                style_map=style_map,
                work_dir=work_dir,
                allow_missing_images=False,
            )

        return (
            output_path.read_bytes(),
            output_path.name,
            md_rel,
            sanitized,
        )


style_map_path, disable_llm = _render_sidebar()

tab_upload, tab_paste, tab_zip = st.tabs(
    ["파일 업로드", "텍스트 붙여넣기", "Markdown + 이미지 ZIP"]
)

uploaded_markdown_text = ""
uploaded_markdown_name = "input.md"
uploaded_zip_bytes: bytes | None = None
uploaded_zip_name = ""

with tab_upload:
    uploaded_file = st.file_uploader(
        "Markdown 파일 업로드",
        type=["md", "markdown"],
        help=".md 또는 .markdown 파일을 업로드하세요.",
    )

    if uploaded_file is not None:
        uploaded_markdown_name = uploaded_file.name or "input.md"
        uploaded_markdown_text = _read_uploaded_markdown(uploaded_file)

        st.subheader("업로드된 Markdown 미리보기")
        st.code(uploaded_markdown_text, language="markdown")

with tab_paste:
    pasted_markdown_text = st.text_area(
        "Markdown 직접 입력",
        height=360,
        placeholder="# 제목\n\n여기에 Markdown 내용을 입력하세요.",
    )

    if pasted_markdown_text.strip():
        uploaded_markdown_text = pasted_markdown_text
        uploaded_markdown_name = "pasted_input.md"

        st.subheader("입력된 Markdown 미리보기")
        st.code(uploaded_markdown_text, language="markdown")

with tab_zip:
    st.markdown(
        "이미지가 포함된 Markdown 을 변환할 때 사용하세요. "
        "`.md` 파일과 참조된 이미지 파일을 **원본 폴더 구조 그대로** "
        "하나의 ZIP 으로 묶어서 업로드하면, Markdown 안의 상대경로가 "
        "그대로 해석됩니다."
    )
    with st.expander("ZIP 구성 예시"):
        st.code(
            "my_doc.zip\n"
            "├── my_doc.md\n"
            "└── images/\n"
            "    ├── figure1.png\n"
            "    └── figure2.jpg\n"
            "\n"
            "# my_doc.md 안에서는:\n"
            "# ![그림1](images/figure1.png)\n",
            language="text",
        )

    zip_file = st.file_uploader(
        "Markdown + 이미지 ZIP 업로드",
        type=["zip"],
        help="루트(혹은 그에 가까운 위치)에 .md 파일이 하나 이상 포함되어야 합니다.",
        key="zip_uploader",
    )

    if zip_file is not None:
        uploaded_zip_bytes = zip_file.getvalue()
        uploaded_zip_name = zip_file.name or "bundle.zip"

        try:
            with zipfile.ZipFile(io.BytesIO(uploaded_zip_bytes)) as zf:
                entries = [
                    n for n in zf.namelist()
                    if n and not n.endswith("/")
                    and not n.startswith("__MACOSX/")
                    and not n.endswith("/.DS_Store")
                ]
        except zipfile.BadZipFile:
            st.error("올바른 ZIP 파일이 아닙니다.")
            uploaded_zip_bytes = None
            entries = []

        if uploaded_zip_bytes is not None:
            st.caption(
                f"업로드된 ZIP: **{uploaded_zip_name}** — 엔트리 {len(entries)}개"
            )
            with st.expander("ZIP 내용 보기"):
                for name in sorted(entries):
                    st.code(name, language="text")

st.markdown("---")

col_left, col_right = st.columns([2, 1])

with col_left:
    convert_clicked = st.button(
        "HWPX로 변환",
        type="primary",
        use_container_width=True,
    )

with col_right:
    st.info(
        "파일 업로드 · 텍스트 입력 · ZIP 업로드 중 하나만 채워도 변환할 수 있습니다. "
        "여러 입력이 동시에 있으면 **ZIP 업로드가 우선**입니다."
    )

if convert_clicked:
    if uploaded_zip_bytes is not None:
        with st.spinner("ZIP 을 풀고 HWPX 파일을 생성하는 중입니다..."):
            try:
                hwpx_bytes, hwpx_filename, md_rel, md_preview = (
                    _convert_zip_to_hwpx(
                        zip_bytes=uploaded_zip_bytes,
                        style_map_path=style_map_path,
                        disable_llm=disable_llm,
                    )
                )
            except Exception as exc:
                st.error("ZIP 변환 중 오류가 발생했습니다.")
                st.exception(exc)
            else:
                st.success(
                    f"변환이 완료되었습니다. (사용한 Markdown: `{md_rel}`)"
                )
                with st.expander("변환에 사용된 Markdown 미리보기"):
                    st.code(md_preview, language="markdown")
                st.download_button(
                    label="HWPX 다운로드",
                    data=hwpx_bytes,
                    file_name=hwpx_filename,
                    mime="application/zip",
                    use_container_width=True,
                )
    elif uploaded_markdown_text.strip():
        with st.spinner("HWPX 파일을 생성하는 중입니다..."):
            try:
                hwpx_bytes, hwpx_filename, missing_images = (
                    _convert_markdown_to_hwpx(
                        markdown_text=uploaded_markdown_text,
                        input_name=uploaded_markdown_name,
                        style_map_path=style_map_path,
                        disable_llm=disable_llm,
                    )
                )
            except Exception as exc:
                st.error("변환 중 오류가 발생했습니다.")
                st.exception(exc)
            else:
                st.success("변환이 완료되었습니다.")
                if missing_images:
                    st.warning(
                        f"다음 이미지 {len(missing_images)}개를 찾지 못해 "
                        "대체 이미지('이미지를 불러올 수 없습니다.')로 "
                        "표시했습니다. 이미지 파일까지 포함해 변환하려면 "
                        "**Markdown + 이미지 ZIP** 탭을 이용하세요."
                    )
                    with st.expander("누락된 이미지 경로 보기"):
                        for src in missing_images:
                            st.code(src, language="text")
                st.download_button(
                    label="HWPX 다운로드",
                    data=hwpx_bytes,
                    file_name=hwpx_filename,
                    mime="application/zip",
                    use_container_width=True,
                )
    else:
        st.warning(
            "먼저 Markdown 파일을 업로드하거나, 텍스트를 입력하거나, "
            "ZIP 을 업로드하세요."
        )
