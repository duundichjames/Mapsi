from __future__ import annotations

import re
import tempfile
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

        import os
        previous_no_llm = os.environ.get("MAPSI_NO_LLM")
        missing_images: list[str] = []
        try:
            if disable_llm:
                os.environ["MAPSI_NO_LLM"] = "1"
            else:
                os.environ.pop("MAPSI_NO_LLM", None)

            md_to_hwpx(
                md_path=input_path,
                output_path=output_path,
                style_map=style_map,
                work_dir=work_dir,
                allow_missing_images=True,
                missing_images_report=missing_images,
            )
        finally:
            if previous_no_llm is None:
                os.environ.pop("MAPSI_NO_LLM", None)
            else:
                os.environ["MAPSI_NO_LLM"] = previous_no_llm

        return output_path.read_bytes(), output_path.name, missing_images


style_map_path, disable_llm = _render_sidebar()

tab_upload, tab_paste = st.tabs(["파일 업로드", "텍스트 붙여넣기"])

uploaded_markdown_text = ""
uploaded_markdown_name = "input.md"

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
        "파일 업로드 또는 텍스트 입력 중 하나만 채워도 변환할 수 있습니다."
    )

if convert_clicked:
    if not uploaded_markdown_text.strip():
        st.warning("먼저 Markdown 파일을 업로드하거나 텍스트를 입력하세요.")
    else:
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
                        "표시했습니다. UI 업로드 경로에서는 Markdown 이 "
                        "참조하는 원본 이미지 파일을 함께 읽을 수 없어 "
                        "발생하는 정상 동작입니다."
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
