# Copyright 2023 The OpenXLA Authors
#
# Licensed under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

from typing import Dict, List, Optional, Sequence, Tuple

from dataclasses import dataclass
from pathlib import Path
import re

from . import git
from . import roller
from . import workspace_meta
from . import types

types.RepoInfo(name="iree",
               ro_url="https://github.com/openxla/iree.git",
               rw_url="git@github.com:openxla/iree.git",
               deps=[],
               submodules=True)
# Not technically part of OpenXLA but key to integration.
types.RepoInfo(name="jax",
               ro_url="https://github.com/google/jax.git",
               rw_url="git@github.com:google/jax.git",
               deps=[])
types.RepoInfo(
    name="openxla-pjrt-plugin",
    ro_url="https://github.com/openxla/openxla-pjrt-plugin.git",
    rw_url="git@github.com:openxla/openxla-pjrt-plugin.git",
    deps=["iree", "jax", "xla"],
    rolling_schedules={
        "continuous": [
            # We want to pick up IREE runtime changes continuously.
            # For everything else, do it nightly.
            roller.GitRepoHead("iree"),
        ],
        "nightly": [
            roller.GitRepoHead("iree"),
            roller.GitRepoHead("xla"),
            roller.GitRepoHead("jax"),
            roller.PyPackage(
                "iree-compiler",
                pip_flags=[
                    "-f",
                    "https://openxla.github.io/iree/pip-release-links.html"
                ],
                update_requirements=["requirements.txt"]),
            roller.PyPackage(
                "jaxlib",
                pip_flags=[
                    "-f",
                    "https://storage.googleapis.com/jax-releases/jaxlib_nightly_releases.html",
                    "--pre",
                ],
                update_requirements=["requirements.txt"]),
        ],
    },
)
types.RepoInfo(name="stablehlo",
               ro_url="https://github.com/openxla/stablehlo.git",
               rw_url="git@github.com:openxla/stablehlo.git",
               deps=[])
types.RepoInfo(name="xla",
               ro_url="https://github.com/openxla/xla.git",
               rw_url="git@github.com:openxla/xla.git",
               deps=[])


def find(name_query: str) -> Optional[types.RepoInfo]:
  r = types.ALL_REPOS.get(name_query)
  return r


def find_required(name_query: str) -> types.RepoInfo:
  r = find(name_query)
  if not r:
    options = ', '.join([v.name for v in types.ALL_REPOS.values()])
    raise types.CLIError(f"No repository matching '{name_query}' found ("
                         f"did you mean one of: {options})")
  return r


def get_from_dir(dir: Path) -> Tuple[types.WorkspaceMeta, types.RepoInfo]:
  toplevel = git.toplevel(dir)
  if not toplevel:
    raise types.CLIError(f"Directory {dir} does not enclose a git repository")
  ws = workspace_meta.find_required(toplevel)
  repo = types.ALL_REPOS.get(toplevel.name)
  if not repo:
    raise types.CLIError(
        f"Git repository {toplevel} is not a known OpenXLA repository")
  return ws, repo, toplevel


def checkout(ws: types.WorkspaceMeta,
             repo: types.RepoInfo,
             *,
             rw: bool = True,
             checkout_deps: bool = True,
             submodules: bool = True,
             skip_repo_names: set = None,
             exclude_submodules: Sequence[str] = (),
             exclude_deps: Sequence[str] = ()):
  if not skip_repo_names:
    skip_repo_names = set()
  if repo.name not in skip_repo_names:
    url = repo.rw_url if rw else repo.ro_url
    path = ws.dir / repo.name
    if path.exists():
      if not git.toplevel(path):
        raise types.CLIError(
            "Directory {path} exists but is not a git repository")
      print(f"Skipping checkout of {repo.name} (already exists)")
    else:
      print(f"Checking out {repo.name} into {path} (from {url})")
      git.clone(url, path)
      if submodules and repo.submodules:

        def filter_submodule(s):
          for pattern in exclude_submodules:
            if re.search(pattern, f"{repo.name}:{s}"):
              print(f"Excluding submodule {s} based on --exclude-submodule")
              return False
          return True

        submodules = [
            s for s in git.list_submodules(path) if filter_submodule(s)
        ]
        git.update_submodules(path, submodules)

  skip_repo_names.add(repo.name)
  if checkout_deps:
    for dep_name in repo.deps:
      if dep_name in skip_repo_names:
        continue
      # Exclude based on flags?
      exclude_dep = False
      for exclude_pattern in exclude_deps:
        if re.search(exclude_pattern, dep_name):
          exclude_dep = True
      if exclude_dep:
        print(f"Excluding {dep_name} based on --exclude-dep")
        continue

      dep_repo = types.ALL_REPOS[dep_name]
      checkout(ws,
               dep_repo,
               rw=rw,
               checkout_deps=checkout_deps,
               submodules=submodules,
               skip_repo_names=skip_repo_names,
               exclude_submodules=exclude_submodules,
               exclude_deps=exclude_deps)
