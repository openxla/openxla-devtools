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

from . import utils

META_FILENAME = ".openxla_workspace.json"
VERSION = 0


@dataclass
class WorkspaceMeta:
  dir: Path

  @staticmethod
  def load_metafile(p: Path) -> "WorkspaceMeta":
    with open(p, "rt") as f:
      info = json.load(f)
    version = info.get("version", VERSION)
    return WorkspaceMeta(dir=p.parent)

  def save_metafile(self):
    info = {"version": VERSION}
    info_json = json.dumps(info, sort_keys=True, indent=2)
    with open(self.dir / META_FILENAME, "wt") as f:
      f.write(info_json)
      f.write("\n")


def find(from_dir: Path = None) -> Optional[WorkspaceMeta]:
  if not from_dir:
    from_dir = Path.cwd()
  # Walk up.
  from_dir = from_dir.resolve()
  orig_from_dir = from_dir
  while from_dir:
    meta_file = from_dir / META_FILENAME
    if meta_file.exists():
      break
    new_from_dir = from_dir.parent
    if new_from_dir == from_dir:
      return None
    from_dir = new_from_dir
  return WorkspaceMeta.load_metafile(meta_file)


def find_required(from_dir: Path = None) -> WorkspaceMeta:
  if not from_dir:
    from_dir = Path.cwd()
  ws = find(from_dir)
  if not ws:
    raise utils.CLIError(
        f"No workspace found in a directory enclosing {from_dir}")
  return ws


def initialize(at_dir: Path) -> WorkspaceMeta:
  ws = WorkspaceMeta(dir=at_dir)
  ws.save_metafile()
  return ws
