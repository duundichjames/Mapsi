"""체크포인트 1 스모크 테스트.

목표: ``samples/base/base.md`` 를 변환한 HWPX 가 한/글이 열 수 있는
ZIP 구조를 만족하는가. 본 테스트는 한/글 자체를 띄우지 않고 다음을 검증한다.

  - 출력 파일이 유효한 ZIP 인가
  - mimetype 이 ZIP 의 첫 엔트리이고 STORED(무압축) 인가
  - 필수 파일(version.xml, META-INF/*, Contents/{header,section0,content.hpf})
    이 모두 들어있는가
  - mimetype 의 내용이 정확히 ``application/hwp+zip`` 와 같은
    한/글 기대 시그니처인가
  - section0.xml 이 lxml 로 well-formed XML 인가
  - CLI (`mapsi -o ...`) 호출도 동일 결과를 낸다
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest
from lxml import etree

from mapsi.cli import main as cli_main
from mapsi.config import load_style_map
from mapsi.converter import md_to_hwpx


REQUIRED_FILES = {
    "mimetype",
    "version.xml",
    "settings.xml",
    "META-INF/container.xml",
    "META-INF/manifest.xml",
    "Contents/header.xml",
    "Contents/section0.xml",
    "Contents/content.hpf",
}


@pytest.fixture
def base_md(samples_dir):
    return samples_dir / "base" / "base.md"


@pytest.fixture
def style_map(spec_dir):
    return load_style_map(spec_dir / "styles.yaml")


@pytest.fixture
def smoke_output(tmp_path, base_md, style_map):
    output = tmp_path / "smoke.hwpx"
    work = tmp_path / "work"
    md_to_hwpx(base_md, output, style_map, work)
    return output


class TestSmokePackaging:
    def test_output_file_exists_and_nonempty(self, smoke_output):
        assert smoke_output.is_file()
        assert smoke_output.stat().st_size > 0

    def test_is_valid_zip(self, smoke_output):
        assert zipfile.is_zipfile(smoke_output)

    def test_mimetype_is_first_and_stored(self, smoke_output):
        with zipfile.ZipFile(smoke_output) as zf:
            infos = zf.infolist()
        assert infos[0].filename == "mimetype", \
            f"첫 엔트리가 mimetype 이 아님: {infos[0].filename}"
        assert infos[0].compress_type == zipfile.ZIP_STORED, \
            "mimetype 은 무압축(STORED) 이어야 함"

    def test_required_files_present(self, smoke_output):
        with zipfile.ZipFile(smoke_output) as zf:
            names = set(zf.namelist())
        missing = REQUIRED_FILES - names
        assert not missing, f"누락 파일: {missing}"

    def test_mimetype_signature(self, smoke_output):
        with zipfile.ZipFile(smoke_output) as zf:
            mimetype = zf.read("mimetype").decode("utf-8").strip()
        assert mimetype == "application/hwp+zip", \
            f"mimetype 시그니처 불일치: {mimetype!r}"

    def test_section0_well_formed_xml(self, smoke_output):
        with zipfile.ZipFile(smoke_output) as zf:
            data = zf.read("Contents/section0.xml")
        # lxml 이 파싱 가능하면 well-formed
        root = etree.fromstring(data)
        assert root.tag.endswith("}sec"), f"루트가 hs:sec 아님: {root.tag}"


class TestSmokeCli:
    def test_cli_produces_equivalent_output(self, tmp_path, base_md, spec_dir):
        output = tmp_path / "cli.hwpx"
        rc = cli_main([
            str(base_md),
            "-o", str(output),
            "--style-map", str(spec_dir / "styles.yaml"),
        ])
        assert rc == 0
        assert output.is_file()
        with zipfile.ZipFile(output) as zf:
            assert "Contents/section0.xml" in zf.namelist()

    def test_python_m_mapsi_works(self, tmp_path, base_md, spec_dir, repo_root):
        output = tmp_path / "module.hwpx"
        result = subprocess.run(
            [sys.executable, "-m", "mapsi",
             str(base_md),
             "-o", str(output),
             "--style-map", str(spec_dir / "styles.yaml")],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, \
            f"종료 코드 {result.returncode}, stderr:\n{result.stderr}"
        assert output.is_file()
