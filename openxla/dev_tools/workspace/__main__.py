# Copyright 2023 The OpenXLA Authors
#
# Licensed under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

import argparse
from pathlib import Path
import sys

from . import pins
from . import repos
from . import workspace_meta
from . import utils


def parse_arguments():
  parser = argparse.ArgumentParser(description="OpenXLA Workspace Tool")
  subparsers = parser.add_subparsers(help="sub-command help",
                                     required=True,
                                     dest="sub_command")

  # 'checkout' sub-command
  checkout_parser = subparsers.add_parser("checkout",
                                          help="Checkout a repository")
  checkout_parser.add_argument("repo_name", nargs="+")

  # 'init' sub-command
  init_parser = subparsers.add_parser(
      "init", help="Initialize (or re-initialize) a workspace")

  # 'pin' sub-command
  pin_parser = subparsers.add_parser("pin",
                                     help="Pin deps to current revisions")
  pin_parser.add_argument("--require-upstream", action="store_true")

  args = parser.parse_args()
  return args


def do_checkout(args):
  ws = workspace_meta.find_required()
  repo_names = args.repo_name
  for repo_name in repo_names:
    r = repos.find_required(repo_name)
    repos.checkout(ws, r)


def do_init(args):
  ws = workspace_meta.find()
  if ws:
    print(f"Running within existing workspace: {ws.dir}")
    return
  else:
    ws = workspace_meta.initialize(Path.cwd())
    print(f"Initialized workspace at: {ws.dir}")


def do_pin(args):
  ws, r, toplevel = repos.get_from_dir(Path.cwd())
  pins.update(ws, r, toplevel, require_upstream=args.require_upstream)

def main():
  args = parse_arguments()
  try:
    if args.sub_command == "checkout":
      do_checkout(args)
    elif args.sub_command == "init":
      do_init(args)
    elif args.sub_command == "pin":
      do_pin(args)
    else:
      raise utils.CLIError(f"Unrecognized sub command {args.sub_command}")
  except utils.CLIError as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
  main()
