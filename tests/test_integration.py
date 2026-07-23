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

    def test_board_config_qualcomm_flags(self):
        """Verify Qualcomm-specific flags are present for msm8937 device."""
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            content = (folder / "BoardConfig.mk").read_text(encoding="utf-8")
            assert "TARGET_USES_QCOM_BSP" in content
            assert "TARGET_RECOVERY_QCOM_RTC_FIX" in content
            assert "BOARD_USES_QCOM_FBE_DECRYPTION" in content

    def test_board_config_common_twrp_flags(self):
        """Verify common TWRP flags are present."""
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            content = (folder / "BoardConfig.mk").read_text(encoding="utf-8")
            assert "TW_INCLUDE_RESETPROP" in content
            assert "TW_USE_MODEL_HARDWARE_ID_FOR_DEVICE_ID" in content
            assert "TW_EXCLUDE_DEFAULT_USB_INIT" in content
            assert "TW_NO_REBOOT_BOOTLOADER" in content
            assert "TW_NO_REBOOT_RECOVERY" in content

    def test_board_config_userdata_f2fs(self):
        """Verify userdata is f2fs (detected from fstab)."""
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            content = (folder / "BoardConfig.mk").read_text(encoding="utf-8")
            assert "BOARD_USERDATAIMAGE_FILE_SYSTEM_TYPE := f2fs" in content

    def test_board_config_platform_flags(self):
        """Verify platform is correctly set."""
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            content = (folder / "BoardConfig.mk").read_text(encoding="utf-8")
            assert "TARGET_BOARD_PLATFORM := msm8937" in content

    def test_board_config_arch_flags(self):
        """Verify architecture flags are correct for arm64."""
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            content = (folder / "BoardConfig.mk").read_text(encoding="utf-8")
            assert "TARGET_ARCH := arm64" in content
            assert "TARGET_2ND_ARCH := arm" in content
            assert "TARGET_CPU_ABI := arm64-v8a" in content

    def test_device_mk_has_qcom_fbe(self):
        """Verify device.mk includes Qualcomm FBE decryption packages."""
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            content = (folder / "device.mk").read_text(encoding="utf-8")
            assert "libkeymaster4" in content
            assert "libpuresoftkeymasterdevice" in content
            assert "ashmemd_aidl_interface-cpp" in content
            assert "libashmemd_client" in content

    def test_board_config_has_fstab_path(self):
        """Verify fstab path is correctly set."""
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            content = (folder / "BoardConfig.mk").read_text(encoding="utf-8")
            assert "TARGET_RECOVERY_FSTAB := $(DEVICE_PATH)/recovery/root/etc/recovery.fstab" in content

    def test_board_config_has_avb(self):
        """Verify AVB (Verified Boot) flags are present."""
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            content = (folder / "BoardConfig.mk").read_text(encoding="utf-8")
            assert "BOARD_AVB_ENABLE := true" in content
            assert "BOARD_AVB_MAKE_VBMETA_IMAGE_ARGS += --flags 3" in content

    def test_board_config_has_security_patch(self):
        """Verify anti-rollback hack is present."""
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            content = (folder / "BoardConfig.mk").read_text(encoding="utf-8")
            assert "PLATFORM_SECURITY_PATCH := 2099-12-31" in content
            assert "VENDOR_SECURITY_PATCH := 2099-12-31" in content

    def test_board_config_has_partition_info(self):
        """Verify partition sizes and types are correct."""
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            content = (folder / "BoardConfig.mk").read_text(encoding="utf-8")
            assert "BOARD_HAS_LARGE_FILESYSTEM" in content
            assert "BOARD_SYSTEMIMAGE_PARTITION_TYPE := ext4" in content
            assert "BOARD_VENDORIMAGE_FILE_SYSTEM_TYPE := ext4" in content
            assert "TARGET_COPY_OUT_VENDOR := vendor" in content

    def test_board_config_has_kernel_args(self):
        """Verify kernel arguments are present."""
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            content = (folder / "BoardConfig.mk").read_text(encoding="utf-8")
            assert "BOARD_KERNEL_BASE" in content
            assert "BOARD_KERNEL_PAGESIZE" in content
            assert "BOARD_RAMDISK_OFFSET" in content
            assert "BOARD_KERNEL_TAGS_OFFSET" in content

    def test_no_duplicate_entries_in_omni_mk(self):
        """Verify no duplicate PRODUCT_DEVICE/PRODUCT_NAME entries."""
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            content = (folder / "omni_olive.mk").read_text(encoding="utf-8")
            assert content.count("PRODUCT_DEVICE") == 1
            assert content.count("PRODUCT_NAME") == 1

    def test_omni_mk_has_brand_model(self):
        """Verify brand and model are in omni makefile."""
        with DeviceTree(image=RECOVERY_IMG) as dt:
            folder = dt.dump_to_folder(self.output_dir)
            content = (folder / "omni_olive.mk").read_text(encoding="utf-8")
            assert "PRODUCT_BRAND" in content
            assert "PRODUCT_MODEL" in content
            assert "PRODUCT_MANUFACTURER" in content
