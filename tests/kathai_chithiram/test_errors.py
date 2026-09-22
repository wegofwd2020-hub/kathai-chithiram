"""Tests for kathai_chithiram.errors module."""

from kathai_chithiram.errors import KathaiChithiramError, RendererError


def test_renderer_error_is_domain_error():
    err = RendererError("blender not found")
    assert isinstance(err, KathaiChithiramError)
    assert "blender not found" in str(err)
