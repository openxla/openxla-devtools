# Copyright 2023 The OpenXLA Authors
#
# Licensed under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

SYNC_DEPS_FILENAME = "sync_deps.py"
PIN_DICT_NAME = "PINNED_VERSIONS"

from typing import Dict

import importlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Optional

from . import git
from . import repos
from . import utils
from . import workspace_meta


def update(ws: workspace_meta.WorkspaceMeta,
           repo: repos.RepoInfo,
           repo_top: Path,
           *,
           require_upstream: bool = False):
  if not repo.deps:
    print(f"Repository {repo.name} has no tracked dependencies. Doing nothing.")
    return

  # Get the existing one.
  pin_dict = read_existing_pins(repo_top)
  if pin_dict is None:
    print(f"Existing {SYNC_DEPS_FILENAME} not found (will generate)")
    pin_dict = {}
    existing = False
  else:
    existing = True

  # Process dependencies.
  origins = {}
  submodules = {}
  summaries = []
  for dep_name in repo.deps:
    print(f"Processing dep {dep_name}")
    dep_repo = repos.ALL_REPOS[dep_name]
    summary = update_dep(ws,
                         pin_dict,
                         repo,
                         dep_repo,
                         require_upstream=require_upstream)
    print(f"  {summary}")
    summaries.append(summary)
    origins[dep_name] = dep_repo.ro_url
    if dep_repo.submodules:
      submodules[dep_name] = 1

  # Write new one.
  pin_file = repo_top / SYNC_DEPS_FILENAME
  print(f"Updating {pin_file}")
  with open(pin_file, "wt") as f:
    f.write("#!/usr/bin/env python\n")
    f.write("### AUTO-GENERATED: DO NOT EDIT\n")
    f.write("### Casual developers and CI bots invoke this to do the most\n")
    f.write("### efficient checkout of dependencies.\n")
    f.write("### Cross-repo project development should use the \n")
    f.write("### 'openxla-workspace' dev tool for more full featured setup.\n")
    f.write("### Update with: openxla-workspace pin\n\n")
    for s in summaries:
      f.write(f"# {s}\n")
    f.write("\n")
    f.write(f"{PIN_DICT_NAME} = {json.dumps(pin_dict, indent=2)}\n\n")
    f.write(f"ORIGINS = {json.dumps(origins, indent=2)}\n\n")
    f.write(f"SUBMODULES = {json.dumps(submodules, indent=2)}\n\n")
    f.write("\n\n### Update support:")
    f.write(SYNC_DEPS_PY)


def update_dep(ws: workspace_meta.WorkspaceMeta, pin_dict: dict,
               repo: repos.RepoInfo, dep_repo: repos.RepoInfo, *,
               require_upstream: bool) -> str:
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
      raise utils.CLIError(
          f"ERROR: Revision not found on remote tracking branch "
          f"{tracking_branch} (found on {containing_branches})")
    else:
      print("  Validated that revision is on upstream tracking branch")
  return f"{dep_repo.name}: {summary}"


def sync(ws: workspace_meta.WorkspaceMeta,
         repo: repos.RepoInfo,
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
    dep_repo = repos.ALL_REPOS[dep_name]
    dep_dir = dep_repo.dir(ws)
    current_revision = git.revparse(dep_dir, "HEAD")
    if current_revision == dep_revision:
      print("  Already at needed revision.")
    else:
      git.checkout_revision(dep_dir, dep_revision)

    # Recurse.
    sync(ws, dep_repo, dep_dir, updated_heads=updated_heads)


def read_existing_pins(repo_top: Path) -> Optional[dict]:
  pin_file = repo_top / SYNC_DEPS_FILENAME
  if not pin_file.exists():
    return None

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
  return getattr(m, PIN_DICT_NAME, None)


SYNC_DEPS_PY = r"""

from pathlib import Path
import shlex
import subprocess

def main():
  workspace_dir = Path(__file__).resolve().parent.parent
  for repo_name, revision in PINNED_VERSIONS.items():
    repo_dir = workspace_dir / repo_name
    if not repo_dir.exists():
      # Shallow clone
      print(f"Cloning {repo_name}...")
      repo_dir.mkdir()
      run(["init"], repo_dir)
      run(["remote", "add", "origin", ORIGINS[repo_name]], repo_dir)
    # Checkout detached head.
    run(["fetch", "--depth=1", "origin", revision], repo_dir)
    run(["-c", "advice.detachedHead=false", "checkout", revision], repo_dir)
    if SUBMODULES.get(repo_name):
      print(f"Initializing submodules for {repo_name}")
      run(["submodule", "update", "--init", "--depth", "1",
           "--recommend-shallow"], repo_dir)


def run(args,
        cwd,
        *,
        capture_output: bool = False,
        check: bool = True,
        silent: bool = False):
  args = ["git"] + args
  args_text = ' '.join([shlex.quote(arg) for arg in args])
  if not silent:
    print(f"[{cwd}]$ {args_text}")
  cp = subprocess.run(args, cwd=str(cwd), capture_output=capture_output)
  if check and cp.returncode != 0:
    addl_info = f":\n({cp.stderr.decode()})" if capture_output else ""
    raise RuntimeError(f"Git command failed: {args_text} (from {cwd})"
                       f"{addl_info}")
  return cp


if __name__ == "__main__":
  main()
"""
