"""Unit tests for private submission storage and untrusted inputs."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from struct import pack_into
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from app.submission_storage import (
    MAX_ARCHIVE_ENTRIES,
    MAX_ARCHIVE_UNCOMPRESSED_BYTES,
    MAX_FILE_SIZE_BYTES,
    FileValidationError,
    PrivateStorageUnavailable,
    stage_upload,
    validate_submission_url,
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://example.org/submissions/srs", "https://example.org/submissions/srs"),
        ("https://EXAMPLE.org:443/srs", "https://example.org:443/srs"),
    ],
)
def test_validate_submission_url_accepts_public_https_urls(
    url: str, expected: str
) -> None:
    assert validate_submission_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org/srs",
        "javascript:alert(1)",
        "data:text/plain,unsafe",
        "file:///etc/passwd",
        "https://user:pass@example.org/srs",
        "https://example.org/srs#fragment",
        "https://localhost/srs",
        "https://service.local/srs",
        "https://127.0.0.1/srs",
        "https://10.1.2.3/srs",
        "https://[::1]/srs",
        "https://bad host.example/srs",
        "https://example.org/" + "x" * 2049,
    ],
)
def test_validate_submission_url_rejects_unsafe_or_malformed_urls(url: str) -> None:
    with pytest.raises(FileValidationError):
        validate_submission_url(url)


def test_stage_upload_streams_valid_pdf_to_opaque_private_key(tmp_path: Path) -> None:
    staged = stage_upload(
        BytesIO(b"%PDF-1.7\nsynthetic document"),
        filename="Synthetic-SRS.pdf",
        content_type="application/pdf",
        configured_dir=str(tmp_path),
    )

    try:
        assert staged.file_size_bytes == 27
        assert staged.media_type == "application/pdf"
        assert staged.original_filename == "Synthetic-SRS.pdf"
        assert len(staged.storage_key) == 32
        assert Path(staged.temp_path).parent == tmp_path
        assert not staged.storage_key.endswith(".pdf")
        assert Path(staged.temp_path).read_bytes() == b"%PDF-1.7\nsynthetic document"
    finally:
        staged.cleanup()

    assert list(tmp_path.iterdir()) == []


def test_stage_upload_rejects_zero_byte_files_and_cleans_temp_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileValidationError) as raised:
        stage_upload(
            BytesIO(b""),
            filename="empty.txt",
            content_type="text/plain",
            configured_dir=str(tmp_path),
        )

    assert raised.value.status_code == 422
    assert list(tmp_path.iterdir()) == []


def test_stage_upload_accepts_exact_size_and_rejects_one_byte_over(
    tmp_path: Path,
) -> None:
    exact = stage_upload(
        BytesIO(b"x" * MAX_FILE_SIZE_BYTES),
        filename="large.txt",
        content_type="text/plain",
        configured_dir=str(tmp_path),
    )
    assert exact.file_size_bytes == MAX_FILE_SIZE_BYTES
    exact.cleanup()

    with pytest.raises(FileValidationError) as raised:
        stage_upload(
            BytesIO(b"x" * (MAX_FILE_SIZE_BYTES + 1)),
            filename="too-large.txt",
            content_type="text/plain",
            configured_dir=str(tmp_path),
        )

    assert raised.value.status_code == 413
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "filename",
    [
        "../report.pdf",
        "folder/report.pdf",
        r"folder\report.pdf",
        "C:report.pdf",
        "report.exe.pdf",
        "report\r\nX-Injected: yes.pdf",
        "report\x00.pdf",
        "x" * 252 + ".pdf",
        "unsafe.svg",
    ],
)
def test_stage_upload_rejects_dangerous_names_and_extensions(
    tmp_path: Path, filename: str
) -> None:
    with pytest.raises(FileValidationError):
        stage_upload(
            BytesIO(b"%PDF-1.7\nsynthetic"),
            filename=filename,
            content_type="application/pdf",
            configured_dir=str(tmp_path),
        )

    assert list(tmp_path.iterdir()) == []


def test_stage_upload_rejects_mime_and_signature_mismatch(tmp_path: Path) -> None:
    with pytest.raises(FileValidationError):
        stage_upload(
            BytesIO(b"not a pdf"),
            filename="report.pdf",
            content_type="application/pdf",
            configured_dir=str(tmp_path),
        )

    with pytest.raises(FileValidationError):
        stage_upload(
            BytesIO(b"%PDF-1.7\nsynthetic"),
            filename="report.pdf",
            content_type="text/html",
            configured_dir=str(tmp_path),
        )

    assert list(tmp_path.iterdir()) == []


def test_stage_upload_checks_docx_package_structure(tmp_path: Path) -> None:
    package = BytesIO()
    with ZipFile(package, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")

    staged = stage_upload(
        BytesIO(package.getvalue()),
        filename="Synthetic-SRS.docx",
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        configured_dir=str(tmp_path),
    )
    staged.cleanup()

    with pytest.raises(FileValidationError):
        stage_upload(
            BytesIO(b"PK\x03\x04not a valid package"),
            filename="broken.docx",
            content_type="application/octet-stream",
            configured_dir=str(tmp_path),
        )

    assert list(tmp_path.iterdir()) == []


def test_stage_upload_accepts_supported_image_archive_and_pptx_content(
    tmp_path: Path,
) -> None:
    pptx = BytesIO()
    with ZipFile(pptx, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("ppt/presentation.xml", "<presentation/>")
    zip_bytes = BytesIO()
    with ZipFile(zip_bytes, "w") as archive:
        archive.writestr("synthetic.txt", "safe test data")

    files = [
        ("image.png", b"\x89PNG\r\n\x1a\nsynthetic", "image/png"),
        ("image.jpg", b"\xff\xd8\xffsynthetic", "image/jpeg"),
        ("archive.zip", zip_bytes.getvalue(), "application/octet-stream"),
        (
            "slides.pptx",
            pptx.getvalue(),
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
    ]

    for filename, payload, content_type in files:
        staged = stage_upload(
            BytesIO(payload),
            filename=filename,
            content_type=content_type,
            configured_dir=str(tmp_path),
        )
        assert staged.file_size_bytes == len(payload)
        staged.cleanup()

    assert list(tmp_path.iterdir()) == []


def test_stage_upload_rejects_invalid_utf8_text(tmp_path: Path) -> None:
    with pytest.raises(FileValidationError):
        stage_upload(
            BytesIO(b"valid prefix\xff"),
            filename="notes.txt",
            content_type="text/plain",
            configured_dir=str(tmp_path),
        )

    assert list(tmp_path.iterdir()) == []


def test_stage_upload_rejects_nul_bytes_in_text(tmp_path: Path) -> None:
    with pytest.raises(FileValidationError):
        stage_upload(
            BytesIO(b"synthetic\x00text"),
            filename="notes.txt",
            content_type="text/plain",
            configured_dir=str(tmp_path),
        )

    assert list(tmp_path.iterdir()) == []


def test_stage_upload_rejects_archives_with_excessive_metadata(
    tmp_path: Path,
) -> None:
    many_entries = BytesIO()
    with ZipFile(many_entries, "w") as archive:
        for index in range(MAX_ARCHIVE_ENTRIES + 1):
            archive.writestr(f"entry-{index}.txt", "")

    with pytest.raises(FileValidationError):
        stage_upload(
            BytesIO(many_entries.getvalue()),
            filename="many.zip",
            content_type="application/zip",
            configured_dir=str(tmp_path),
        )

    compact = BytesIO()
    with ZipFile(compact, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("expanded.txt", "x")
    expanded_metadata = bytearray(compact.getvalue())
    central_directory = expanded_metadata.index(b"PK\x01\x02")
    pack_into(
        "<I",
        expanded_metadata,
        central_directory + 24,
        MAX_ARCHIVE_UNCOMPRESSED_BYTES + 1,
    )

    with pytest.raises(FileValidationError):
        stage_upload(
            BytesIO(expanded_metadata),
            filename="expanded.zip",
            content_type="application/zip",
            configured_dir=str(tmp_path),
        )

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("configured_dir", [None, "relative-upload-path"])
def test_private_storage_requires_a_configured_absolute_directory(
    tmp_path: Path, configured_dir: str | None
) -> None:
    with pytest.raises(PrivateStorageUnavailable):
        stage_upload(
            BytesIO(b"%PDF-1.7\nsynthetic"),
            filename="document.pdf",
            content_type="application/pdf",
            configured_dir=configured_dir,
        )

    assert list(tmp_path.iterdir()) == []


def test_private_storage_rejects_repository_paths_before_creating_them() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    rejected_path = repository_root / ".gradtrack-private-uploads-test"

    with pytest.raises(PrivateStorageUnavailable):
        stage_upload(
            BytesIO(b"%PDF-1.7\nsynthetic"),
            filename="document.pdf",
            content_type="application/pdf",
            configured_dir=str(rejected_path),
        )

    assert not rejected_path.exists()


def test_private_storage_rejects_symlinked_roots(tmp_path: Path) -> None:
    actual_root = tmp_path / "actual"
    actual_root.mkdir()
    linked_root = tmp_path / "linked"
    try:
        linked_root.symlink_to(actual_root, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable for this Windows account")

    with pytest.raises(PrivateStorageUnavailable):
        stage_upload(
            BytesIO(b"%PDF-1.7\nsynthetic"),
            filename="document.pdf",
            content_type="application/pdf",
            configured_dir=str(linked_root),
        )

    assert list(actual_root.iterdir()) == []
