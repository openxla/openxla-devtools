# Copyright 2023 The OpenXLA Authors
#
# Licensed under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

from typing import Dict, List, Optional, Tuple

from dataclasses import dataclass
from pathlib import Path

from . import git
from . import workspace_meta
from . import utils


@dataclass
class RepoInfo:
  name: str
  ro_url: str
  rw_url: str
  deps: List[str]
  submodules: bool = False
  tracking_branch: str = "main"

  def __post_init__(self):
    if self.name in ALL_REPOS:
      raise ValueError(f"Repository {self.name} already exists")
    ALL_REPOS[self.name] = self

  def dir(self,
          ws: workspace_meta.WorkspaceMeta,
          *,
          validate: bool = True) -> Path:
    repo_dir = ws.dir / self.name
    if validate:
      if not git.toplevel(repo_dir):
        raise utils.CLIError(
            f"Repository {self.name} at {repo_dir} is not checkout out")
    return repo_dir


ALL_REPOS: Dict[str, RepoInfo] = {}

RepoInfo(name="iree",
         ro_url="https://github.com/openxla/iree.git",
         rw_url="git@github.com:openxla/iree.git",
         deps=[],
         submodules=True)
RepoInfo(name="openxla-pjrt-plugin",
         ro_url="https://github.com/openxla/openxla-pjrt-plugin.git",
         rw_url="git@github.com:openxla/openxla-pjrt-plugin.git",
         deps=["iree", "xla"])
RepoInfo(name="stablehlo",
         ro_url="https://github.com/openxla/stablehlo.git",
         rw_url="git@github.com:openxla/stablehlo.git",
         deps=[])
RepoInfo(name="xla",
         ro_url="https://github.com/openxla/xla.git",
         rw_url="git@github.com:openxla/xla.git",
         deps=[])


def find(name_query: str) -> Optional[RepoInfo]:
  r = ALL_REPOS.get(name_query)
  return r


def find_required(name_query: str) -> RepoInfo:
  r = find(name_query)
  if not r:
    options = ', '.join([v.name for v in ALL_REPOS.values()])
    raise utils.CLIError(f"No repository matching '{name_query}' found ("
                         f"did you mean one of: {options})")
  return r


def get_from_dir(dir: Path) -> Tuple[workspace_meta.WorkspaceMeta, RepoInfo]:
  toplevel = git.toplevel(dir)
  if not toplevel:
    raise utils.CLIError(f"Directory {dir} does not enclose a git repository")
  ws = workspace_meta.find_required(toplevel)
  repo = ALL_REPOS.get(toplevel.name)
  if not repo:
    raise utils.CLIError(
        f"Git repository {toplevel} is not a known OpenXLA repository")
  return ws, repo, toplevel


def checkout(ws: workspace_meta.WorkspaceMeta,
             repo: RepoInfo,
             *,
             rw: bool = True,
             checkout_deps: bool = True,
             submodules: bool = True,
             skip_repo_names: set = None):
  if not skip_repo_names:
    skip_repo_names = set()
  if repo.name not in skip_repo_names:
    url = repo.rw_url if rw else repo.ro_url
    path = ws.dir / repo.name
    if path.exists():
      if not git.toplevel(path):
        raise utils.CLIError(
            "Directory {path} exists but is not a git repository")
      print(f"Skipping checkout of {repo.name} (already exists)")
    else:
      print(f"Checking out {repo.name} into {path} (from {url})")
      git.clone(url, path)
      if submodules and repo.submodules:
        git.init_submodules(path)

  skip_repo_names.add(repo.name)
  if checkout_deps:
    for dep_name in repo.deps:
      if dep_name in skip_repo_names:
        continue
      dep_repo = ALL_REPOS[dep_name]
      checkout(ws,
               dep_repo,
               rw=rw,
               checkout_deps=checkout_deps,
               skip_repo_names=skip_repo_names)
