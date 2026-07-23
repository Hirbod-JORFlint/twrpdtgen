"""Tests for the pure Python image unpacker."""

import gzip
import struct
import tempfile
from pathlib import Path

import pytest

from twrpdtgen.image_unpacker import (
    ANDROID_BOOT_MAGIC,
    CPIO_NEWC_MAGIC,
    CPIO_NEWC_MAGIC_END,
    _detect_compression,
    _decompress_ramdisk,
    _extract_cpio,
    _read_uint32,
    _round_up,
    PurePythonImageUnpacker,
)


class TestHelpers:
    def test_read_uint32(self):
        data = struct.pack("<I", 0x12345678)
        assert _read_uint32(data, 0) == 0x12345678

    def test_read_uint32_offset(self):
        data = b"\x00\x00" + struct.pack("<I", 42)
        assert _read_uint32(data, 2) == 42

    def test_round_up(self):
        assert _round_up(0, 4) == 0
        assert _round_up(1, 4) == 4
        assert _round_up(4, 4) == 4
        assert _round_up(5, 4) == 8
        assert _round_up(1023, 1024) == 1024

    def test_detect_compression_gzip(self):
        assert _detect_compression(b"\x1f\x8b\x08\x00") == "gzip"

    def test_detect_compression_lz4(self):
        assert _detect_compression(b"\x28\xb5\x2f\xfd") == "lz4"

    def test_detect_compression_lzma(self):
        assert _detect_compression(b"\xfd\x37\x7a\x58\x5a\x00") == "lzma"

    def test_detect_compression_bzip2_as_lzma(self):
        assert _detect_compression(b"BZh") == "lzma"

    def test_detect_compression_none(self):
        assert _detect_compression(b"\x00\x00\x00\x00") == "none"

    def test_decompress_ramdisk_gzip(self):
        original = b"hello world test data"
        compressed = gzip.compress(original)
        assert _decompress_ramdisk(compressed) == original

    def test_decompress_ramdisk_none(self):
        data = b"raw data"
        assert _decompress_ramdisk(data) == data


class TestCpioExtraction:
    def _make_cpio_entry(self, name: bytes, data: bytes, mode: int = 0o100644) -> bytes:
        """Build a minimal newc cpio entry.

        All fields in the newc format are hex-encoded.
        """
        name_padded = name + b"\x00"
        namesize = len(name_padded)
        filesize = len(data)

        header = b"070701"
        header += b"0" * 8   # ino
        header += format(mode, "08x").encode()
        header += b"0" * 8   # uid
        header += b"0" * 8   # gid
        header += b"0" * 8   # nlink
        header += b"0" * 8   # mtime
        header += format(filesize, "08x").encode()
        header += b"0" * 8   # devmajor
        header += b"0" * 8   # devminor
        header += b"0" * 8   # rdevmajor
        header += b"0" * 8   # rdevminor
        header += format(namesize, "08x").encode()
        header += b"0" * 8   # check

        # Pad header to 110 bytes
        assert len(header) == 110, f"Header is {len(header)} bytes, expected 110"

        entry = header + name_padded
        # Align to 4 bytes
        while len(entry) % 4 != 0:
            entry += b"\x00"
        entry += data
        # Align file data to 4 bytes
        while len(entry) % 4 != 0:
            entry += b"\x00"
        return entry

    def _make_cpio_archive(self, entries: list) -> bytes:
        """Build a cpio archive from entries, with TRAILER!!! end marker."""
        archive = b""
        for entry in entries:
            archive += entry
        # End marker
        trailer = self._make_cpio_entry(b"TRAILER!!!", b"")
        archive += trailer
        return archive

    def test_extract_regular_file(self):
        content = b"test file content"
        entry = self._make_cpio_entry(b"test.txt", content)
        archive = self._make_cpio_archive([entry])

        with tempfile.TemporaryDirectory() as tmpdir:
            _extract_cpio(archive, Path(tmpdir))
            assert (Path(tmpdir) / "test.txt").read_bytes() == content

    def test_extract_directory(self):
        entry = self._make_cpio_entry(b"mydir", b"", mode=0o040755)
        archive = self._make_cpio_archive([entry])

        with tempfile.TemporaryDirectory() as tmpdir:
            _extract_cpio(archive, Path(tmpdir))
            assert (Path(tmpdir) / "mydir").is_dir()

    def test_extract_nested_file(self):
        dir_entry = self._make_cpio_entry(b"subdir", b"", mode=0o040755)
        file_entry = self._make_cpio_entry(b"subdir/file.txt", b"nested")
        archive = self._make_cpio_archive([dir_entry, file_entry])

        with tempfile.TemporaryDirectory() as tmpdir:
            _extract_cpio(archive, Path(tmpdir))
            assert (Path(tmpdir) / "subdir" / "file.txt").read_bytes() == b"nested"

    def test_extract_symlink(self):
        link_entry = self._make_cpio_entry(
            b"link", b"target.txt", mode=0o120777
        )
        file_entry = self._make_cpio_entry(b"target.txt", b"hello")
        archive = self._make_cpio_archive([link_entry, file_entry])

        with tempfile.TemporaryDirectory() as tmpdir:
            _extract_cpio(archive, Path(tmpdir))
            target = Path(tmpdir) / "link"
            # On systems that support symlinks, it should be a symlink.
            # On Windows it may be a regular file or a symlink depending
            # on Developer Mode. Either way, the file should exist.
            assert target.exists()

    def test_empty_archive(self):
        trailer = self._make_cpio_entry(b"TRAILER!!!", b"")
        with tempfile.TemporaryDirectory() as tmpdir:
            _extract_cpio(trailer, Path(tmpdir))
            # Should not crash, only TRAILER should be skipped


class TestPurePythonImageUnpacker:
    @staticmethod
    def _make_cpio_with_file(name: bytes, content: bytes) -> bytes:
        """Create a minimal valid cpio archive containing one file."""
        name_padded = name + b"\x00"
        namesize = len(name_padded)
        filesize = len(content)
        mode = 0o100644

        header = b"070701"
        header += b"0" * 8
        header += format(mode, "08x").encode()
        header += b"0" * 8 * 4  # uid, gid, nlink, mtime
        header += format(filesize, "08x").encode()
        header += b"0" * 8 * 4  # devmajor, devminor, rdevmajor, rdevminor
        header += format(namesize, "08x").encode()
        header += b"0" * 8  # check

        entry = header + name_padded
        while len(entry) % 4 != 0:
            entry += b"\x00"
        entry += content
        while len(entry) % 4 != 0:
            entry += b"\x00"

        # End marker
        trailer_name = b"TRAILER!!!\x00"
        trailer_namesize = len(trailer_name)
        trailer_header = b"070701"
        trailer_header += b"0" * 8
        trailer_header += format(0o100644, "08x").encode()
        trailer_header += b"0" * 8 * 4
        trailer_header += format(0, "08x").encode()
        trailer_header += b"0" * 8 * 4
        trailer_header += format(trailer_namesize, "08x").encode()
        trailer_header += b"0" * 8

        trailer = trailer_header + trailer_name
        while len(trailer) % 4 != 0:
            trailer += b"\x00"

        return entry + trailer

    def _make_boot_image(
        self,
        ramdisk_data: bytes = b"",
        page_size: int = 2048,
    ) -> bytes:
        """Build a minimal Android boot image v0 with gzip-compressed ramdisk."""
        kernel_size = 1024
        kernel_data = b"\x00" * kernel_size
        compressed_ramdisk = gzip.compress(ramdisk_data) if ramdisk_data else b""

        # Header (first page)
        header = bytearray(page_size)
        # Magic at offset 0
        header[0:8] = ANDROID_BOOT_MAGIC
        # kernel_size at offset 8
        struct.pack_into("<I", header, 8, kernel_size)
        # kernel_addr at offset 12
        struct.pack_into("<I", header, 12, 0x80008000)
        # ramdisk_size at offset 16
        struct.pack_into("<I", header, 16, len(compressed_ramdisk))
        # ramdisk_addr at offset 20
        struct.pack_into("<I", header, 20, 0x81000000)
        # tags_addr at offset 32
        struct.pack_into("<I", header, 32, 0x80000100)
        # page_size at offset 36
        struct.pack_into("<I", header, 36, page_size)

        image = bytes(header)

        # Kernel (page-aligned)
        kernel_page = bytearray(page_size)
        kernel_page[:kernel_size] = kernel_data
        image += bytes(kernel_page)

        # Ramdisk (page-aligned)
        if compressed_ramdisk:
            rd_page = bytearray(_round_up(len(compressed_ramdisk), page_size))
            rd_page[:len(compressed_ramdisk)] = compressed_ramdisk
            image += bytes(rd_page)

        return image

    def test_unpack_valid_image_with_ramdisk(self):
        cpio_content = self._make_cpio_with_file(b"test.txt", b"hello")
        image_data = self._make_boot_image(ramdisk_data=cpio_content)

        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "boot.img"
            image_path.write_bytes(image_data)

            unpacker = PurePythonImageUnpacker()
            try:
                info = unpacker.unpackimg(image_path)
                assert info.header_version == "0"
                assert info.pagesize == "2048"
                assert info.kernel is not None
                assert info.kernel.exists()
                assert info.ramdisk is not None
            finally:
                unpacker.cleanup()

    def test_unpack_valid_image_without_ramdisk(self):
        image_data = self._make_boot_image(ramdisk_data=b"")

        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "boot.img"
            image_path.write_bytes(image_data)

            unpacker = PurePythonImageUnpacker()
            try:
                info = unpacker.unpackimg(image_path)
                assert info.header_version == "0"
                assert info.kernel is not None
            finally:
                unpacker.cleanup()

    def test_unpack_invalid_magic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "bad.img"
            image_path.write_bytes(b"NOT_ANDROID_MAGIC")

            unpacker = PurePythonImageUnpacker()
            try:
                with pytest.raises(RuntimeError, match="Invalid Android boot image"):
                    unpacker.unpackimg(image_path)
            finally:
                unpacker.cleanup()

    def test_cleanup_removes_temp_dir(self):
        unpacker = PurePythonImageUnpacker()
        temp_path = unpacker._path
        assert temp_path.exists()
        unpacker.cleanup()
        assert not temp_path.exists()
