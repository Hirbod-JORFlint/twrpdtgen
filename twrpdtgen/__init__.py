#
# Copyright (C) 2022 The Android Open Source Project
#
# SPDX-License-Identifier: Apache-2.0
#
"""TWRP device tree generator.

Automatically generates a TWRP-compatible device tree from an Android
recovery or boot image.
"""

from pathlib import Path

__version__ = "3.0.0"

module_path = Path(__file__).parent
current_path = Path.cwd()
