# twrpdtgen

A fork of [twrpdtgen](https://github.com/twrpdtgen/twrpdtgen) with enhanced Windows support, TWRP flag generation, and additional device detection.

Create a [TWRP](https://twrp.me/)-compatible device tree only from an Android recovery image (or a boot image if the device uses non-dynamic partitions A/B) of your device's stock ROM.
It has been confirmed that this script supports images built starting from Android 4.4 up to Android 12.

Requires Python 3.8 or greater

## Platform Support

- **Linux**: Full support (recommended)
- **macOS**: Full support
- **Windows**: Supported via pure Python image unpacker (no external tools required)

## Installation

This fork is **not published to PyPI** — install directly from GitHub:

```sh
pip3 install git+https://github.com/Hirbod-JORFlint/twrpdtgen.git
```

To upgrade to the latest version:

```sh
pip3 install --upgrade git+https://github.com/Hirbod-JORFlint/twrpdtgen.git
```

### Linux/macOS

Be sure to have `cpio` installed in your system:
```sh
# Debian/Ubuntu
sudo apt install cpio

# Arch Linux
sudo pacman -S cpio

# macOS (via Homebrew)
brew install cpio
```

### Windows

No additional system packages required. The tool uses a pure Python image unpacker on Windows.

If your recovery image uses LZ4 compression, install the optional LZ4 support:
```sh
pip3 install "git+https://github.com/Hirbod-JORFlint/twrpdtgen.git[windows]"
```

## Instructions

### Basic Usage

```sh
python3 -m twrpdtgen <path to image>
```

When an image is provided, if everything goes well, there will be a device tree at `output/manufacturer/codename`

### Advanced Usage

#### Custom Output Directory

```sh
python3 -m twrpdtgen <path to image> -o /path/to/output
```

#### Enable Debug Mode

```sh
python3 -m twrpdtgen <path to image> -d
```

#### Create Git Repository

```sh
python3 -m twrpdtgen <path to image> --git
```

#### Combined Options

```sh
python3 -m twrpdtgen recovery.img -o ~/device_trees --git -d
```

### Python API Usage

You can also use the module in a script, with the following code:

```python
from twrpdtgen.device_tree import DeviceTree

# Get image info
device_tree = DeviceTree(image_path)

# Dump device tree to folder
device_tree.dump_to_folder(output_path)

# Or with git initialization
device_tree.dump_to_folder(output_path, git=True)
```

### Using as a Library

```python
from twrpdtgen.device_tree import DeviceTree
from pathlib import Path

# Generate device tree from recovery image
image_path = Path("recovery.img")
output_path = Path("output")

with DeviceTree(image=image_path) as device_tree:
    # Generate the device tree
    tree_folder = device_tree.dump_to_folder(output_path, git=True)
    print(f"Device tree generated at: {tree_folder}")
```

### Examples

#### Example 1: Basic Device Tree Generation

```sh
# Generate a device tree from a recovery image
python3 -m twrpdtgen /path/to/recovery.img
```

#### Example 2: Generate with Custom Output

```sh
# Generate device tree to a specific directory
python3 -m twrpdtgen boot.img -o ~/my_device_tree
```

#### Example 3: Debug Mode for Troubleshooting

```sh
# Enable debug logging to troubleshoot issues
python3 -m twrpdtgen recovery.img -d
```

#### Example 4: Generate with Git Repository

```sh
# Automatically initialize a git repository
python3 -m twrpdtgen recovery.img --git
```

## License

```
#
# Copyright (C) 2022 The Android Open Source Project
#
# SPDX-License-Identifier: Apache-2.0
#
```
