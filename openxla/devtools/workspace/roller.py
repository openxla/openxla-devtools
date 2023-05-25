# Copyright 2023 The OpenXLA Authors
#
# Licensed under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
"""Dependency version rolling."""

from typing import Sequence

from pathlib import Path
import re
import shlex
import subprocess
import sys

from . import git
from . import pins
from . import repos
from . import workspace_meta
from . import types


class GitRepoHead(types.RepoAction):
  """Advances a tracked git dependency to HEAD of its tracking branch."""

  def __init__(self, dep_repo_name: str):
    self.dep_repo_name = dep_repo_name

  def __str__(self):
    return f"GitRepoHead({self.dep_repo_name})"

  def update(self, ws: types.WorkspaceMeta, r: types.RepoInfo):
    dep_repo = types.ALL_REPOS[self.dep_repo_name]
    head_revision = git.get_remote_head(dep_repo.ro_url,
                                        dep_repo.tracking_branch)
    print(f"  Remote head for {dep_repo.tracking_branch}: {head_revision}")
    if pins.set_pin_revision(r.dir(ws), self.dep_repo_name, head_revision):
      print("  Updated pinned revision.")
    else:
      print("  No update required.")


class GitRepoViaDep(types.RepoAction):
  """Advances a tracked git dependency to the pinned version of another repo."""

  def __init__(self, dep_repo_name: str, *, via: str):
    self.dep_repo_name = dep_repo_name
    self.via = via

  def __str__(self):
    return f"GitRepoViaDep({self.dep_repo_name}, {self.via})"

  def update(self, ws: types.WorkspaceMeta, r: types.RepoInfo):
    via_repo = types.ALL_REPOS[self.via]
    via_repo_dir = via_repo.dir(ws)
    via_pins = pins.read_existing_pins(via_repo_dir)
    if self.dep_repo_name not in via_pins:
      raise types.CLIError(
          f"Repository {via_repo} does not contain a version pin "
          f"for {self.dep_repo_name}, which is needed to roll "
          f"requested versions (available={via_pins}).")
    dep_revision = via_pins[self.dep_repo_name]
    print(f"  Resolved revision {dep_revision} via {self.via}")
    if pins.set_pin_revision(r.dir(ws), self.dep_repo_name, dep_revision):
      print("  Updated pinned revision.")
    else:
      print("  No update required.")


class PyPackage(types.RepoAction):

  def __init__(self,
               package_name: str,
               pip_flags: Sequence[str] = (),
               update_requirements: Sequence[str] = ()):
    self.package_name = package_name
    self.pip_flags = pip_flags
    self.update_requirements = update_requirements

  def __str__(self):
    return f"PyPackage({self.package_name})"

  def update(self, ws: types.WorkspaceMeta, r: types.RepoInfo):
    repo_dir = r.dir(ws)
    pip_args = [
        sys.executable,
        "-m",
        "pip",
        "index",
    ] + list(self.pip_flags) + [
        "versions",
        self.package_name,
    ]
    pip_args_text = ' '.join([shlex.quote(arg) for arg in pip_args])
    print(f"[{Path.cwd()}]$ {pip_args_text}")
    cp = subprocess.run(pip_args, capture_output=True, check=True)
    output = cp.stdout.decode()
    print(output)
    # The CLI for this command has changed a bit, but the "Available versions:"
    # line is so far consistent.
    found_version = None
    for line in output.splitlines():
      m = re.match(r"^\s*Available versions:\s+(.+)", line)
      if m:
        all_versions = re.split(r"\s*,\s*", m.group(1))
        found_version = all_versions[0]
        break
    else:
      raise types.CLIError(
          f"Could not find 'LATEST:' tag in output (note that this is an experimental CLI so may need to be updated)"
      )

    print(f"Found latest version: '{found_version}'")

    for req_file in self.update_requirements:
      req_path = (repo_dir / req_file).resolve()
      if not req_path.exists():
        raise types.CLIError(
            f"Cannot update requirements (does not exist): {req_path}")
      self.update_requirements_file(req_path, found_version)

  def update_requirements_file(self, p: Path, version: str):
    with open(p, "rt") as f:
      lines = f.readlines()
    # Scan for the package.
    new_lines = []
    for line in lines:
      m = re.match(f"^\\s*{re.escape(self.package_name)}==\\S+", line)
      if m:
        existing_spec = m.group(0)
        tail = line[len(existing_spec):]
        new_lines.append(f"{self.package_name}=={version}{tail}")
        found = True
      else:
        new_lines.append(line)
    if not found:
      new_lines.append(f"{self.package_name}=={version}\n")
    with open(p, "wt") as f:
      print(f"Updating {p}")
      f.writelines(new_lines)
