# Copyright 2023 The OpenXLA Authors
#
# Licensed under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

from typing import List, Optional

from pathlib import Path
import shlex
import subprocess

from . import utils


def clone(repo_url: str, d: Path):
  run(["clone", repo_url, str(d)], capture_coutput=False)


def init_submodules(d: Path):
  run(["submodule", "update", "--init", "--depth", "1", "--recommend-shallow"],
      d,
      capture_coutput=False)


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


def run(args,
        cwd=None,
        *,
        capture_coutput: bool = True,
        check: bool = True,
        silent: bool = False):
  if not cwd:
    cwd = Path.cwd()
  args = ["git"] + args
  args_text = ' '.join([shlex.quote(arg) for arg in args])
  if not silent:
    print(f"[{cwd}]$ {args_text}")
  cp = subprocess.run(args, cwd=str(cwd), capture_output=capture_coutput)
  if check and cp.returncode != 0:
    addl_info = f":\n({cp.stderr})" if capture_coutput else ""
    raise utils.CLIError(f"Git command failed: {args_text} (from {cwd})"
                         f"{addl_info}")
  return cp
