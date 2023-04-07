# Copyright 2023 The OpenXLA Authors
#
# Licensed under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

from typing import Dict, List, Optional

from dataclasses import dataclass
import json
from pathlib import Path

from . import git


class CLIError(Exception):
  ...


META_FILENAME = ".openxla_workspace.json"
WS_VERSION = 0


@dataclass
class WorkspaceMeta:
  dir: Path

  @staticmethod
  def load_metafile(p: Path) -> "WorkspaceMeta":
    with open(p, "rt") as f:
      info = json.load(f)
    version = info.get("version", WS_VERSION)
    return WorkspaceMeta(dir=p.parent)

  def save_metafile(self):
    info = {"version": WS_VERSION}
    info_json = json.dumps(info, sort_keys=True, indent=2)
    with open(self.dir / META_FILENAME, "wt") as f:
      f.write(info_json)
      f.write("\n")


@dataclass
class RepoInfo:
  name: str
  ro_url: str
  rw_url: str
  deps: List[str]
  submodules: bool = False
  tracking_branch: str = "main"
  rolling_schedules: Optional[Dict[str, List["RepoAction"]]] = None

  def __post_init__(self):
    if self.name in ALL_REPOS:
      raise ValueError(f"Repository {self.name} already exists")
    ALL_REPOS[self.name] = self

  def dir(self, ws: WorkspaceMeta, *, validate: bool = True) -> Path:
    repo_dir = ws.dir / self.name
    if validate:
      if not git.toplevel(repo_dir):
        raise CLIError(
            f"Repository {self.name} at {repo_dir} is not checkout out")
    return repo_dir


ALL_REPOS: Dict[str, RepoInfo] = {}


class RepoAction:
  """Base class for an action to be applied to a repository."""

  def update(self, ws: WorkspaceMeta, r: RepoInfo):
    raise NotImplementedError
