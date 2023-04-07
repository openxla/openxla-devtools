# OpenXLA Development Tools

This repository contains a Python package providing development tools
that span the OpenXLA suite of projects under the [openxla org](https://github.com/openxla).

It is primarily intended to be installed by developers. In everyday use,
it should not be necessary to actual modify the tools themselves.

## Installing the tools

```
pip install git+https://github.com/stellaraccident/openxla-dev-tools.git
```

## openxla-workspace User's Guide

The `openxla-workspace` command is used to:

* Setup and maintain an "OpenXLA workspace" (collection of individual project
  repositories).
* Checkout individual project repositories.
* Sync repositories to pinned versions.
* Update pinned version.

Quick start to create an openxla repository and start developing:

```
mkdir ~/openxla
cd ~/openxla
openxla-workspace init
openxla-workspace checkout --sync openxla-pjrt-plugin
```

The above will initialize a new workspace and checkout the `openxla-pjrt-plugin`
plus its dependencies, syncing to the dependency version pins that the project
specifies. There is nothing special about this project except that it is a
leaf project and illustrates dependency resolution.

The `--sync` option tells checkout to behave as if the `sync` command was
run on the checked out repository. This has the effect of checking out the
pinned revisions of all deps recursively.

### Manually updating version pins

NOTE: Some projects manage their dependencies via submodules. Such cases are
not covered here (just use normal `git` tools).

If a project depends on other OpenXLA projects, it expresses these dependencies
via `sync_deps.py` script in the root of its repository. This script is both
importable (in order to get programmatic access to dependencies) and runnable
(so that end-developers and CI systems have the simplest possible mechanism
to check everything out needed to build the project).

When it is time to update the pins in this file, bring the dependencies of
interest to the desired commit (and land it in the corresponding dependency
repo). Then, from the project to be updated, run `openxla-workspace pin`.

Example:

```
cd ~/openxla/openxla-pjrt-plugin
openxla-workspace pin --require-upstream
```

Note that the `--require-upstream` flag enables an (expensive) safety check
to ensure that the chosen commits are on the appropriate upstream tracking
branch.

This will overwrite the `sync_deps.py` script with a new version. Creating a
PR in the repo with changes to this file will trigger the CI to validate the
chosen commits.

This same basic procedure will be applied by automation which periodically
moves all dependencies forward when there are no build/test issues.

### Rolling dependencies

A repository may be configured to have dependency rolling schedules. These
schedules can be invoked by both humans and automation to bump dependencies
according to different policies.

Typically, a repository will define two schedules (if it has any):

* `continuous`: Makes "inter-day" updates to core dependencies. Used to
  integrate rapidly changing deps automatically.
* `nightly`: Makes "once per day" updates to all dependencies. These can be
  done multiple times per day if desired but typically this involves "big
  jumps". Usually this schedule will be responsible for updating pinned
  binaries (i.e. pip packages) and such as well (which may be derived from
  nightly releases).

Once dependencies are rolled, `sync` must be performed and any project specific
steps for upgrading packages.

Invoke a dependency roll with a command like this:

```
cd ~/openxla/openxla-pjrt-plugin
openxla-workspace roll nightly
```
