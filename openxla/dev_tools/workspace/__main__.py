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
from . import roller
from . import workspace_meta
from . import types


def parse_arguments():
  parser = argparse.ArgumentParser(description="OpenXLA Workspace Tool")
  subparsers = parser.add_subparsers(help="sub-command help",
                                     required=True,
                                     dest="sub_command")

  # 'checkout' sub-command
  checkout_parser = subparsers.add_parser("checkout",
                                          help="Checkout a repository")
  checkout_parser.add_argument("--sync",
                               action="store_true",
                               help="Sync deps as repositories are checked out")
  checkout_parser.add_argument("--no-submodules",
                               action="store_true",
                               help="Disables all submodule updates")
  checkout_parser.add_argument("--no-deps",
                               action="store_true",
                               help="Disables checkout of dependencies")
  checkout_parser.add_argument(
      "--ro",
      action="store_true",
      help="Clones repositories using the 'ro' (http) origins")
  checkout_parser.add_argument("repo_name", nargs="+")

  # 'init' sub-command
  init_parser = subparsers.add_parser(
      "init", help="Initialize (or re-initialize) a workspace")

  # 'pin' sub-command
  pin_parser = subparsers.add_parser("pin",
                                     help="Pin deps to current revisions")
  pin_parser.add_argument("--require-upstream", action="store_true")

  # 'roll' sub-command
  roll_parser = subparsers.add_parser(
      "roll",
      help="Apply a dependency rolling schedule and make corresponding updates")
  roll_parser.add_argument("schedule", help="Name of the schedule to apply")

  # 'sync' sub-command
  sync_parser = subparsers.add_parser(
      "sync",
      help=
      "Sync all dependent repositories to pinned deps of the current repository"
  )

  args = parser.parse_args()
  return args


def do_checkout(args):
  ws = workspace_meta.find_required()
  repo_names = args.repo_name
  updated_heads = dict()
  for repo_name in repo_names:
    r = repos.find_required(repo_name)
    repos.checkout(ws,
                   r,
                   submodules=not args.no_submodules,
                   checkout_deps=not args.no_deps,
                   rw=not args.ro)
    if args.sync:
      pins.sync(ws, r, r.dir(ws), updated_heads=updated_heads)


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


def do_roll(args):
  ws, r, toplevel = repos.get_from_dir(Path.cwd())
  schedule_name = args.schedule
  if not r.rolling_schedules:
    raise types.CLIError(f"Repository {r.name} has no rolling schedules")
  try:
    actions = r.rolling_schedules[schedule_name]
  except KeyError:
    raise types.CLIError(f"Unknown schedule '{schedule_name}' for {r.name}. "
                         f"Available: {', '.join(r.rolling_schedules.keys())}")
  for action in actions:
    print(f"Performing rolling action: {str(action)}")
    action.update(ws, r)


def do_sync(args):
  ws, r, toplevel = repos.get_from_dir(Path.cwd())
  pins.sync(ws, r, toplevel)


def main():
  args = parse_arguments()
  try:
    if args.sub_command == "checkout":
      do_checkout(args)
    elif args.sub_command == "init":
      do_init(args)
    elif args.sub_command == "pin":
      do_pin(args)
    elif args.sub_command == "roll":
      do_roll(args)
    elif args.sub_command == "sync":
      do_sync(args)
    else:
      raise types.CLIError(f"Unrecognized sub command {args.sub_command}")
  except types.CLIError as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
  main()
