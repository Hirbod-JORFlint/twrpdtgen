"""Tests for device tree helpers and template rendering."""

from pathlib import Path

from twrpdtgen.device_tree import (
    BUILDPROP_LOCATIONS,
    FSTAB_LOCATIONS,
    _detect_emulated_storage,
    _detect_has_sdcard,
    _detect_hardware_mismatch,
    _detect_selinux_permissive,
    _detect_touchscreen_orientation,
    _detect_tw_theme,
    _detect_userdata_fs_type,
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
