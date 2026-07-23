#
# Copyright (C) 2022 The Android Open Source Project
#
# SPDX-License-Identifier: Apache-2.0
#

from datetime import datetime
from git import Repo
from os import chmod
from pathlib import Path
from sebaubuntu_libs.libaik import AIKManager
from sebaubuntu_libs.libandroid.device_info import DeviceInfo
from sebaubuntu_libs.libandroid.fstab import Fstab
from sebaubuntu_libs.libandroid.props import BuildProp
from sebaubuntu_libs.liblogging import LOGD
from shutil import copyfile, rmtree
from stat import S_IRWXU, S_IRGRP, S_IROTH
from twrpdtgen import __version__ as version
from twrpdtgen.templates import render_template
from typing import List, Optional

BUILDPROP_LOCATIONS = [Path() / "default.prop",
                       Path() / "prop.default",]
BUILDPROP_LOCATIONS += [Path() / dir / "build.prop"
                        for dir in ["system", "vendor"]]
BUILDPROP_LOCATIONS += [Path() / dir / "etc" / "build.prop"
                        for dir in ["system", "vendor"]]

FSTAB_LOCATIONS = [Path() / "etc" / "recovery.fstab"]
FSTAB_LOCATIONS += [Path() / dir / "etc" / "recovery.fstab"
                    for dir in ["system", "vendor"]]

INIT_RC_LOCATIONS = [Path()]
INIT_RC_LOCATIONS += [Path() / dir / "etc" / "init"
                      for dir in ["system", "vendor"]]

MEDIATEK_PLATFORMS = ("mt", "mtk")


def _is_mediatek_platform(platform: str) -> bool:
	"""Check if a platform string indicates a MediaTek chipset.

	Args:
		platform: The platform identifier (e.g., "mt6735", "MT6765").

	Returns:
		True if the platform is MediaTek-based.
	"""
	return platform.lower().startswith(MEDIATEK_PLATFORMS)


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
			raise FileNotFoundError("Specified file doesn't exist")

		# Extract the image
		self.aik_manager = AIKManager()
		self.image_info = self.aik_manager.unpackimg(image)

		if not self.image_info.ramdisk:
			raise RuntimeError("Ramdisk not found in image")

		LOGD("Getting device infos...")
		self.build_prop = BuildProp()
		for build_prop in [self.image_info.ramdisk / location for location in BUILDPROP_LOCATIONS]:
			if not build_prop.is_file():
				continue

			self.build_prop.import_props(build_prop)

		self.device_info = DeviceInfo(self.build_prop)

		# Detect MediaTek platform
		self.is_mediatek = _is_mediatek_platform(self.device_info.platform)
		if self.is_mediatek:
			LOGD(f"MediaTek platform detected: {self.device_info.platform}")

		# Generate fstab
		fstab = None
		for fstab_location in [self.image_info.ramdisk / location for location in FSTAB_LOCATIONS]:
			if not fstab_location.is_file():
				continue

			LOGD(f"Generating fstab using {fstab_location} as reference...")
			fstab = Fstab(fstab_location)
			break

		if fstab is None:
			raise RuntimeError("fstab not found in image")

		self.fstab = fstab

		# Search for init rc files
		self.init_rcs: List[Path] = []
		for init_rc_path in [self.image_info.ramdisk / location for location in INIT_RC_LOCATIONS]:
			if not init_rc_path.is_dir():
				continue

			self.init_rcs += [init_rc for init_rc in init_rc_path.iterdir()
			                  if init_rc.name.endswith(".rc") and init_rc.name != "init.rc"]

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
		(device_tree_folder / "recovery.fstab").write_text(self.fstab.format(twrp=True))

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

		with git_repo.config_reader() as git_config_reader, \
		     git_repo.config_writer() as git_config_writer:
			try:
				git_global_email = git_config_reader.get_value('user', 'email')
				git_global_name = git_config_reader.get_value('user', 'name')
			except Exception:
				git_global_email, git_global_name = None, None

			if git_global_email is None or git_global_name is None:
				git_config_writer.set_value('user', 'email', 'barezzisebastiano@gmail.com')
				git_config_writer.set_value('user', 'name', 'Sebastiano Barezzi')

		git_repo.index.add(["*"])
		commit_message = self._render_template(None, "commit_message", to_file=False)
		git_repo.index.commit(commit_message)

		return device_tree_folder

	def _render_template(self, *args, comment_prefix: str = "#", **kwargs):
		"""Render a Jinja2 template to a file or return its content."""
		return render_template(*args,
		                       comment_prefix=comment_prefix,
		                       current_year=self.current_year,
		                       device_info=self.device_info,
		                       fstab=self.fstab,
		                       image_info=self.image_info,
		                       is_mediatek=self.is_mediatek,
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
