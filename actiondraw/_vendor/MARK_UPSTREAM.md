# Mark native Markdown editor

Source: https://github.com/oyvinrog/mark/blob/main/mark.py
Author: oyvinrog
Upstream Git blob: 946c2b15da7ad9bb21a5741a5e3ac980cc35108e

Adapted for ActionDraw at the user's explicit request. The upstream repository
has no license declaration at this revision; no new license grant is asserted.
Local changes: PyQt6 imports replaced with PySide6; Markdown serialization accepts
an optional document clone so ActionDraw can preserve node-link anchor identities.
The integration and project persistence live outside this upstream module.
