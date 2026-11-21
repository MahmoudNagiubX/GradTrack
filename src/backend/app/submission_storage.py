"""Private local storage and validation for untrusted submission files."""

from __future__ import annotations

import codecs
import ipaddress
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4
from zipfile import BadZipFile, LargeZipFile, ZipFile

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024
MAX_AVATAR_SIZE_BYTES = 2 * 1024 * 1024
AVATAR_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg"})
MAX_ARCHIVE_ENTRIES = 1_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
_CHUNK_SIZE = 1024 * 1024
MAX_MULTIPART_OVERHEAD_BYTES = 1024 * 1024
_SUPPORTED_MEDIA_TYPES = {
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    },
    ".pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    },
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".zip": {"application/zip", "application/x-zip-compressed"},
    ".txt": {"text/plain"},
}
_UNSAFE_HOST_SUFFIXES = {
    "corp",
    "example",
    "home",
    "internal",
    "intranet",
    "invalid",
    "lan",
    "local",
    "localdomain",
    "localhost",
    "onion",
    "arpa",
    "test",
}


class FileValidationError(ValueError):
    """An invalid URL, filename, or upload payload with a safe HTTP status."""

    def __init__(self, message: str, *, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


class PrivateStorageUnavailable(RuntimeError):
    """The configured private storage root is missing or unsafe."""


@dataclass(slots=True)
class StagedUpload:
    """A validated temporary file awaiting its database transaction."""

    root: Path
    temp_path: Path
    storage_key: str
    original_filename: str
    file_size_bytes: int
    media_type: str
    final_path: Path | None = None
    committed: bool = False

    def promote(self) -> None:
        """Atomically expose the random key without overwriting an existing file."""
        root = private_storage_root(str(self.root), create=False)
        if self.temp_path.parent != root:
            raise PrivateStorageUnavailable
        _reject_reparse_points(self.temp_path)
        destination = _storage_path(root, self.storage_key)
        _reject_reparse_points(destination)
        try:
            os.link(self.temp_path, destination)
            self.final_path = destination
            self.temp_path.unlink()
        except OSError as error:
            raise PrivateStorageUnavailable from error

    def cleanup(self) -> None:
        """Remove staging files and any promoted file after a failed transaction."""
        try:
            root = private_storage_root(str(self.root), create=False)
        except PrivateStorageUnavailable:
            return
        if self.temp_path.parent != root:
            return
        for path in (self.temp_path, self.final_path if not self.committed else None):
            if path is None:
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError:
                # Cleanup is best effort; the configured root remains private.
                pass


def validate_submission_url(value: str) -> str:
    """Validate and normalize an HTTPS URL without resolving or fetching it."""
    if (
        not value
        or len(value) > 2_048
        or "#" in value
        or "\\" in value
        or any(
            character.isspace() or ord(character) < 32 or ord(character) == 127
            for character in value
        )
        or re.search(r"%(?![0-9A-Fa-f]{2})", value)
    ):
        raise FileValidationError("A valid public HTTPS URL is required")

    try:
        parts = urlsplit(value)
        port = parts.port
        hostname = parts.hostname
    except ValueError:
        raise FileValidationError("A valid public HTTPS URL is required") from None

    if (
        parts.scheme.lower() != "https"
        or not parts.netloc
        or hostname is None
        or parts.username is not None
        or parts.password is not None
        or parts.fragment
    ):
        raise FileValidationError("A valid public HTTPS URL is required")

    if port is not None and not 1 <= port <= 65_535:
        raise FileValidationError("A valid public HTTPS URL is required")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None

    if address is not None:
        if not address.is_global:
            raise FileValidationError("A valid public HTTPS URL is required")
        normalized_host = (
            f"[{address.compressed}]" if address.version == 6 else address.compressed
        )
    else:
        if hostname.endswith(".."):
            raise FileValidationError("A valid public HTTPS URL is required")
        if "%" in hostname:
            raise FileValidationError("A valid public HTTPS URL is required")
        try:
            normalized_host = (
                hostname.rstrip(".").encode("idna").decode("ascii").lower()
            )
        except UnicodeError:
            raise FileValidationError("A valid public HTTPS URL is required") from None
        labels = normalized_host.split(".")
        if (
            not normalized_host
            or len(normalized_host) > 253
            or len(labels) < 2
            or labels[-1] in _UNSAFE_HOST_SUFFIXES
            or len(labels[-1]) < 2
            or any(
                not label
                or len(label) > 63
                or label.startswith("-")
                or label.endswith("-")
                or not re.fullmatch(r"[a-z0-9-]+", label)
                for label in labels
            )
        ):
            raise FileValidationError("A valid public HTTPS URL is required")

    authority = normalized_host if port is None else f"{normalized_host}:{port}"
    return urlunsplit(("https", authority, parts.path, parts.query, ""))


def validate_upload_filename(
    filename: str | None,
    *,
    allowed_extensions: set[str] | frozenset[str] | None = None,
) -> tuple[str, str]:
    """Return a safe basename and supported extension for response metadata."""
    if (
        not filename
        or len(filename) > 255
        or filename in {".", ".."}
        or any(character in filename for character in ("/", "\\", ":"))
        or any(ord(character) < 32 or ord(character) == 127 for character in filename)
        or filename.endswith((".", " "))
    ):
        raise FileValidationError("The uploaded filename is invalid")

    basename, separator, suffix = filename.rpartition(".")
    extension = f".{suffix.casefold()}" if separator else ""
    supported = (
        allowed_extensions
        if allowed_extensions is not None
        else set(_SUPPORTED_MEDIA_TYPES)
    )
    if not basename or "." in basename or extension not in supported:
        raise FileValidationError("The uploaded file type is not supported")
    return filename, extension


def private_storage_root(configured_dir: str | None, *, create: bool = True) -> Path:
    """Create/check an absolute private directory outside the repository."""
    if configured_dir is None:
        raise PrivateStorageUnavailable

    target = Path(configured_dir)
    if not target.is_absolute():
        raise PrivateStorageUnavailable

    try:
        repository_root = Path(__file__).resolve().parents[3]
        if _is_within(target.resolve(strict=False), repository_root):
            raise PrivateStorageUnavailable
        _create_directories_without_reparse_points(target, create=create)
        root = target.resolve(strict=True)
        if _is_within(root, repository_root):
            raise PrivateStorageUnavailable
        _reject_reparse_points(root)
        if os.name != "nt" and stat.S_IMODE(root.stat().st_mode) & 0o077:
            raise PrivateStorageUnavailable
        return root
    except PrivateStorageUnavailable:
        raise
    except (OSError, RuntimeError, ValueError):
        raise PrivateStorageUnavailable from None


def stage_upload(
    source: BinaryIO,
    *,
    filename: str | None,
    content_type: str | None,
    configured_dir: str | None,
    max_file_size_bytes: int = MAX_FILE_SIZE_BYTES,
    allowed_extensions: set[str] | frozenset[str] | None = None,
) -> StagedUpload:
    """Bounded-stream, validate, and stage one untrusted file in private storage."""
    safe_filename, extension = validate_upload_filename(
        filename, allowed_extensions=allowed_extensions
    )
    media_type = _SUPPORTED_MEDIA_TYPES[extension]
    declared_type = (content_type or "").split(";", 1)[0].strip().casefold()
    if declared_type not in {"", "application/octet-stream", *media_type}:
        raise FileValidationError(
            "The uploaded content type does not match its file type"
        )

    root = private_storage_root(configured_dir)
    temp_path: Path | None = None
    try:
        file_descriptor, temp_name = tempfile.mkstemp(
            prefix=".gradtrack-upload-", suffix=".tmp", dir=root
        )
        temp_path = Path(temp_name)
        size = 0
        with os.fdopen(file_descriptor, "wb") as destination:
            source.seek(0)
            while True:
                chunk = source.read(_CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_file_size_bytes:
                    limit_mb = max_file_size_bytes // (1024 * 1024)
                    raise FileValidationError(
                        f"The uploaded file exceeds the {limit_mb} MiB limit",
                        status_code=413,
                    )
                destination.write(chunk)
            destination.flush()
            os.fsync(destination.fileno())

        if size == 0:
            raise FileValidationError("The uploaded file must not be empty")

        _validate_file_contents(temp_path, extension)
        canonical_type = next(iter(sorted(media_type)))
        if extension == ".zip":
            canonical_type = "application/zip"
        return StagedUpload(
            root=root,
            temp_path=temp_path,
            storage_key=uuid4().hex,
            original_filename=safe_filename,
            file_size_bytes=size,
            media_type=canonical_type,
        )
    except FileValidationError:
        _unlink_quietly(temp_path)
        raise
    except PrivateStorageUnavailable:
        _unlink_quietly(temp_path)
        raise
    except OSError as error:
        _unlink_quietly(temp_path)
        raise PrivateStorageUnavailable from error


def delete_stored_file(configured_dir: str | None, storage_key: str | None) -> None:
    """Remove an opaque stored key from private storage quietly."""
    if not storage_key or not re.fullmatch(r"[0-9a-f]{32}", storage_key):
        return
    try:
        root = private_storage_root(configured_dir, create=False)
        path = _storage_path(root, storage_key)
        _reject_reparse_points(path)
        path.unlink(missing_ok=True)
    except Exception:
        pass


def open_stored_file(configured_dir: str | None, storage_key: str) -> BinaryIO:
    """Open an opaque stored key without following a symlink or exposing paths."""
    if not re.fullmatch(r"[0-9a-f]{32}", storage_key):
        raise PrivateStorageUnavailable
    root = private_storage_root(configured_dir, create=False)
    path = _storage_path(root, storage_key)
    try:
        _reject_reparse_points(path)
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise PrivateStorageUnavailable
        return os.fdopen(descriptor, "rb")
    except PrivateStorageUnavailable:
        raise
    except OSError as error:
        raise PrivateStorageUnavailable from error


def _validate_file_contents(path: Path, extension: str) -> None:
    with path.open("rb") as source:
        header = source.read(8)
        if extension == ".pdf":
            valid = header.startswith(b"%PDF-")
        elif extension == ".png":
            valid = header == b"\x89PNG\r\n\x1a\n"
        elif extension in {".jpg", ".jpeg"}:
            valid = header.startswith(b"\xff\xd8\xff")
        elif extension in {".zip", ".docx", ".pptx"}:
            valid = header.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))
        else:
            valid = True
        if not valid:
            raise FileValidationError("The uploaded file content is invalid")

        if extension == ".txt":
            _validate_utf8_text(path)
        elif extension in {".zip", ".docx", ".pptx"}:
            _validate_archive(path, extension)


def _validate_utf8_text(path: Path) -> None:
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    try:
        with path.open("rb") as source:
            while chunk := source.read(_CHUNK_SIZE):
                if b"\x00" in chunk:
                    raise FileValidationError("The uploaded text file is invalid")
                decoder.decode(chunk)
            decoder.decode(b"", final=True)
    except UnicodeDecodeError:
        raise FileValidationError("The uploaded text file must be UTF-8") from None


def _validate_archive(path: Path, extension: str) -> None:
    try:
        with ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_ENTRIES:
                raise FileValidationError("The uploaded archive has too many entries")
            if any(entry.flag_bits & 0x1 for entry in entries):
                raise FileValidationError("Encrypted archives are not accepted")
            if (
                sum(entry.file_size for entry in entries)
                > MAX_ARCHIVE_UNCOMPRESSED_BYTES
            ):
                raise FileValidationError(
                    "The uploaded archive expands beyond the limit"
                )

            if extension == ".docx":
                required = {"[Content_Types].xml", "word/document.xml"}
            elif extension == ".pptx":
                required = {"[Content_Types].xml", "ppt/presentation.xml"}
            else:
                required = set()
            names = [entry.filename for entry in entries]
            if any(names.count(name) != 1 for name in required):
                raise FileValidationError("The Office document package is invalid")
    except FileValidationError:
        raise
    except (BadZipFile, EOFError, LargeZipFile, OSError, RuntimeError, ValueError):
        raise FileValidationError("The uploaded archive is invalid") from None


def _storage_path(root: Path, storage_key: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", storage_key):
        raise PrivateStorageUnavailable
    path = root / storage_key
    try:
        if not path.absolute().is_relative_to(root):
            raise PrivateStorageUnavailable
    except (OSError, ValueError):
        raise PrivateStorageUnavailable from None
    return path


def _create_directories_without_reparse_points(target: Path, *, create: bool) -> None:
    current = Path(target.anchor)
    _reject_reparse_points(current)
    for component in target.parts[1:]:
        current /= component
        try:
            current.lstat()
        except FileNotFoundError:
            if not create:
                raise PrivateStorageUnavailable from None
            try:
                current.mkdir(mode=0o700)
            except FileExistsError:
                pass
        _reject_reparse_points(current)
        if not current.is_dir():
            raise PrivateStorageUnavailable


def _reject_reparse_points(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(metadata.st_mode):
        raise PrivateStorageUnavailable
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if getattr(metadata, "st_file_attributes", 0) & reparse_flag:
        raise PrivateStorageUnavailable


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _unlink_quietly(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
