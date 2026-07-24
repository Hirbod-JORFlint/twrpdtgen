"""Tests for device tree helpers and template rendering."""

from pathlib import Path

from twrpdtgen.device_tree import (
    BUILDPROP_LOCATIONS,
    FSTAB_LOCATIONS,
    FSTAB_BACKUP_PARTITIONS,
    FSTAB_PARTITION_DISPLAY_NAMES,
    FSTAB_REMOVABLE_STORAGE,
    _detect_emulated_storage,
    _detect_has_sdcard,
    _detect_hardware_mismatch,
    _detect_selinux_permissive,
    _detect_touchscreen_orientation,
    _detect_tw_theme,
    _detect_userdata_fs_type,
    _generate_twrp_fstab,
    _is_mediatek_platform,
    _is_qualcomm_platform,
    _is_samsung_device,
)


class TestHelperFunctions:
    def test_is_mediatek_mt6735(self):
        assert _is_mediatek_platform("mt6735") is True

    def test_is_mediatek_uppercase(self):
        assert _is_mediatek_platform("MT6765") is True

    def test_is_mediatek_qcom(self):
        assert _is_mediatek_platform("msm8937") is False

    def test_is_mediatek_default(self):
        assert _is_mediatek_platform("default") is False

    def test_is_qualcomm_platform(self):
        assert _is_qualcomm_platform("msm8937") is True
        assert _is_qualcomm_platform("MSM8998") is True
        assert _is_qualcomm_platform("sdm845") is True
        assert _is_qualcomm_platform("SM8150") is True

    def test_is_not_qualcomm_platform(self):
        assert _is_qualcomm_platform("mt6735") is False
        assert _is_qualcomm_platform("default") is False
        assert _is_qualcomm_platform("exynos9810") is False

    def test_is_samsung_device(self):
        assert _is_samsung_device("samsung") is True
        assert _is_samsung_device("Samsung") is True
        assert _is_samsung_device("SAMSUNG") is True

    def test_is_not_samsung_device(self):
        assert _is_samsung_device("xiaomi") is False
        assert _is_samsung_device("google") is False

    def test_detect_tw_theme_hdpi(self):
        assert _detect_tw_theme(320) == "portrait_hdpi"
        assert _detect_tw_theme(480) == "portrait_hdpi"
        assert _detect_tw_theme(240) == "portrait_hdpi"

    def test_detect_tw_theme_mdpi(self):
        assert _detect_tw_theme(160) == "portrait_mdpi"
        assert _detect_tw_theme(120) == "portrait_mdpi"

    def test_detect_tw_theme_none(self):
        assert _detect_tw_theme(None) == "portrait_hdpi"

    def test_detect_tw_theme_invalid(self):
        assert _detect_tw_theme("invalid") == "portrait_hdpi"

    def test_detect_tw_theme_boundary(self):
        assert _detect_tw_theme(239) == "portrait_mdpi"
        assert _detect_tw_theme(240) == "portrait_hdpi"

    def test_detect_tw_theme_landscape_hdpi(self):
        assert _detect_tw_theme(320, is_landscape=True) == "landscape_hdpi"
        assert _detect_tw_theme(480, is_landscape=True) == "landscape_hdpi"

    def test_detect_tw_theme_landscape_mdpi(self):
        assert _detect_tw_theme(160, is_landscape=True) == "landscape_mdpi"
        assert _detect_tw_theme(120, is_landscape=True) == "landscape_mdpi"

    def test_detect_tw_theme_landscape_none(self):
        assert _detect_tw_theme(None, is_landscape=True) == "landscape_hdpi"

    def test_detect_tw_theme_watch(self):
        assert _detect_tw_theme(320, is_watch=True) == "watch_mdpi"
        assert _detect_tw_theme(160, is_watch=True) == "watch_mdpi"
        assert _detect_tw_theme(None, is_watch=True) == "watch_mdpi"

    def test_detect_selinux_permissive_true(self):
        cmdline = "console=ttyMSM0,115200n8 androidboot.selinux=permissive"
        assert _detect_selinux_permissive(cmdline) is True

    def test_detect_selinux_permissive_false(self):
        cmdline = "console=ttyMSM0,115200n8 androidboot.hardware=qcom"
        assert _detect_selinux_permissive(cmdline) is False

    def test_detect_selinux_permissive_empty(self):
        assert _detect_selinux_permissive("") is False
        assert _detect_selinux_permissive(None) is False

    def test_detect_hardware_mismatch_match(self):
        assert _detect_hardware_mismatch("sagit", "sagit") is False

    def test_detect_hardware_mismatch_case_insensitive(self):
        assert _detect_hardware_mismatch("SAGIT", "sagit") is False

    def test_detect_hardware_mismatch_mismatch(self):
        assert _detect_hardware_mismatch("qcom", "sagit") is True

    def test_detect_hardware_mismatch_empty(self):
        assert _detect_hardware_mismatch("", "sagit") is False
        assert _detect_hardware_mismatch("qcom", "") is False
        assert _detect_hardware_mismatch("", "") is False


class TestFstabAnalysis:
    """Tests for fstab analysis helpers (from guide1)."""

    @staticmethod
    def _make_fstab_entry(mount_point, fs_type, src, mnt_flags=None, fs_flags=None):
        """Create a mock FstabEntry-like object."""
        class MockEntry:
            def __init__(self, mount_point, fs_type, src, mnt_flags, fs_flags):
                self.mount_point = mount_point
                self.fs_type = fs_type
                self.src = src
                self.mnt_flags = mnt_flags or []
                self.fs_flags = fs_flags or []
        return MockEntry(mount_point, fs_type, src, mnt_flags or [], fs_flags or [])

    @staticmethod
    def _make_fstab(entries):
        """Create a mock Fstab-like object."""
        class MockFstab:
            def __init__(self, entries):
                self.entries = entries
        return MockFstab(entries)

    def test_detect_emulated_storage_with_sdcard(self):
        """Device with /sdcard in fstab uses emulated storage."""
        fstab = self._make_fstab([
            self._make_fstab_entry("/data", "ext4", "/dev/block/userdata"),
            self._make_fstab_entry("/sdcard", "vfat", "/dev/block/mmcblk1p1"),
        ])
        assert _detect_emulated_storage(fstab) is True

    def test_detect_emulated_storage_with_noemulatedsd(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/data", "f2fs", "/dev/block/userdata",
                                   fs_flags=["wait", "check", "noemulatedsd"]),
        ])
        assert _detect_emulated_storage(fstab) is True

    def test_detect_no_emulated_storage(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/data", "ext4", "/dev/block/userdata"),
            self._make_fstab_entry("/external_sd", "vfat", "/dev/block/mmcblk1p1"),
        ])
        assert _detect_emulated_storage(fstab) is False

    def test_detect_sdcard_with_external(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/external_sd", "vfat", "/dev/block/mmcblk1p1",
                                   fs_flags=["removable"]),
        ])
        assert _detect_has_sdcard(fstab) is True

    def test_detect_sdcard_with_usb_otg(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/usb-otg", "vfat", "/dev/block/sda1",
                                   fs_flags=["removable"]),
        ])
        assert _detect_has_sdcard(fstab) is True

    def test_detect_no_sdcard(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/data", "ext4", "/dev/block/userdata"),
            self._make_fstab_entry("/sdcard", "vfat", "/dev/block/mmcblk1p1"),
        ])
        assert _detect_has_sdcard(fstab) is False

    def test_detect_userdata_fs_type_ext4(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/data", "ext4", "/dev/block/userdata"),
        ])
        assert _detect_userdata_fs_type(fstab) == "ext4"

    def test_detect_userdata_fs_type_f2fs(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/data", "f2fs", "/dev/block/userdata"),
        ])
        assert _detect_userdata_fs_type(fstab) == "f2fs"

    def test_detect_userdata_fs_type_default(self):
        """No /data entry should default to ext4."""
        fstab = self._make_fstab([
            self._make_fstab_entry("/system", "ext4", "/dev/block/system"),
        ])
        assert _detect_userdata_fs_type(fstab) == "ext4"


class TestTouchscreenOrientation:
    """Tests for touch screen orientation detection (from guide1)."""

    @staticmethod
    def _make_build_prop(props):
        """Create a mock BuildProp-like object."""
        class MockBuildProp:
            def __init__(self, props):
                self._props = props
            def get_prop(self, key, default=""):
                return self._props.get(key, default)
        return MockBuildProp(props)

    def test_swap_xy_rotation_90(self):
        bp = self._make_build_prop({"ro.sf.hwrotation": "90"})
        result = _detect_touchscreen_orientation(bp)
        assert result["swap_xy"] is True

    def test_swap_xy_rotation_270(self):
        bp = self._make_build_prop({"ro.sf.hwrotation": "270"})
        result = _detect_touchscreen_orientation(bp)
        assert result["swap_xy"] is True

    def test_no_rotation(self):
        bp = self._make_build_prop({"ro.sf.hwrotation": "0"})
        result = _detect_touchscreen_orientation(bp)
        assert result["swap_xy"] is False
        assert result["flip_x"] is False
        assert result["flip_y"] is False

    def test_rotation_180_flips_both(self):
        bp = self._make_build_prop({"ro.sf.hwrotation": "180"})
        result = _detect_touchscreen_orientation(bp)
        assert result["flip_x"] is True
        assert result["flip_y"] is True

    def test_no_hwrotation_prop(self):
        bp = self._make_build_prop({})
        result = _detect_touchscreen_orientation(bp)
        assert result["swap_xy"] is False
        assert result["flip_x"] is False
        assert result["flip_y"] is False

    def test_invalid_hwrotation(self):
        bp = self._make_build_prop({"ro.sf.hwrotation": "invalid"})
        result = _detect_touchscreen_orientation(bp)
        assert result["swap_xy"] is False


class TestBuildPropLocations:
    def test_default_prop_in_locations(self):
        names = [loc.name for loc in BUILDPROP_LOCATIONS]
        assert "default.prop" in names

    def test_prop_default_in_locations(self):
        names = [loc.name for loc in BUILDPROP_LOCATIONS]
        assert "prop.default" in names

    def test_system_build_prop_in_locations(self):
        names = [loc.as_posix() for loc in BUILDPROP_LOCATIONS]
        assert "system/build.prop" in names

    def test_vendor_build_prop_in_locations(self):
        names = [loc.as_posix() for loc in BUILDPROP_LOCATIONS]
        assert "vendor/build.prop" in names

    def test_system_etc_build_prop_in_locations(self):
        names = [loc.as_posix() for loc in BUILDPROP_LOCATIONS]
        assert "system/etc/build.prop" in names


class TestFstabLocations:
    def test_etc_recovery_fstab(self):
        names = [loc.as_posix() for loc in FSTAB_LOCATIONS]
        assert "etc/recovery.fstab" in names

    def test_system_etc_recovery_fstab(self):
        names = [loc.as_posix() for loc in FSTAB_LOCATIONS]
        assert "system/etc/recovery.fstab" in names


class TestTemplateRendering:
    def test_jinja_env_setup(self):
        from twrpdtgen.templates import jinja_env
        assert jinja_env.keep_trailing_newline is True

    def test_render_license_template(self):
        from twrpdtgen.templates import render_template
        result = render_template(
            None, "LICENSE",
            comment_prefix="#",
            to_file=False,
        )
        assert "Copyright" in result
        assert "Apache-2.0" in result


class TestGenerateTwrpFstab:
    """Tests for the enhanced TWRP fstab generator (guide1 flags)."""

    @staticmethod
    def _make_fstab_entry(mount_point, fs_type, src, mnt_flags=None, fs_flags=None):
        class MockEntry:
            def __init__(self, mount_point, fs_type, src, mnt_flags, fs_flags):
                self.mount_point = mount_point
                self.fs_type = fs_type
                self.src = src
                self.mnt_flags = mnt_flags or []
                self.fs_flags = fs_flags or []
            def is_logical(self):
                return "logical" in self.fs_flags
            def is_slotselect(self):
                return "slotselect" in self.fs_flags
        return MockEntry(mount_point, fs_type, src, mnt_flags or [], fs_flags or [])

    @staticmethod
    def _make_fstab(entries):
        class MockFstab:
            def __init__(self, entries):
                self.entries = entries
        return MockFstab(entries)

    def test_display_name_system_root(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/", "ext4", "/dev/block/system"),
        ])
        result = _generate_twrp_fstab(fstab)
        assert "display=System" in result

    def test_display_name_data(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/data", "ext4", "/dev/block/userdata"),
        ])
        result = _generate_twrp_fstab(fstab)
        assert "display=Data" in result

    def test_backup_flag_on_system(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/system", "ext4", "/dev/block/system"),
        ])
        result = _generate_twrp_fstab(fstab)
        assert "backup=1" in result

    def test_backup_flag_on_data(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/data", "ext4", "/dev/block/userdata"),
        ])
        result = _generate_twrp_fstab(fstab)
        assert "backup=1" in result

    def test_backup_flag_on_boot(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/boot", "emmc", "/dev/block/boot"),
        ])
        result = _generate_twrp_fstab(fstab)
        # /boot should have backup=1 (it's in FSTAB_BACKUP_PARTITIONS)
        assert "backup=1" in result

    def test_storage_flag_on_sdcard(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/sdcard", "vfat", "/dev/block/mmcblk1p1"),
        ])
        result = _generate_twrp_fstab(fstab)
        assert "storage" in result

    def test_removable_flags_on_external_sd(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/external_sd", "vfat", "/dev/block/mmcblk1p1"),
        ])
        result = _generate_twrp_fstab(fstab)
        assert "storage" in result
        assert "wipeingui" in result
        assert "removable" in result

    def test_removable_flags_on_usb_otg(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/usb-otg", "vfat", "/dev/block/sda1"),
        ])
        result = _generate_twrp_fstab(fstab)
        assert "storage" in result
        assert "wipeingui" in result
        assert "removable" in result

    def test_length_flag_with_encryption(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/data", "ext4", "/dev/block/userdata"),
        ])
        result = _generate_twrp_fstab(fstab, has_encryption=True)
        assert "length=-16384" in result

    def test_no_length_flag_without_encryption(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/data", "ext4", "/dev/block/userdata"),
        ])
        result = _generate_twrp_fstab(fstab, has_encryption=False)
        assert "length=" not in result

    def test_slotselect_preserved(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/system", "ext4", "/dev/block/system",
                                   fs_flags=["slotselect"]),
        ])
        result = _generate_twrp_fstab(fstab)
        assert "slotselect" in result

    def test_logical_preserved(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/system", "ext4", "/dev/block/system",
                                   fs_flags=["logical"]),
        ])
        result = _generate_twrp_fstab(fstab)
        assert "logical" in result

    def test_all_entries_have_flags(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/system", "ext4", "/dev/block/system"),
            self._make_fstab_entry("/data", "ext4", "/dev/block/userdata"),
            self._make_fstab_entry("/cache", "ext4", "/dev/block/cache"),
        ])
        result = _generate_twrp_fstab(fstab)
        for line in result.split("\n"):
            if line.strip():
                assert "flags=" in line

    def test_trailing_newline(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/system", "ext4", "/dev/block/system"),
        ])
        result = _generate_twrp_fstab(fstab)
        assert result.endswith("\n")

    def test_wipeduringfactoryreset_on_data(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/data", "ext4", "/dev/block/userdata"),
        ])
        result = _generate_twrp_fstab(fstab)
        assert "wipeduringfactoryreset" in result

    def test_wipeduringfactoryreset_on_cache(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/cache", "ext4", "/dev/block/cache"),
        ])
        result = _generate_twrp_fstab(fstab)
        assert "wipeduringfactoryreset" in result

    def test_no_wipeduringfactoryreset_on_system(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/system", "ext4", "/dev/block/system"),
        ])
        result = _generate_twrp_fstab(fstab)
        assert "wipeduringfactoryreset" not in result

    def test_settingsstorage_on_data(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/data", "ext4", "/dev/block/userdata"),
        ])
        result = _generate_twrp_fstab(fstab)
        assert "settingsstorage" in result

    def test_no_settingsstorage_on_system(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/system", "ext4", "/dev/block/system"),
        ])
        result = _generate_twrp_fstab(fstab)
        assert "settingsstorage" not in result

    def test_canbewipe_on_cust(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/cust", "ext4", "/dev/block/cust"),
        ])
        result = _generate_twrp_fstab(fstab)
        assert "canbewipe" in result

    def test_canbewipe_on_preload(self):
        fstab = self._make_fstab([
            self._make_fstab_entry("/preload", "ext4", "/dev/block/preload"),
        ])
        result = _generate_twrp_fstab(fstab)
        assert "canbewipe" in result
