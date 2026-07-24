#
# Copyright (C) 2022 The Android Open Source Project
#
# SPDX-License-Identifier: Apache-2.0
#

# Standard library
from datetime import datetime
from os import chmod
from pathlib import Path
from platform import system
from shutil import copyfile, rmtree
from stat import S_IRWXU, S_IRGRP, S_IROTH
from typing import List, Optional, Dict

# Third-party
from git import Repo
from sebaubuntu_libs.libandroid.device_info import DeviceInfo
from sebaubuntu_libs.libandroid.fstab import Fstab
from sebaubuntu_libs.libandroid.props import BuildProp
from sebaubuntu_libs.liblogging import LOGD, LOGI, LOGW

# Local
from twrpdtgen import __version__ as version
from twrpdtgen.templates import render_template

# Platform detection for image unpacking
_IS_WINDOWS = system() == "Windows"

if not _IS_WINDOWS:
	from sebaubuntu_libs.libaik import AIKManager
else:
	from twrpdtgen.image_unpacker import PurePythonImageUnpacker

BUILDPROP_LOCATIONS = [
	Path() / "default.prop",
	Path() / "prop.default",
]
BUILDPROP_LOCATIONS += [
	Path() / d / "build.prop"
	for d in ["system", "vendor"]
]
BUILDPROP_LOCATIONS += [
	Path() / d / "etc" / "build.prop"
	for d in ["system", "vendor"]
]

FSTAB_LOCATIONS = [
	Path() / "etc" / "recovery.fstab",
]
FSTAB_LOCATIONS += [
	Path() / d / "etc" / "recovery.fstab"
	for d in ["system", "vendor"]
]
FSTAB_LOCATIONS += [
	Path() / "fstab",
	Path() / "etc" / "fstab",
]
FSTAB_LOCATIONS += [
	Path() / d / "etc" / "fstab"
	for d in ["system", "vendor"]
]

INIT_RC_LOCATIONS = [
	Path(),
]
INIT_RC_LOCATIONS += [
	Path() / d / "etc" / "init"
	for d in ["system", "vendor"]
]

MEDIATEK_PLATFORMS = ("mt", "mtk")

# Samsung is known for using Download mode instead of bootloader
SAMSUNG_BRANDS = ("samsung",)

# Qualcomm platforms (for future use)
QUALCOMM_PLATFORMS = ("msm", "sdm", "sm", "qcom")

# Known encryption property values
ENCRYPTION_STATES = ("encrypted", "unencrypted")
ENCRYPTION_FILE_TYPE = "file"
ENCRYPTION_FDE_FLAG = "ro.vold.forceencryption"
ENCRYPTION_FBE_PROPS = (
	"ro.crypto.state",
	"ro.crypto.type",
	"ro.vold.forceencryption",
)

# Mount points that indicate emulated storage (from guide1: RECOVERY_SDCARD_ON_DATA)
EMULATED_STORAGE_MOUNT_POINTS = ("/sdcard", "/internal_sd", "/internal_sdcard", "/emmc")
# Mount points that indicate an external/removable SD card
SDCARD_MOUNT_POINTS = ("/sdcard", "/external_sd", "/usb-otg")

# Partition display names for TWRP fstab (from guide1: display= flag)
# Includes all known Qualcomm, MediaTek, Samsung, and Xiaomi partitions
FSTAB_PARTITION_DISPLAY_NAMES = {
	# User-facing system partitions
	"/": "System",
	"/system": "System",
	"/system_root": "System Root",
	"/vendor": "Vendor",
	"/product": "Product",
	"/system_ext": "System Extended",
	"/odm": "ODM",
	"/cache": "Cache",
	"/data": "Data",
	"/cust": "Cust",
	"/preload": "Preload",
	"/oeminfo": "OEMinfo",
	"/splash2": "Splash2",
	# Internal/external storage
	"/sdcard": "Internal Storage",
	"/internal_sd": "Internal SD",
	"/internal_sdcard": "Internal SD Card",
	"/emmc": "eMMC Storage",
	"/external_sd": "Micro SDcard",
	"/usb-otg": "USB-OTG",
	# Modem/Radio
	"/modem": "Modem",
	"/modemst1": "Modem ST1",
	"/modemst2": "Modem ST2",
	"/mdm": "Modem",
	"/fsg": "FSG",
	"/fsc": "FSC",
	"/mcfg": "MCFG",
	"/radio": "Radio",
	"/bluetooth": "Bluetooth",
	"/wifi": "WiFi",
	# DSP/Audio
	"/dsp": "DSP",
	"/dspbak": "DSP Backup",
	"/adsp": "ADSP",
	"/adspbak": "ADSP Backup",
	"/cdnsp": "CDSP",
	"/cdnspbak": "CDSP Backup",
	# Qualcomm Boot
	"/aboot": "Android Bootloader",
	"/abootbak": "Android Bootloader Backup",
	"/sbl1": "SBL1",
	"/sbl1bak": "SBL1 Backup",
	"/rpm": "RPM",
	"/rpmbak": "RPM Backup",
	"/tz": "TrustZone",
	"/tzbak": "TrustZone Backup",
	# Qualcomm Display
	"/splash": "Splash Screen",
	"/dtbo": "DTBO",
	"/dtbobak": "DTBO Backup",
	# Security/TrustZone
	"/cmnlib": "CMN Library",
	"/cmnlibbak": "CMN Library Backup",
	"/cmnlib64": "CMN Library 64-bit",
	"/cmnlib64bak": "CMN Library 64-bit Backup",
	"/keymaster": "Keymaster",
	"/keymasterbak": "Keymaster Backup",
	"/devcfg": "Device Config",
	"/devcfgbak": "Device Config Backup",
	"/devinfo": "Device Info",
	"/keystore": "Keystore",
	"/persist": "Persist",
	"/persistbak": "Persist Backup",
	"/sec": "SEC",
	"/dpo": "DPO",
	"/apdp": "APDP",
	"/msadp": "MSADP",
	"/mdtp": "MDTP",
	"/mdtpbak": "MDTP Backup",
	# Verified Boot
	"/vbmeta": "Verified Boot Meta",
	"/vbmetabak": "Verified Boot Meta Backup",
	"/vbmeta_system": "VBMeta System",
	"/vbmeta_vendor": "VBMeta Vendor",
	"/vbmeta_boot": "VBMeta Boot",
	# EFS (Samsung/Qualcomm)
	"/efs": "EFS",
	"/efs1": "EFS",
	"/efs2": "EFS 2",
	"/efs3": "EFS 3",
	"/pds": "PDS",
	"/fsg": "FSG",
	# Debug/Logging
	"/logdump": "Log Dump",
	"/minidump": "Mini Dump",
	"/exaid": "EXAID",
	"/misc": "Misc",
	"/dip": "DIP",
	"/gsort": "GSort",
	"/limits": "Limits",
	"/config": "Config",
	"/syscfg": "SysConfig",
	"/mota": "MOTA",
	"/ssd": "SSD",
	# Qualcomm bootloader/debug
	"/bk1": "Backup 1",
	"/bk2": "Backup 2",
	"/bk3": "Backup 3",
	"/bk4": "Backup 4",
	"/DDR": "DDR",
	# GPU/graphics
	"/gpu": "GPU",
	"/pvr": "PowerVR",
	# Other partitions
	"/boot": "Boot",
	"/recovery": "Recovery",
	"/metadata": "Metadata",
	"/super": "Super",
	"/userdata": "Userdata",
}

# Partitions that should be backed up by default (from guide1: backup= flag)
# Only user-facing partitions that users would want to restore
FSTAB_BACKUP_PARTITIONS = {
	"/system", "/system_root", "/vendor", "/product", "/system_ext", "/odm",
	"/cache", "/data",
	"/efs", "/efs1", "/efs2", "/efs3", "/pds",
	"/preload", "/cust", "/oeminfo",
	"/modem", "/radio", "/bluetooth", "/wifi",
	"/boot", "/recovery",
}

# Removable storage partitions (from guide1: removable + storage + wipeingui)
FSTAB_REMOVABLE_STORAGE = ("/external_sd", "/usb-otg")

# Internal storage partitions (from guide1: storage flag)
FSTAB_INTERNAL_STORAGE = ("/sdcard", "/internal_sd", "/internal_sdcard", "/emmc")

# Partitions that should be wiped during factory reset (from guide1: wipeduringfactoryreset)
FSTAB_FACTORY_RESET_PARTITIONS = ("/data", "/cache")

# Settings storage partition (from guide1: settingsstorage - only one should have this)
FSTAB_SETTINGS_STORAGE = ("/data",)


def _generate_twrp_fstab(fstab: Fstab, has_encryption: bool = False) -> str:
	"""Generate an enhanced TWRP recovery.fstab with proper flags from guide1.

	Enhances the basic fstab output with TWRP-specific flags:
	- display= : Human-readable name for the GUI (guide1: display=)
	- backup=1 : Whether the partition can be backed up (guide1: backup=)
	- storage  : Whether the partition can be used as storage (guide1: storage)
	- removable : Whether the partition may not always be present (guide1: removable)
	- wipeingui : Whether the partition shows in advanced wipe menu (guide1: wipeingui)
	- wipeduringfactoryreset : Partition wiped during factory reset (guide1: wipeduringfactoryreset)
	- settingsstorage : Partition used for TWRP settings (guide1: settingsstorage)
	- length=  : Reserved space for encryption key (guide1: length=)

	Args:
		fstab: A Fstab object with parsed fstab entries.
		has_encryption: Whether the device supports encryption (affects length= flag).

	Returns:
		A formatted fstab string with TWRP flags.
	"""
	LOGD(f"Generating TWRP fstab with {len(fstab.entries)} entries, encryption={has_encryption}")
	lines = []

	# Calculate column widths for alignment
	mount_point_width = max(len(e.mount_point) for e in fstab.entries) + 2
	fs_type_width = max(len(e.fs_type) for e in fstab.entries) + 2
	src_width = max(len(e.src) for e in fstab.entries) + 2

	for entry in fstab.entries:
		# Build TWRP flags list
		twrp_flags = []

		# Add display name
		display_name = FSTAB_PARTITION_DISPLAY_NAMES.get(
			entry.mount_point,
			entry.mount_point.lstrip("/").replace("_", " ").replace("-", " ").title()
		)
		if " " in display_name:
			twrp_flags.append(f'display="{display_name}"')
		else:
			twrp_flags.append(f"display={display_name}")

		# Add backup flag for backupable partitions
		if entry.mount_point in FSTAB_BACKUP_PARTITIONS:
			twrp_flags.append("backup=1")
			LOGD(f"Added backup flag for partition: {entry.mount_point}")

		# Add storage flag for internal storage
		if entry.mount_point in FSTAB_INTERNAL_STORAGE:
			twrp_flags.append("storage")

		# Add removable + storage + wipeingui for removable storage
		if entry.mount_point in FSTAB_REMOVABLE_STORAGE:
			twrp_flags.append("storage")
			twrp_flags.append("wipeingui")
			twrp_flags.append("removable")

		# Preserve logical and slotselect flags from the original fstab
		if entry.is_logical():
			twrp_flags.append("logical")
		if entry.is_slotselect():
			twrp_flags.append("slotselect")

		# Add length= for /data when encryption is detected (guide1: length=)
		# This reserves space at the end of /data for the decryption key
		length_flag = ""
		if entry.mount_point == "/data" and has_encryption:
			length_flag = " length=-16384"
			LOGD("Added encryption length flag for /data partition")

		# Add wipeduringfactoryreset for partitions wiped during factory reset
		# From guide1: these partitions are wiped during factory reset
		if entry.mount_point in FSTAB_FACTORY_RESET_PARTITIONS:
			twrp_flags.append("wipeduringfactoryreset")

		# Add settingsstorage flag for the settings storage partition
		# From guide1: only one partition should be set as settings storage
		if entry.mount_point in FSTAB_SETTINGS_STORAGE:
			twrp_flags.append("settingsstorage")

		# Add canbewipe flag for partitions that can be wiped
		if entry.mount_point in ["/cache", "/data", "/system", "/vendor", "/cust", "/preload"]:
			twrp_flags.append("canbewipe")

		# Add ignore flags for special partitions that shouldn't be touched
		if entry.mount_point in ["/misc", "/metadata"]:
			twrp_flags.append("ignore")

		# Pad columns for alignment
		mount_pad = " " * (mount_point_width - len(entry.mount_point))
		fs_type_pad = " " * (fs_type_width - len(entry.fs_type))
		src_pad = " " * (src_width - len(entry.src))

		flags_str = "flags=" + ";".join(twrp_flags)
		lines.append(
			f"{entry.mount_point}{mount_pad}{entry.fs_type}{fs_type_pad}"
			f"{entry.src}{src_pad}{flags_str}{length_flag}"
		)

	# End with a trailing newline
	lines.append("")
	return "\n".join(lines)


def _detect_emulated_storage(fstab: Fstab) -> bool:
	"""Detect if device uses emulated storage (SD card on /data).

	From guide1: RECOVERY_SDCARD_ON_DATA enables proper handling of
	/data/media on devices that have this folder for storage. If no
	references to /sdcard, /internal_sd, /internal_sdcard, or /emmc
	are found in the fstab, TWRP automatically assumes emulated storage.

	Args:
		fstab: A Fstab object with parsed fstab entries.

	Returns:
		True if device uses emulated storage, False otherwise.
	"""
	LOGD("Detecting emulated storage")
	for entry in fstab.entries:
		if entry.mount_point in EMULATED_STORAGE_MOUNT_POINTS:
			return True
		# Check for "media" in mount options (indicates /data/media)
		for flag in entry.mnt_flags:
			if "media" in flag.lower():
				return True
		for flag in entry.fs_flags:
			if "noemulatedsd" in flag.lower():
				return True
	return False


def _detect_has_sdcard(fstab: Fstab) -> bool:
	"""Detect if device has an external SD card slot.

	From guide1: sdcard/external_sd/usb-otg entries indicate physical
	storage is available. Checks for removable storage mount points
	like /external_sd or /usb-otg.

	Args:
		fstab: A Fstab object with parsed fstab entries.

	Returns:
		True if device has external SD card support, False otherwise.
	"""
	for entry in fstab.entries:
		if entry.mount_point in ("/external_sd", "/usb-otg"):
			return True
		if "removable" in entry.fs_flags:
			return True
	return False


def _detect_userdata_fs_type(fstab: Fstab) -> str:
	"""Detect the filesystem type of the /data partition.

	From guide1: the fstab specifies the filesystem for each partition.
	We extract the /data filesystem type instead of hardcoding it.

	Args:
		fstab: A Fstab object with parsed fstab entries.

	Returns:
		Filesystem type string (e.g., "ext4", "f2fs"). Defaults to "ext4".
	"""
	LOGD("Detecting /data filesystem type")
	for entry in fstab.entries:
		if entry.mount_point == "/data":
			fs_type = entry.fs_type.lower()
			if fs_type in ("ext4", "f2fs"):
				return fs_type
	return "ext4"  # Default fallback


def _detect_touchscreen_orientation(build_prop: BuildProp) -> Dict[str, bool]:
	"""Detect touchscreen orientation settings from build properties.

	From guide1: RECOVERY_TOUCHSCREEN_SWAP_XY, RECOVERY_TOUCHSCREEN_FLIP_X,
	RECOVERY_TOUCHSCREEN_FLIP_Y can fix touchscreen rotation issues.
	Analyzes build properties to determine if touchscreen coordinates need
	to be swapped or flipped for proper touch input handling.

	Args:
		build_prop: A BuildProp object with device properties.

	Returns:
		Dictionary with orientation settings:
		- swap_xy: Whether to swap X and Y coordinates
		- flip_x: Whether to flip X coordinates
		- flip_y: Whether to flip Y coordinates
	"""
	LOGD("Detecting touchscreen orientation")
	result = {"swap_xy": False, "flip_x": False, "flip_y": False}

	# Check ro.sf.hwrotation for screen rotation
	hwrotation = build_prop.get_prop("ro.sf.hwrotation", "")
	if hwrotation:
		try:
			rotation = int(hwrotation)
			if rotation in (90, 270):
				result["swap_xy"] = True
			if rotation == 180:
				result["flip_x"] = True
				result["flip_y"] = True
		except (ValueError, TypeError):
			pass

	# Check ro.input.devices for touchscreen rotation hints
	input_devices = build_prop.get_prop("ro.input.devices", "")
	if input_devices and "flip" in input_devices.lower():
		result["flip_x"] = True

	return result


def _is_mediatek_platform(platform: str) -> bool:
	"""Check if the platform is a MediaTek chipset.

	Args:
		platform: Platform string from device info.

	Returns:
		True if platform is MediaTek (starts with 'mt' or 'mtk'), False otherwise.
	"""
	LOGD(f"Checking if platform '{platform}' is MediaTek")
	return platform.lower().startswith(MEDIATEK_PLATFORMS)


def _is_samsung_device(brand: str) -> bool:
	"""Check if the device brand is Samsung.

	Samsung devices use Download mode instead of bootloader mode,
	which affects recovery key combinations (guide1: TW_NO_REBOOT_BOOTLOADER).

	Args:
		brand: Device brand string.

	Returns:
		True if brand is Samsung (case-insensitive), False otherwise.
	"""
	return brand.lower() in SAMSUNG_BRANDS


def _detect_tw_theme(
	screen_density: Optional[int],
	is_landscape: bool = False,
	is_watch: bool = False,
) -> str:
	"""Detect appropriate TWRP theme based on screen density and orientation.

	From guide1: TWRP supports 5 themes:
	- portrait_hdpi: for portrait devices with >= 720x1280 resolution
	- portrait_mdpi: for portrait devices with lower resolution
	- landscape_hdpi: for landscape devices with >= 1280x720 resolution
	- landscape_mdpi: for landscape devices with lower resolution
	- watch_mdpi: for round/watch devices (240x240, 280x280, 320x320)

	TWRP uses scaling to stretch any theme to fit the screen resolution.

	Args:
		screen_density: Screen density in DPI, or None if unknown.
		is_landscape: Whether the device has a landscape orientation.
		is_watch: Whether the device is a round/watch device.

	Returns:
		Theme string (e.g., "portrait_hdpi", "landscape_mdpi", "watch_mdpi").
	"""
	if is_watch:
		return "watch_mdpi"

	if screen_density is None:
		return "portrait_hdpi" if not is_landscape else "landscape_hdpi"

	# Ensure we have a numeric value for comparison
	try:
		density = int(screen_density)
	except (ValueError, TypeError):
		return "portrait_hdpi" if not is_landscape else "landscape_hdpi"

	# mdpi is ~160dpi, hdpi is ~240dpi, xhdpi is ~320dpi
	# For most modern devices (>= 720p), hdpi is appropriate
	if density >= 240:
		return "portrait_hdpi" if not is_landscape else "landscape_hdpi"

	return "portrait_mdpi" if not is_landscape else "landscape_mdpi"


def _is_qualcomm_platform(platform: str) -> bool:
	"""Check if the platform is a Qualcomm chipset.

	Args:
		platform: Platform string from device info.

	Returns:
		True if platform is Qualcomm (msm, sdm, sm, qcom), False otherwise.
	"""
	return platform.lower().startswith(QUALCOMM_PLATFORMS)


def _detect_selinux_permissive(cmdline: str) -> bool:
	"""Detect if SELinux is set to permissive mode in kernel cmdline.

	From guide1/mediatek: permissive mode is often set for MediaTek
	devices via `androidboot.selinux=permissive` in the kernel cmdline.

	Args:
		cmdline: Kernel command line string.

	Returns:
		True if androidboot.selinux=permissive is present, False otherwise.
	"""
	if not cmdline:
		return False
	return "androidboot.selinux=permissive" in cmdline


def _detect_hardware_mismatch(board_name: str, codename: str) -> bool:
	"""Detect if there's a mismatch between board name and device codename.

	From guide3 (GDB debugging): when ro.hardware doesn't match the codename,
	GDB's gdbclient will look for symbol files in the wrong directory
	(e.g., out/target/product/qcom/symbols instead of out/target/product/codename/symbols).
	A mismatch may indicate that the device tree needs special handling
	or that the device uses a different board name than expected.

	Args:
		board_name: Board name from build props.
		codename: Device codename.

	Returns:
		True if board name and codename don't match, False otherwise.
	"""
	LOGD(f"Checking hardware mismatch: board='{board_name}', codename='{codename}'")
	if not board_name or not codename:
		return False
	return board_name.lower() != codename.lower()


class DeviceTree:
	"""A class representing a TWRP device tree.

	It initializes a basic device tree structure and saves the
	location of some important files extracted from a recovery
	or boot image.
	"""
	def __init__(self, image: Path):
		"""Initialize the device tree class.

		Args:
			image: Path to the recovery or boot image.

		Raises:
			FileNotFoundError: If the image file does not exist.
			RuntimeError: If the ramdisk, fstab, or other required
			              components cannot be found in the image.
		"""
		self.image = image

		self.current_year = str(datetime.now().year)

		# Check if the image exists
		if not self.image.is_file():
			raise FileNotFoundError(
				f"Specified file doesn't exist: {image}"
			)

		# Extract the image using platform-appropriate unpacker
		if _IS_WINDOWS:
			LOGD("Using pure Python image unpacker (Windows)")
			self.aik_manager = PurePythonImageUnpacker()
		else:
			LOGD("Using AIK (Linux/macOS)")
			self.aik_manager = AIKManager()

		self.image_info = self.aik_manager.unpackimg(image)

		if not self.image_info.ramdisk:
			raise RuntimeError(
				"Ramdisk not found in image. "
				"Ensure the image is a valid recovery or boot image.\n"
				"Hint: For A/B devices, use the boot image (not recovery). "
				"The recovery ramdisk is embedded in the boot image.\n"
				"Hint: For non-A/B devices, use the recovery image from the stock ROM."
			)

		LOGD("Getting device infos...")
		self.build_prop = BuildProp()
		for build_prop_path in [
			self.image_info.ramdisk / location
			for location in BUILDPROP_LOCATIONS
		]:
			if not build_prop_path.is_file():
				continue

			self.build_prop.import_props(build_prop_path)

		self.device_info = DeviceInfo(self.build_prop)

		# Detect MediaTek platform
		self.is_mediatek = _is_mediatek_platform(self.device_info.platform)
		if self.is_mediatek:
			LOGD(f"MediaTek platform detected: {self.device_info.platform}")

		# Detect Qualcomm platform
		self.is_qualcomm = _is_qualcomm_platform(self.device_info.platform)
		if self.is_qualcomm:
			LOGD(f"Qualcomm platform detected: {self.device_info.platform}")

		# Detect Samsung device (uses Download mode instead of bootloader)
		self.is_samsung = _is_samsung_device(self.device_info.brand)
		if self.is_samsung:
			LOGD(f"Samsung device detected: {self.device_info.brand}")

		# Detect encryption support from build properties
		self.has_encryption = self._detect_encryption()

		# Detect SELinux permissive mode from kernel cmdline
		self.is_selinux_permissive = _detect_selinux_permissive(
			self.image_info.cmdline or ""
		)
		if self.is_selinux_permissive:
			LOGD("SELinux permissive mode detected in kernel cmdline")

		# Detect ro.hardware / codename mismatch (from guide3: GDB debugging)
		# When ro.hardware doesn't match codename, GDB looks for symbols
		# in the wrong directory (e.g., out/target/product/qcom/symbols
		# instead of out/target/product/<codename>/symbols)
		self.has_hardware_mismatch = _detect_hardware_mismatch(
			self.device_info.bootloader_board_name or "",
			self.device_info.codename or "",
		)
		if self.has_hardware_mismatch:
			LOGD(
				f"WARNING: ro.hardware '{self.device_info.bootloader_board_name}' "
				f"does not match codename '{self.device_info.codename}'. "
				f"This may cause GDB symbol path issues during debugging. "
				f"See guide3 for details."
			)

		# Detect TWRP theme based on screen density and device type
		# From guide1: portrait_hdpi/mdpi, landscape_hdpi/mdpi, watch_mdpi
		is_landscape = self.device_info.is_tablet if hasattr(self.device_info, 'is_tablet') else False
		is_watch = "watch" in (self.device_info.codename or "").lower()
		self.tw_theme = _detect_tw_theme(
			self.device_info.screen_density,
			is_landscape=is_landscape,
			is_watch=is_watch,
		)

		# Generate fstab
		fstab = None
		for fstab_location in [
			self.image_info.ramdisk / location
			for location in FSTAB_LOCATIONS
		]:
			if not fstab_location.is_file():
				continue

			LOGD(f"Generating fstab using {fstab_location} as reference...")
			fstab = Fstab(fstab_location)
			break

		if fstab is None:
			raise RuntimeError(
				"fstab not found in image. "
				"Ensure the recovery image contains a recovery.fstab "
				"in etc/, system/etc/, or vendor/etc/.\n"
				"Hint: Some devices use fstab in /fstab or /etc/fstab instead. "
				"The tool also searches these locations.\n"
				"Hint: For A/B devices, the fstab may be in the vendor ramdisk "
				"or in the system partition."
			)

		self.fstab = fstab

		# Analyze fstab for storage configuration (from guide1)
		self.has_emulated_storage = _detect_emulated_storage(fstab)
		if self.has_emulated_storage:
			LOGD("Emulated storage detected in fstab (RECOVERY_SDCARD_ON_DATA)")

		self.has_sdcard = _detect_has_sdcard(fstab)
		if not self.has_sdcard:
			LOGD("No SD card detected in fstab (BOARD_HAS_NO_REAL_SDCARD)")

		self.userdata_fs_type = _detect_userdata_fs_type(fstab)
		LOGD(f"Userdata filesystem type: {self.userdata_fs_type}")

		# Detect touch screen orientation from build properties
		self.touchscreen_orientation = _detect_touchscreen_orientation(self.build_prop)

		# Search for init rc files
		# Per guide3: TWRP uses init.recovery.*.rc files for recovery-specific
		# configuration. Also look for factory_init.*.rc and meta_init.*.rc
		# which are common in MediaTek devices (from mediatek guide).
		self.init_rcs: List[Path] = []
		for init_rc_path in [
			self.image_info.ramdisk / location
			for location in INIT_RC_LOCATIONS
		]:
			if not init_rc_path.is_dir():
				continue

			self.init_rcs += [
				init_rc for init_rc in init_rc_path.iterdir()
				if init_rc.name.endswith(".rc") and init_rc.name != "init.rc"
			]

		# Also search vendor/etc/init for additional .rc files
		vendor_init_path = self.image_info.ramdisk / "vendor" / "etc" / "init"
		if vendor_init_path.is_dir():
			self.init_rcs += [
				init_rc for init_rc in vendor_init_path.iterdir()
				if init_rc.name.endswith(".rc")
			]

	def _detect_encryption(self) -> bool:
		"""Detect if the device supports encryption based on build properties.

		Checks for common encryption-related properties in build.prop:
		- ro.crypto.state (encrypted/unencrypted)
		- ro.crypto.type (file for FBE)
		- ro.vold.forceencryption (FDE indicator)
		- ro.crypto.dm_default_key.enabled (dm-default-key FBE)

		Returns:
			True if the device appears to support encryption.
		"""
		# Check for encryption state
		crypto_state = self.build_prop.get_prop("ro.crypto.state", "")
		if crypto_state in ENCRYPTION_STATES:
			return True

		# Check for file-based encryption type
		crypto_type = self.build_prop.get_prop("ro.crypto.type", "")
		if crypto_type == ENCRYPTION_FILE_TYPE:
			return True

		# Check for legacy FDE indicators
		fde_flag = self.build_prop.get_prop(ENCRYPTION_FDE_FLAG, "")
		if fde_flag:
			return True

		# Check for dm-default-key FBE (Android 10+)
		dm_default_key = self.build_prop.get_prop(
			"ro.crypto.dm_default_key.enabled", ""
		)
		if dm_default_key in ("true", "1"):
			return True

		return False

	def dump_to_folder(self, output_path: Path, git: bool = False) -> Path:
		"""Dump the device tree to a folder.

		Args:
			output_path: The parent output directory.
			git: Whether to initialize a git repo and commit.

		Returns:
			Path to the generated device tree folder.
		"""
		device_tree_folder = output_path / self.device_info.manufacturer / self.device_info.codename
		prebuilt_path = device_tree_folder / "prebuilt"
		recovery_root_path = device_tree_folder / "recovery" / "root"

		LOGD("Creating device tree folders...")
		if device_tree_folder.is_dir():
			rmtree(device_tree_folder, ignore_errors=True)
		device_tree_folder.mkdir(parents=True)
		prebuilt_path.mkdir(parents=True)
		recovery_root_path.mkdir(parents=True)

		LOGD("Writing makefiles/blueprints")
		self._render_template(device_tree_folder, "Android.bp", comment_prefix="//")
		self._render_template(device_tree_folder, "Android.mk")
		self._render_template(device_tree_folder, "AndroidProducts.mk")
		self._render_template(device_tree_folder, "BoardConfig.mk")
		self._render_template(device_tree_folder, "device.mk")
		self._render_template(device_tree_folder, "extract-files.sh")
		self._render_template(device_tree_folder, "omni_device.mk", out_file=f"omni_{self.device_info.codename}.mk")
		self._render_template(device_tree_folder, "README.md")
		self._render_template(device_tree_folder, "setup-makefiles.sh")
		self._render_template(device_tree_folder, "vendorsetup.sh")

		# Set permissions
		chmod(device_tree_folder / "extract-files.sh", S_IRWXU | S_IRGRP | S_IROTH)
		chmod(device_tree_folder / "setup-makefiles.sh", S_IRWXU | S_IRGRP | S_IROTH)

		LOGD("Copying kernel...")
		if self.image_info.kernel is not None:
			copyfile(self.image_info.kernel, prebuilt_path / "kernel")
		if self.image_info.dt is not None:
			copyfile(self.image_info.dt, prebuilt_path / "dt.img")
		if self.image_info.dtb is not None:
			copyfile(self.image_info.dtb, prebuilt_path / "dtb.img")
		if self.image_info.dtbo is not None:
			copyfile(self.image_info.dtbo, prebuilt_path / "dtbo.img")

		LOGD("Copying fstab...")
		fstab_etc_path = recovery_root_path / "etc"
		fstab_etc_path.mkdir(parents=True, exist_ok=True)
		(fstab_etc_path / "recovery.fstab").write_text(
			_generate_twrp_fstab(self.fstab, has_encryption=self.has_encryption)
		)

		LOGD("Copying init scripts...")
		for init_rc in self.init_rcs:
			copyfile(init_rc, recovery_root_path / init_rc.name, follow_symlinks=True)

		# Generate MediaTek-specific permissive.sh
		if self.is_mediatek:
			LOGD("Generating MediaTek permissive.sh...")
			sbin_path = recovery_root_path / "sbin"
			sbin_path.mkdir(parents=True, exist_ok=True)
			permissive_sh = sbin_path / "permissive.sh"
			self._render_template(None, "permissive.sh", out_file=str(permissive_sh), to_file=True)
			permissive_sh.chmod(S_IRWXU | S_IRGRP | S_IROTH)

		if not git:
			return device_tree_folder

		# Create a git repo
		LOGD("Creating git repo...")

		git_repo = Repo.init(device_tree_folder)

		# Configure git user for this repo only if not already set globally
		with git_repo.config_writer() as git_config_writer:
			try:
				with git_repo.config_reader() as git_config_reader:
					git_config_reader.get_value('user', 'email')
					git_config_reader.get_value('user', 'name')
					# Both are set globally; no local override needed
			except Exception:
				# Global config missing; set local defaults
				git_config_writer.set_value(
					'user', 'email', 'barezzisebastiano@gmail.com'
				)
				git_config_writer.set_value(
					'user', 'name', 'Sebastiano Barezzi'
				)

		git_repo.index.add(["*"])
		commit_message = self._render_template(
			None, "commit_message", to_file=False
		)
		git_repo.index.commit(commit_message)

		return device_tree_folder

	def _render_template(self, *args, comment_prefix: str = "#", **kwargs):
		"""Render a Jinja2 template to a file or return its content."""
		return render_template(*args,
		                       comment_prefix=comment_prefix,
		                       current_year=self.current_year,
		                       device_info=self.device_info,
		                       fstab=self.fstab,
		                       has_emulated_storage=self.has_emulated_storage,
		                       has_encryption=self.has_encryption,
		                       has_hardware_mismatch=self.has_hardware_mismatch,
		                       has_sdcard=self.has_sdcard,
		                       image_info=self.image_info,
		                       is_mediatek=self.is_mediatek,
		                       is_qualcomm=self.is_qualcomm,
		                       is_samsung=self.is_samsung,
		                       is_selinux_permissive=self.is_selinux_permissive,
		                       touchscreen_orientation=self.touchscreen_orientation,
		                       tw_theme=self.tw_theme,
		                       userdata_fs_type=self.userdata_fs_type,
		                       version=version,
		                       **kwargs)

	def cleanup(self):
		"""Clean up temporary resources used during image extraction."""
		self.aik_manager.cleanup()

	def __enter__(self):
		"""Support for use as a context manager."""
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		"""Clean up on context manager exit."""
		self.cleanup()
		return False
