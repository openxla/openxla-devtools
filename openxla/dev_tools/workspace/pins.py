# Copyright 2023 The OpenXLA Authors
#
# Licensed under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

SYNC_DEPS_FILENAME = "sync_deps.py"
ORIGINS_NAME = "ORIGINS"
PIN_DICT_NAME = "PINNED_VERSIONS"
SUBMODULES_NAME = "SUBMODULES"

from typing import Dict

import importlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Optional

from . import git
from . import repos
from . import types
from . import workspace_meta


def update(ws: types.WorkspaceMeta,
           repo: types.RepoInfo,
           repo_top: Path,
           *,
           require_upstream: bool = False):
  if not repo.deps:
    print(f"Repository {repo.name} has no tracked dependencies. Doing nothing.")
    return

  def callback(pinned_versions, origins, submodules) -> bool:
    # Process dependencies.
    for dep_name in repo.deps:
      print(f"Processing dep {dep_name}")
      dep_repo = types.ALL_REPOS[dep_name]
      summary = update_dep(ws,
                           pinned_versions,
                           repo,
                           dep_repo,
                           require_upstream=require_upstream)
      print(f"  {summary}")
      origins[dep_name] = dep_repo.ro_url
      if dep_repo.submodules:
        submodules[dep_name] = 1
    return True  # Write new file

  process_pin_file(repo_top, callback)


def update_dep(ws: types.WorkspaceMeta, pin_dict: dict, repo: types.RepoInfo,
               dep_repo: types.RepoInfo, *, require_upstream: bool) -> str:
  dep_dir = dep_repo.dir(ws, validate=True)
  head_revision = git.revparse(dep_dir, "HEAD")
  pin_dict[dep_repo.name] = head_revision
  summary = git.format_ref(dep_dir, head_revision)

  # Validate that it is on the tracking branch.
  if require_upstream:
    git.fetch(dep_dir, "origin")
    containing_branches = git.remote_branches_containing(dep_dir, head_revision)
    tracking_branch = f"origin/{dep_repo.tracking_branch}"
    if tracking_branch not in containing_branches:
      raise types.CLIError(
          f"ERROR: Revision not found on remote tracking branch "
          f"{tracking_branch} (found on {containing_branches})")
    else:
      print("  Validated that revision is on upstream tracking branch")
  return f"{dep_repo.name}: {summary}"


def sync(ws: types.WorkspaceMeta,
         repo: types.RepoInfo,
         repo_top: Path,
         *,
         updated_heads: Dict[str, str] = None):
  pins = read_existing_pins(repo_top)
  if updated_heads is None:
    updated_heads = {}
  for dep_name in repo.deps:
    if dep_name in updated_heads:
      print(f"Skipping duplicate dep in dag: {dep_name}")
      continue
    if dep_name not in pins:
      print(f"WARNING: No pinned revision for {dep_name}. Skipping")
      continue
    dep_revision = pins[dep_name]
    updated_heads[dep_name] = dep_revision
    print(f"Syncing dep {dep_name} to {dep_revision}")
    dep_repo = types.ALL_REPOS[dep_name]
    dep_dir = dep_repo.dir(ws)
    current_revision = git.revparse(dep_dir, "HEAD")
    if current_revision == dep_revision:
      print("  Already at needed revision.")
    else:
      git.fetch(dep_dir)
      git.checkout_revision(dep_dir, dep_revision)
      if dep_repo.submodules:
        git.init_submodules(dep_dir)

    # Recurse.
    sync(ws, dep_repo, dep_dir, updated_heads=updated_heads)


def set_pin_revision(repo_top: Path, dep_name: str, revision: str) -> bool:

  def callback(pinned_versions, origins, submodules):
    if dep_name not in pinned_versions:
      raise types.CLIError(
          f"Cannot update pin for {dep_name} because it is not in the "
          f"version file")
    if pinned_versions[dep_name] == revision:
      return False
    pinned_versions[dep_name] = revision
    return True

  return process_pin_file(repo_top, callback)


def process_pin_file(repo_top: Path, callback) -> bool:
  pin_file = repo_top / SYNC_DEPS_FILENAME
  if not pin_file.exists():
    pinned_versions = {}
    origins = {}
    submodules = {}
  else:
    # Import the module anonymously.
    orig_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # Don't generate __pycache__ dir
    try:
      spec = importlib.util.spec_from_file_location("sync_deps__anon",
                                                    str(pin_file))
      if not spec or not spec.loader:
        return None
      m = importlib.util.module_from_spec(spec)
      spec.loader.exec_module(m)
    finally:
      sys.dont_write_bytecode = orig_dont_write_bytecode
    pinned_versions = getattr(m, PIN_DICT_NAME, {})
    origins = getattr(m, ORIGINS_NAME, {})
    submodules = getattr(m, SUBMODULES_NAME, {})

  if callback(pinned_versions=pinned_versions,
              origins=origins,
              submodules=submodules):
    # Write new one.
    with open(pin_file, "wt") as f:
      f.write("#!/usr/bin/env python\n")
      f.write("### AUTO-GENERATED: DO NOT EDIT\n")
      f.write("### Casual developers and CI bots invoke this to do the most\n")
      f.write("### efficient checkout of dependencies.\n")
      f.write("### Cross-repo project development should use the \n")
      f.write(
          "### 'openxla-workspace' dev tool for more full featured setup.\n")
      f.write("### Update with: openxla-workspace pin\n\n")
      f.write(f"{PIN_DICT_NAME} = {json.dumps(pinned_versions, indent=2)}\n\n")
      f.write(f"ORIGINS = {json.dumps(origins, indent=2)}\n\n")
      f.write(f"SUBMODULES = {json.dumps(submodules, indent=2)}\n\n")
      f.write("\n\n### Update support:")
      f.write(SYNC_DEPS_PY)
    return True
  else:
    return False


def read_existing_pins(repo_top: Path) -> Dict[str, str]:
  results = {}

  def callback(pinned_versions, origins, submodules):
    results.update(pinned_versions)

  process_pin_file(repo_top, callback=callback)
  return results


SYNC_DEPS_PY = r"""

import argparse
from pathlib import Path
import re
import shlex
import subprocess


def main():
  parser = argparse.ArgumentParser(description="Source deps sync")
  parser.add_argument(
      "--exclude-submodule",
      nargs="*",
      help="Exclude submodules by regex (relative to '{project}:{path})")
  parser.add_argument("--exclude-dep",
                      nargs="*",
                      help="Excludes dependencies by regex")
  args = parser.parse_args()

  workspace_dir = Path(__file__).resolve().parent.parent
  for repo_name, revision in PINNED_VERSIONS.items():
    # Exclude this dep?
    exclude_repo = False
    for exclude_pattern in (args.exclude_dep or ()):
      if re.search(exclude_pattern, repo_name):
        exclude_repo = True
    if exclude_repo:
      print(f"Excluding {repo_name} based on --exclude-dep")
      continue

    print(f"Syncing {repo_name}")
    repo_dir = workspace_dir / repo_name
    if not repo_dir.exists():
      # Shallow clone
      print(f"  Cloning {repo_name}...")
      repo_dir.mkdir()
      run(["init"], repo_dir)
      run(["remote", "add", "origin", ORIGINS[repo_name]], repo_dir)
    # Checkout detached head.
    run(["fetch", "--depth=1", "origin", revision], repo_dir)
    run(["-c", "advice.detachedHead=false", "checkout", revision], repo_dir)
    if SUBMODULES.get(repo_name):
      print(f"  Initializing submodules for {repo_name}")
      run(["submodule", "init"], repo_dir)
      cp = run(["submodule", "status"],
               repo_dir,
               silent=True,
               capture_output=True)
      for submodule_status_line in cp.stdout.decode().splitlines():
        submodule_status_parts = submodule_status_line.split()
        submodule_path = submodule_status_parts[1]
        exclude_submodule = False
        for exclude_pattern in (args.exclude_submodule or ()):
          if re.search(exclude_pattern, f"{repo_name}:{submodule_path}"):
            exclude_submodule = True
        if exclude_submodule:
          print(f"  Excluding {submodule_path} based on --exclude-submodule")
          continue

        print(f"  Updating submodule {submodule_path}")
        run([
            "submodule", "update", "--depth", "1", "--recommend-shallow", "--",
            submodule_path
        ], repo_dir)


def run(args,
        cwd,
        *,
        capture_output: bool = False,
        check: bool = True,
        silent: bool = False):
  args = ["git"] + args
  args_text = ' '.join([shlex.quote(arg) for arg in args])
  if not silent:
    print(f"  [{cwd}]$ {args_text}")
  cp = subprocess.run(args, cwd=str(cwd), capture_output=capture_output)
  if check and cp.returncode != 0:
    addl_info = f":\n({cp.stderr.decode()})" if capture_output else ""
    raise RuntimeError(f"Git command failed: {args_text} (from {cwd})"
                       f"{addl_info}")
  return cp


if __name__ == "__main__":
  main()
"""
