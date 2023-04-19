# Copyright 2023 The OpenXLA Authors
#
# Licensed under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

from pathlib import Path
import os
import subprocess
import unittest
import sys
import tempfile


def run(args, cwd) -> subprocess.CompletedProcess:
  if not cwd:
    cwd = Path.cwd()
  new_env = dict(os.environ)
  new_env["PYTHONPATH"] = Path(__file__).resolve().parent
  cp = subprocess.run([sys.executable, "-m", "openxla.devtools.workspace"] +
                      args,
                      env=new_env,
                      capture_output=True,
                      text=True,
                      cwd=str(cwd))
  print(f"Executed ({cwd}): {' '.join(args)} (rc {cp.returncode})")
  print(f"---\nSTDOUT:\n{cp.stdout}\n")
  print(f"---\nSTDERR:\n{cp.stderr}\n")
  print(f"---")
  return cp


class TestWorkspaceInit(unittest.TestCase):

  def testInit(self):
    with tempfile.TemporaryDirectory() as d:
      cp = run(["init"], cwd=d)
      cp.check_returncode()
      self.assertEqual(cp.stdout.strip(), f"Initialized workspace at: {d}")
      subdir = Path(d) / "sub"
      subdir.mkdir()
      cp = run(["init"], cwd=subdir)
      self.assertEqual(cp.stdout.strip(),
                       f"Running within existing workspace: {d}")
      cp.check_returncode()

  def testCheckoutNotFound(self):
    with tempfile.TemporaryDirectory() as d:
      run(["init"], cwd=d).check_returncode()
      cp = run(["checkout", "not-found"], cwd=d)
      self.assertNotEqual(cp.returncode, 0)
      self.assertIn("No repository matching", cp.stderr)

  # TODO: More checkout tests once ok with some expensive ones.
  def testCheckoutLeaf(self):
    with tempfile.TemporaryDirectory() as d:
      run(["init"], cwd=d).check_returncode()
      cp = run(["checkout", "xla"], cwd=d)
      cp.check_returncode()


if __name__ == "__main__":
  unittest.main()
