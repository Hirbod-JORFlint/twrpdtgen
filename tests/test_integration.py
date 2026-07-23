"""Integration tests using the actual recovery.img."""

import shutil
from pathlib import Path

import pytest

from twrpdtgen.device_tree import DeviceTree

RECOVERY_IMG = Path(__file__).parent.parent / "recovery.img"


@pytest.fixture(scope="module")
def recovery_img_exists():
    return RECOVERY_IMG.is_file()


@pytest.mark.skipif(
    not RECOVERY_IMG.exists(),
    reason="recovery.img not found"
)
class TestDeviceTreeGeneration:
    @pytest.fixture(autouse=True)
    def setup_device_tree(self):
        self.output_dir = RECOVERY_IMG.parent / "test_output"
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir, ignore_errors=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        yield
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir, ignore_errors=True)

    def test_generate_device_tree(self):
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            assert folder.exists()
            assert folder.is_dir()

    def test_board_config_exists(self):
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            board_config = folder / "BoardConfig.mk"
            assert board_config.exists()
            content = board_config.read_text(encoding="utf-8")
            assert "TARGET_ARCH" in content
            assert "TARGET_BOARD_PLATFORM" in content

    def test_fstab_at_correct_path(self):
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            fstab = folder / "recovery" / "root" / "etc" / "recovery.fstab"
            assert fstab.exists(), (
                f"recovery.fstab not at expected path. "
                f"Files in recovery/root/etc: "
                f"{list((folder / 'recovery' / 'root' / 'etc').iterdir()) if (folder / 'recovery' / 'root' / 'etc').exists() else 'dir missing'}"
            )

    def test_fstab_not_at_old_wrong_path(self):
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            old_fstab = folder / "recovery.fstab"
            assert not old_fstab.exists(), (
                "recovery.fstab still at old wrong path (device root)"
            )

    def test_kernel_copied(self):
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            kernel = folder / "prebuilt" / "kernel"
            assert kernel.exists()
            assert kernel.stat().st_size > 0

    def test_init_rc_files_copied(self):
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            recovery_root = folder / "recovery" / "root"
            rc_files = list(recovery_root.glob("*.rc"))
            assert len(rc_files) > 0, "No .rc files found in recovery/root/"

    def test_device_info_correct(self):
        with DeviceTree(image=RECOVERY_IMG) as dt:
            assert dt.device_info.codename == "olive"
            assert dt.device_info.manufacturer == "xiaomi"
            assert dt.device_info.brand == "Xiaomi"
            assert str(dt.device_info.arch) == "arm64"
            assert dt.device_info.platform == "msm8937"

    def test_omni_makefile_exists(self):
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            omni_mk = folder / "omni_olive.mk"
            assert omni_mk.exists()
            content = omni_mk.read_text(encoding="utf-8")
            assert "omni_olive" in content

    def test_extract_files_script_executable(self):
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            extract = folder / "extract-files.sh"
            assert extract.exists()
            content = extract.read_text(encoding="utf-8")
            assert content.startswith("#!/bin/bash")
