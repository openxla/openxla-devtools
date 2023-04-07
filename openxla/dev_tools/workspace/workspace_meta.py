# Copyright 2023 The OpenXLA Authors
#
# Licensed under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

from typing import Optional

import json

from dataclasses import dataclass
from pathlib import Path
import os

from . import types


def find(from_dir: Path = None) -> Optional[types.WorkspaceMeta]:
  if not from_dir:
    from_dir = Path.cwd()
  # Walk up.
  from_dir = from_dir.resolve()
  orig_from_dir = from_dir
  while from_dir:
    meta_file = from_dir / types.META_FILENAME
    if meta_file.exists():
      break
    new_from_dir = from_dir.parent
    if new_from_dir == from_dir:
      return None
    from_dir = new_from_dir
  return types.WorkspaceMeta.load_metafile(meta_file)


def find_required(from_dir: Path = None) -> types.WorkspaceMeta:
  if not from_dir:
    from_dir = Path.cwd()
  ws = find(from_dir)
  if not ws:
    raise types.CLIError(
        f"No workspace found in a directory enclosing {from_dir}")
  return ws


def initialize(at_dir: Path) -> types.WorkspaceMeta:
  ws = types.WorkspaceMeta(dir=at_dir)
  ws.save_metafile()
  return ws
