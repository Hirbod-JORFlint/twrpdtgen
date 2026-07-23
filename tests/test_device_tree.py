"""Tests for device tree helpers and template rendering."""

from pathlib import Path

from twrpdtgen.device_tree import (
    BUILDPROP_LOCATIONS,
    FSTAB_LOCATIONS,
    _detect_selinux_permissive,
    _detect_tw_theme,
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
