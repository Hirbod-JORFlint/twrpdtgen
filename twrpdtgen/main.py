#
# Copyright (C) 2022 The Android Open Source Project
#
# SPDX-License-Identifier: Apache-2.0
#

import sys
from argparse import ArgumentParser
from pathlib import Path

from sebaubuntu_libs.liblogging import setup_logging, LOGI

from twrpdtgen import __version__ as version, current_path
from twrpdtgen.device_tree import DeviceTree


def _validate_image_path(image_path: Path) -> None:
	"""Validate that the image path is valid and accessible.

	Args:
		image_path: Path to the image file to validate.

	Raises:
		FileNotFoundError: If the image file doesn't exist.
		ValueError: If the path is not a file or is invalid.
	"""
	if not image_path.exists():
		raise FileNotFoundError(f"Image file not found: {image_path}")
	
	if not image_path.is_file():
		raise ValueError(f"Path is not a file: {image_path}")
	
	# Check file extension for common Android image formats
	valid_extensions = {'.img', '.bin', '.elf'}
	if image_path.suffix.lower() not in valid_extensions:
		LOGI(f"Warning: Unusual file extension '{image_path.suffix}'. Expected .img, .bin, or .elf")


def _validate_output_path(output_path: Path) -> None:
	"""Validate and prepare the output directory.

	Args:
		output_path: Path to the output directory.

	Raises:
		ValueError: If the output path is invalid.
	"""
	# Ensure output path is a directory
	if output_path.exists() and not output_path.is_dir():
		raise ValueError(f"Output path exists but is not a directory: {output_path}")
	
	# Check if parent directory exists
	if not output_path.parent.exists():
		raise ValueError(f"Parent directory does not exist: {output_path.parent}")


def main() -> None:
	print(f"TWRP device tree generator\n"
	      f"Version {version}\n")

	parser = ArgumentParser(prog='python3 -m twrpdtgen')

	# Main DeviceTree arguments
	parser.add_argument(
		"image", type=Path,
		help="path to an image (recovery image or boot image if the device is A/B)",
	)
	parser.add_argument(
		"-o", "--output", type=Path, default=current_path / "output",
		help="custom output folder",
	)

	# Optional DeviceTree arguments
	parser.add_argument(
		"--git", action='store_true',
		help="create a git repo after the generation",
	)

	# Logging
	parser.add_argument(
		"-d", "--debug", action='store_true',
		help="enable debugging features",
	)

	args = parser.parse_args()

	setup_logging(args.debug)

	try:
		# Validate input and output paths
		_validate_image_path(args.image)
		_validate_output_path(args.output)
		
		# Create output directory if it doesn't exist
		args.output.mkdir(parents=True, exist_ok=True)
		
		LOGI(f"Starting device tree generation for image: {args.image}")
		LOGI(f"Output directory: {args.output}")
		
		with DeviceTree(image=args.image) as device_tree:
			folder = device_tree.dump_to_folder(args.output, git=args.git)
			LOGI(f"Device tree successfully generated at: {folder}")
			print(f"\nDone! You can find the device tree in {folder}")
	except FileNotFoundError as e:
		print(f"Error: Required file not found: {e}", file=sys.stderr)
		sys.exit(1)
	except PermissionError as e:
		print(f"Error: Permission denied: {e}", file=sys.stderr)
		sys.exit(1)
	except ValueError as e:
		print(f"Error: Invalid input: {e}", file=sys.stderr)
		sys.exit(1)
	except RuntimeError as e:
		print(f"Error: {e}", file=sys.stderr)
		sys.exit(1)
	except KeyboardInterrupt:
		print("\nOperation cancelled by user", file=sys.stderr)
		sys.exit(130)
	except Exception as e:
		print(f"Unexpected error: {e}", file=sys.stderr)
		if args.debug:
			import traceback
			traceback.print_exc()
		sys.exit(1)
