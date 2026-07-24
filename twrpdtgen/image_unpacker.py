#
# Copyright (C) 2022 The Android Open Source Project
#
# SPDX-License-Identifier: Apache-2.0
#
"""Pure Python cross-platform Android boot/recovery image unpacker.

Provides a fallback for Windows where AIK (Android Image Kitchen) cannot run
natively. Parses boot image headers (v0-v4), extracts kernel/ramdisk/DTB/DTBO,
and decompresses and extracts ramdisk cpio archives.
"""

import gzip
import io
import lzma
import struct
from pathlib import Path
from shutil import rmtree
from tempfile import TemporaryDirectory
from typing import Optional, Tuple

from sebaubuntu_libs.libaik import AIKImageInfo
from sebaubuntu_libs.liblogging import LOGD, LOGI

# Android boot image magic bytes
ANDROID_BOOT_MAGIC = b"ANDROID!"

# AVB (Android Verified Boot) signatures
AVB_FOOTER_MAGIC = b"AVBf"
AVB_HASHTREE_MAGIC = b"AVBh"
AVB_METADATA_MAGIC = b"AVB0"

# DTBO (Device Tree Blob Overlay) magic
DTBO_MAGIC = 0xD7B7AB1E

# Compression types for ramdisk
RAMDISK_COMPRESSION_GZIP = "gzip"
RAMDISK_COMPRESSION_LZ4 = "lz4"
RAMDISK_COMPRESSION_LZMA = "lzma"
RAMDISK_COMPRESSION_XZ = "lzma"
RAMDISK_COMPRESSION_NONE = "none"

# cpio magic
CPIO_NEWC_MAGIC = b"070701"
CPIO_NEWC_MAGIC_END = b"00000000"

# Compression types for ramdisk (additional)
RAMDISK_COMPRESSION_BZIP2 = "bzip2"
RAMDISK_COMPRESSION_ZSTD = "zstd"


def _read_uint32(data: bytes, offset: int) -> int:
	"""Read a little-endian uint32 from bytes.

	Args:
		data: Byte array to read from.
		offset: Starting offset in bytes.

	Returns:
		32-bit unsigned integer value.
	"""
	return struct.unpack_from("<I", data, offset)[0]


def _round_up(value: int, alignment: int) -> int:
	"""Round up value to the next multiple of alignment.

	Args:
		value: Value to round up.
		alignment: Alignment boundary (must be power of 2).

	Returns:
		Rounded up value.
	"""
	return (value + alignment - 1) & ~(alignment - 1)


def _detect_compression(data: bytes) -> str:
	"""Detect compression type from magic bytes.

	Args:
		data: First few bytes of the compressed data.

	Returns:
		Compression type string.
	"""
	LOGD("Detecting compression type from magic bytes")
	if data[:2] == b"\x1f\x8b":
		return RAMDISK_COMPRESSION_GZIP
	if data[:4] == b"\x28\xb5\x2f\xfd":
		return RAMDISK_COMPRESSION_ZSTD
	if data[:4] == b"\x04\x22\x4d\x18":
		return RAMDISK_COMPRESSION_LZ4
	if data[:6] == b"\xfd\x37\x7a\x58\x5a\x00":
		return RAMDISK_COMPRESSION_LZMA
	if data[:3] == b"BZh":
		return RAMDISK_COMPRESSION_BZIP2
	return RAMDISK_COMPRESSION_NONE


def _decompress_ramdisk(data: bytes) -> bytes:
	"""Decompress ramdisk data based on detected compression.

	Args:
		data: Raw compressed ramdisk data.

	Returns:
		Decompressed ramdisk data.

	Raises:
		RuntimeError: If decompression fails or format is unsupported.
	"""
	compression = _detect_compression(data)
	LOGD(f"Ramdisk compression: {compression}")

	if compression == RAMDISK_COMPRESSION_GZIP:
		return gzip.decompress(data)
	elif compression == RAMDISK_COMPRESSION_LZMA:
		return lzma.decompress(data)
	elif compression == RAMDISK_COMPRESSION_BZIP2:
		import bz2
		return bz2.decompress(data)
	elif compression == RAMDISK_COMPRESSION_LZ4:
		try:
			import lz4.frame
			return lz4.frame.decompress(data)
		except ImportError:
			try:
				import lz4.block
				return lz4.block.decompress(data)
			except ImportError:
				raise RuntimeError(
					"LZ4 decompression requires the lz4 package. "
					"Install it with: pip install lz4"
				)
	elif compression == RAMDISK_COMPRESSION_ZSTD:
		try:
			import zstandard as zstd
			dctx = zstd.ZstdDecompressor()
			return dctx.decompress(data)
		except ImportError:
			try:
				import zstd as zstd_mod
				return zstd_mod.decompress(data)
			except ImportError:
				raise RuntimeError(
					"Zstd decompression requires the zstandard package. "
					"Install it with: pip install zstandard"
				)
	elif compression == RAMDISK_COMPRESSION_NONE:
		return data
	else:
		raise RuntimeError(f"Unsupported ramdisk compression: {compression}")


def _extract_cpio(data: bytes, output_dir: Path) -> None:
	"""Extract a cpio archive in newc format to a directory.

	Args:
		data: Raw cpio archive data.
		output_dir: Directory to extract files into.

	Raises:
		RuntimeError: If the cpio archive is invalid.
	"""
	offset = 0
	data_len = len(data)

	while offset < data_len:
		# Need at least 6 bytes for the magic
		if offset + 6 > data_len:
			break

		magic = data[offset:offset + 6]

		# Check for end of archive
		if magic == CPIO_NEWC_MAGIC_END:
			break

		if magic != CPIO_NEWC_MAGIC:
			# Try to find next valid header (skip padding)
			offset += 4
			continue

		# Parse newc header (110 bytes total including magic)
		if offset + 110 > data_len:
			break

		header = data[offset:offset + 110]

		# Parse fields from newc header
		ino = int(header[6:14], 16)
		mode = int(header[14:22], 16)
		uid = int(header[22:30], 16)
		gid = int(header[30:38], 16)
		nlink = int(header[38:46], 16)
		mtime = int(header[46:54], 16)
		filesize = int(header[54:62], 16)
		devmajor = int(header[62:70], 16)
		devminor = int(header[70:78], 16)
		rdevmajor = int(header[78:86], 16)
		rdevminor = int(header[86:94], 16)
		namesize = int(header[94:102], 16)
		check = int(header[102:110], 16)

		# Read filename
		name_data = data[offset + 110:offset + 110 + namesize]
		name = name_data.rstrip(b"\x00").decode("utf-8", errors="replace")

		# File data starts after header + name (total rounded up to 4-byte boundary)
		file_data_offset = _round_up(offset + 110 + namesize, 4)

		# Handle different file types
		file_type = mode & 0o170000

		if name == "." or name == "..":
			offset = _round_up(file_data_offset + filesize, 4)
			continue

		if file_type == 0o040000:  # Directory
			(output_dir / name).mkdir(parents=True, exist_ok=True)
		elif file_type == 0o100000:  # Regular file
			file_data = data[file_data_offset:file_data_offset + filesize]
			target = output_dir / name
			target.parent.mkdir(parents=True, exist_ok=True)
			target.write_bytes(file_data)
		elif file_type == 0o120000:  # Symlink
			link_data = data[file_data_offset:file_data_offset + filesize]
			link_target = link_data.rstrip(b"\x00").decode("utf-8", errors="replace")
			target = output_dir / name
			target.parent.mkdir(parents=True, exist_ok=True)
			try:
				target.symlink_to(link_target)
			except OSError:
				# On Windows, symlinks may require admin or Developer Mode.
				# Preserve symlink info via a .link sidecar file so it can
				# be reconstructed on Linux.
				target.write_text(link_target, encoding="utf-8")
				link_sidecar = output_dir / f"{name}.link"
				link_sidecar.write_text(link_target, encoding="utf-8")
		elif file_type == 0o060000:  # Block device
			pass  # Skip device nodes
		elif file_type == 0o020000:  # Character device
			pass  # Skip device nodes
		elif file_type == 0o010000:  # FIFO
			pass  # Skip FIFO nodes

		offset = _round_up(file_data_offset + filesize, 4)


class PurePythonImageUnpacker:
	"""Pure Python cross-platform boot/recovery image unpacker.

	Parses Android boot image headers and extracts kernel, ramdisk, DTB, and
	DTBO without requiring any external Linux tools.
	"""

	def __init__(self):
		"""Initialize the unpacker with a temporary directory."""
		self._tempdir = TemporaryDirectory()
		self._path = Path(self._tempdir.name)
		self._images_path = self._path / "split_img"
		self._ramdisk_path = self._path / "ramdisk"
		self._images_path.mkdir(parents=True)
		self._ramdisk_path.mkdir(parents=True)

	def unpackimg(self, image: Path) -> AIKImageInfo:
		"""Extract a boot or recovery image.

		Args:
			image: Path to the boot/recovery image file.

		Returns:
			An AIKImageInfo object with extracted file paths and metadata.

		Raises:
			RuntimeError: If the image format is invalid.
		"""
		LOGI(f"Extracting image: {image}")

		image_data = image.read_bytes()

		# Verify magic
		if image_data[:8] != ANDROID_BOOT_MAGIC:
			raise RuntimeError(
				f"Invalid Android boot image: {image.name}. "
				f"Expected magic 'ANDROID!', got {image_data[:8]!r}."
			)

		# Parse header
		page_size = _read_uint32(image_data, 36)
		kernel_size = _read_uint32(image_data, 8)
		kernel_addr = _read_uint32(image_data, 12)
		ramdisk_size = _read_uint32(image_data, 16)
		ramdisk_addr = _read_uint32(image_data, 20)
		tags_addr = _read_uint32(image_data, 32)
		header_version = _read_uint32(image_data, 1024) if len(image_data) > 1028 else 0
		cmdline = image_data[48:48+512].split(b"\x00")[0].decode("utf-8", errors="replace")
		board_name = image_data[16:16+16].split(b"\x00")[0].decode("utf-8", errors="replace")

		LOGD(f"Header version: {header_version}")
		LOGD(f"Page size: {page_size}")
		LOGD(f"Kernel size: {kernel_size}")
		LOGD(f"Ramdisk size: {ramdisk_size}")
		LOGD(f"Board name: {board_name}")
		LOGD(f"Kernel cmdline: {cmdline[:80]}...")

		# Calculate offsets (all sections are page-aligned)
		kernel_offset = page_size  # First page is the header
		ramdisk_offset = kernel_offset + _round_up(kernel_size, page_size)

		# Extract kernel
		kernel_path = None
		if kernel_size > 0:
			kernel_data = image_data[kernel_offset:kernel_offset + kernel_size]
			if kernel_data:
				kernel_path = self._images_path / f"{image.name}-kernel"
				kernel_path.write_bytes(kernel_data)

		# Extract ramdisk
		ramdisk_data = b""
		if ramdisk_size > 0:
			ramdisk_data = image_data[ramdisk_offset:ramdisk_offset + ramdisk_size]

		# Detect ramdisk compression
		ramdisk_compression = None
		if ramdisk_data:
			ramdisk_compression = _detect_compression(ramdisk_data)

		# Parse header v1+ additional fields
		dtb_offset_val = None
		dtb_size = 0
		recovery_dtbo_offset = None
		recovery_dtbo_size = 0
		dtb_offset_addr = None

		if header_version >= 1:
			# DTB field (header v1)
			dtb_offset_in_header = 1632 if header_version < 3 else 1632
			if len(image_data) > dtb_offset_in_header + 8:
				dtb_size = _read_uint32(image_data, dtb_offset_in_header)
				dtb_offset_addr = _read_uint32(image_data, dtb_offset_in_header + 4)

		if header_version >= 2:
			# Recovery DTBO (header v2)
			recovery_dtbo_offset_in_header = 1664
			if len(image_data) > recovery_dtbo_offset_in_header + 8:
				recovery_dtbo_size = _read_uint32(image_data, recovery_dtbo_offset_in_header)

		# Calculate DTB/DTBO offsets in the image
		dtb_image_offset = ramdisk_offset + _round_up(ramdisk_size, page_size)
		recovery_dtbo_image_offset = dtb_image_offset

		if dtb_size > 0:
			# DTB comes after ramdisk
			dtb_data = image_data[dtb_image_offset:dtb_image_offset + dtb_size]
			recovery_dtbo_image_offset = dtb_image_offset + _round_up(dtb_size, page_size)
		else:
			dtb_data = b""

		if recovery_dtbo_size > 0:
			# Recovery DTBO comes after DTB
			# Find the actual offset based on header
			offset_in_header = 1640 if header_version >= 3 else 1664
			if len(image_data) > offset_in_header + 4:
				recovery_dtbo_offset_val = _read_uint32(image_data, offset_in_header)
				recovery_dtbo_image_offset = recovery_dtbo_offset_val
			recovery_dtbo_data = image_data[recovery_dtbo_image_offset:recovery_dtbo_image_offset + recovery_dtbo_size]
		else:
			recovery_dtbo_data = b""

		# Check for header v3+ vendor_boot style
		if header_version >= 3:
			# For header v3, DTB and vendor_boot structure differ
			# Try to find DTBO in the standard location
			if not recovery_dtbo_data and ramdisk_size > 0:
				candidate_offset = ramdisk_offset + _round_up(ramdisk_size, page_size)
				if candidate_offset < len(image_data):
					# Check if there's a valid DTBO header (0xD7B7AB1E)
					if len(image_data) > candidate_offset + 4:
						dtbo_magic = _read_uint32(image_data, candidate_offset)
						if dtbo_magic == DTBO_MAGIC:
							# DTBO v1 header: magic(4) + total_size(4) + header_size(4) + dt_entry_size(4) + dt_entry_count(4) + dt_entries_offset(4) + page_size(4) + version(4)
							if len(image_data) > candidate_offset + 32:
								total_dtbo_size = _read_uint32(image_data, candidate_offset + 4)
								if total_dtbo_size > 0:
									recovery_dtbo_data = image_data[candidate_offset:candidate_offset + total_dtbo_size]

		# Write extracted files
		dtb_path = None
		if dtb_data:
			dtb_path = self._images_path / f"{image.name}-dtb"
			dtb_path.write_bytes(dtb_data)

		dtbo_path = None
		if recovery_dtbo_data:
			dtbo_path = self._images_path / f"{image.name}-dtbo"
			dtbo_path.write_bytes(recovery_dtbo_data)

		# Extract ramdisk
		if ramdisk_data:
			LOGD("Extracting ramdisk...")
			LOGD(f"Ramdisk data size: {len(ramdisk_data)} bytes")
			LOGD(f"Ramdisk compression: {ramdisk_compression or 'unknown'}")
			try:
				decompressed = _decompress_ramdisk(ramdisk_data)
				LOGD(f"Ramdisk decompressed to {len(decompressed)} bytes")
				_extract_cpio(decompressed, self._ramdisk_path)
				LOGD(f"Ramdisk extracted to {self._ramdisk_path}")
			except Exception as e:
				LOGD(f"Ramdisk extraction failed: {e}")
				# Continue without ramdisk - some images may have issues
				pass

		# Determine sigtype (simplified detection)
		sigtype = "unknown"
		# Check for AVB footer at the end of the image
		if len(image_data) >= 64:
			avb_footer = image_data[-64:]
			if avb_footer[:4] == AVB_FOOTER_MAGIC:
				sigtype = "AVBv2"
				LOGD("AVBv2 signature detected (footer magic)")
			elif avb_footer[:4] == AVB_HASHTREE_MAGIC:
				sigtype = "AVBv2"
				LOGD("AVBv2 signature detected (hashtree magic)")
			elif avb_footer[:4] == AVB_METADATA_MAGIC:
				sigtype = "AVBv2"
				LOGD("AVBv2 signature detected (metadata magic)")

		# Check for AVB hashtree in boot image (common on A/B devices)
		if sigtype == "unknown" and len(image_data) >= 4:
			# AVB hashtree is typically appended after the boot image
			# Check the last 64 bytes for AVB markers
			for check_offset in [64, 128, 256]:
				if len(image_data) >= check_offset:
					marker = image_data[-check_offset:][:4]
					if marker in (AVB_FOOTER_MAGIC, AVB_HASHTREE_MAGIC, AVB_METADATA_MAGIC):
						sigtype = "AVBv2"
						LOGD(f"AVBv2 signature detected at offset -{check_offset}")
						break

		# Build origsize string (total image size)
		origsize = str(len(image_data))

		# Parse os_version from header (bytes 52-58)
		os_version = ""
		if len(image_data) > 58:
			os_ver_raw = image_data[52:58]
			os_version = os_ver_raw.rstrip(b"\x00").decode("utf-8", errors="replace")

		# Convert numeric addresses to hex strings for compatibility
		def addr_to_hex(addr):
			return hex(addr) if addr else None

		return AIKImageInfo(
			base_address=addr_to_hex(kernel_addr),
			board_name=board_name or None,
			cmdline=cmdline or None,
			dt=None,  # DT is usually embedded in the kernel or separate
			dtb=dtb_path,
			dtb_offset=addr_to_hex(dtb_offset_addr),
			dtbo=dtbo_path,
			header_version=str(header_version),
			image_type="boot",
			kernel=kernel_path,
			kernel_offset=addr_to_hex(kernel_addr),
			origsize=origsize,
			os_version=os_version or None,
			pagesize=str(page_size),
			ramdisk=self._ramdisk_path if any(self._ramdisk_path.iterdir()) else None,
			ramdisk_compression=ramdisk_compression,
			ramdisk_offset=addr_to_hex(ramdisk_addr),
			sigtype=sigtype,
			tags_offset=addr_to_hex(tags_addr),
		)

	def cleanup(self) -> None:
		"""Clean up temporary directory and extracted files."""
		self._tempdir.cleanup()

	def __enter__(self):
		"""Context manager entry."""
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		"""Context manager exit with cleanup."""
		self.cleanup()
		return False
		"""Clean up temporary files."""
		try:
			rmtree(self._path, ignore_errors=True)
		except Exception:
			pass
