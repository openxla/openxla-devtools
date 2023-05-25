# Copyright 2023 The OpenXLA Authors
#
# Licensed under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

from typing import List, Optional, Sequence

from pathlib import Path
import shlex
import subprocess


def clone(repo_url: str, d: Path):
  run(["clone", repo_url, str(d)], capture_output=False)


def list_submodules(d: Path):
  results = []
  cp = run(["submodule", "status"], d, silent=True, capture_output=True)
  for submodule_status_line in cp.stdout.decode().splitlines():
    submodule_status_parts = submodule_status_line.split()
    results.append(submodule_status_parts[1])
  return results


def update_submodules(d: Path, submodules: Sequence[str], *, depth: int = 0):
  args = ["submodule", "update", "--init"]
  if depth > 0:
    args.extend(["--depth", "1"])
  args.extend(["--"])
  args.extend(submodules)
  run(args, d, capture_output=False)


def fetch(d: Path, remote: str = "origin"):
  run(["fetch", remote], d, silent=True)


def remote_branches_containing(d: Path, ref: str) -> List[str]:
  cp = run(["branch", "-r", "--contains", ref], d, silent=True, check=True)
  results = cp.stdout.decode().splitlines()
  return [r.strip() for r in results]


def revparse(d: Path, *args) -> str:
  cp = run(["rev-parse"] + list(args), d, silent=True, check=True)
  return cp.stdout.decode().strip()


def toplevel(d: Path) -> Optional[Path]:
  cp = run(["rev-parse", "--show-toplevel"], d, silent=True, check=False)
  if cp.returncode != 0:
    return None
  return Path(cp.stdout.decode().strip()).resolve()


def format_ref(d: Path, ref: str) -> str:
  cp = run(["show", "--quiet", "--format=format:%h %ci : %s", ref],
           d,
           silent=True,
           check=True)
  return cp.stdout.decode().strip()


def checkout_revision(d: Path, ref: str):
  run(["checkout", "--detach", ref], d)


def get_remote_head(url: str, branch: str) -> str:
  cp = run(["ls-remote", "--heads", url, branch], silent=True, check=True)
  lines = cp.stdout.decode().splitlines()
  if len(lines) != 1:
    raise GitError(f"ls-remote returned multiple results for {url} {branch}")
  line = lines[0]
  comps = line.split()
  if len(comps) < 1:
    raise GitError(f"ls-remote returned malformed output")
  return comps[0]


def show_file(d: Path, *, ref: str, path: str) -> bytes:
  cp = run(["show", f"{ref}:{path}"], d, check=True, capture_output=True)
  return cp.stdout


def run(args,
        cwd=None,
        *,
        capture_output: bool = True,
        check: bool = True,
        silent: bool = False):
  if not cwd:
    cwd = Path.cwd()
  args = ["git"] + args
  args_text = ' '.join([shlex.quote(arg) for arg in args])
  if not silent:
    print(f"[{cwd}]$ {args_text}")
  cp = subprocess.run(args, cwd=str(cwd), capture_output=capture_output)
  if check and cp.returncode != 0:
    addl_info = f":\n({cp.stderr})" if capture_output else ""
    raise GitError(f"Git command failed: {args_text} (from {cwd})"
                   f"{addl_info}")
  return cp


class GitError(Exception):
  ...
