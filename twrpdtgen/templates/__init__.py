#
# Copyright (C) 2022 The Android Open Source Project
#
# SPDX-License-Identifier: Apache-2.0
#
"""twrpdtgen templates utils."""

from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from typing import Optional

from twrpdtgen import module_path

jinja_env = Environment(
	loader=FileSystemLoader(module_path / 'templates'),
	autoescape=True,
	trim_blocks=True,
	lstrip_blocks=True,
	keep_trailing_newline=True,
)


def render_template(path: Optional[Path], template_file: str,
                    out_file: str = '', to_file: bool = True, **kwargs):
	"""Render a Jinja2 template to a file.

	Args:
		path: Output directory path. Required when to_file is True.
		template_file: Name of the template file (without .jinja2 extension).
		out_file: Custom output filename. Defaults to template_file name.
		to_file: Whether to write the rendered output to a file.
		**kwargs: Variables to pass to the Jinja2 template.

	Returns:
		The rendered template string.
	"""
	template = jinja_env.get_template(f"{template_file}.jinja2")
	rendered_template = template.render(**kwargs)

	if to_file:
		if not out_file:
			out_file = template_file

		output_path = Path(path) / out_file
		output_path.write_text(rendered_template, encoding="utf-8")

	return rendered_template
