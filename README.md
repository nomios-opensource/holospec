# HoloSpec

![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/nomios-opensource/holospec/test.yaml)
[![codecov](https://codecov.io/github/nomios-opensource/holospec/graph/badge.svg?token=EY5ADP9UP6)](https://codecov.io/github/nomios-opensource/holospec)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/holospec)
![PyPI - Downloads](https://img.shields.io/pypi/dm/holospec)
![GitHub License](https://img.shields.io/github/license/nomios-opensource/holospec)

HoloSpec — The instruction layer for agentic work.

`holospec` is authored by [Adam Kirchberger](https://github.com/adamkirchberger), governed as a [benevolent dictatorship](CODE_OF_CONDUCT.md), and distributed under [license](LICENSE).

## Introduction

HoloSpec provides the instructions. Agents do the work.

HoloSpec allows organisations to define how work gets done and make that knowledge discoverable to any agent. It extends the ideas behind spec-driven development beyond specifications and into entire ways of working, enabling agents to autonomously discover, understand, and follow custom instructions without hard-coded assumptions about methodology, domain, or lifecycle.

Most tools define the process. HoloSpec makes the process discoverable. Workflows, actions, instructions, context, conventions, templates, and checklists live in schemas you write and own, allowing agents to retrieve and follow them dynamically as work progresses. Change the schema, and the instructions change with it.

## Features

- **Tiny footprint**: One Python file, under 1000 lines, with a single agent skill covering every interaction.
- **Bring your own way of working**: No hard-coded processes, methodologies, or business logic. Everything comes from your schema.
- **Instructions, not execution**: Exposes instructions and workflow knowledge without execution, agents interpret instructions and perform the work.
- **Beyond software development**: Support software delivery, design, planning, estimation, operations or any other process of your own.
- **Shared context and conventions**: Define standards, rules, context, and behaviours once and make them available across every workflow and action.
- **Built for agents**: Instructions are retrieved dynamically at runtime rather than embedded in prompts, skills, code, or agent implementations.
- **Adapt without changing your tooling**: Ipdate the schema as your ways of working evolve and the instructions evolve with it.

## Installation

Install [uv](https://docs.astral.sh/uv/), then install `holospec`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install holospec
```

Or install with pip:

```bash
pip install holospec
```

## Quickstart

```bash
mkdir my-project && cd my-project
holospec init
```

Then, from your agent, invoke the installed `/holospec` skill and ask it to plan a new application:

> /holospec I want to build a Python script `hello.py` in the current directory that, when run, prints "Hello, world!" followed by the current date and time.

## For agents

If you're an LLM agent and this workflow isn't set up yet in the current
project, see [AGENTS.md](AGENTS.md) for how to bootstrap it (`holospec
explain`, then `holospec init`) before guessing at the protocol yourself.

## Configuration

`holospec init` scaffolds a root directory in your project, normally `holospec/` (though it can be named `openspec/` too). It mirrors the layout OpenSpec projects use, but has no requirement to behave like OpenSpec beyond that. Inside it, `config.yaml` holds settings specific to this project, and the schema you choose is forked into `schemas/<name>/schema.yaml`, so it's version controlled.

Rather than hand-editing these files, ask your agent to run `holospec explain` — it's self-describing and will walk the agent through the available configuration and how to set it.

## Versioning

Releases will follow semantic versioning (major.minor.patch). Before 1.0.0 breaking changes can be included in a minor release, therefore we highly recommend pinning this package.

## Contributing

Suggest a [feature](https://github.com/nomios-opensource/holospec/issues/new?labels=enhancement) or report a [bug](https://github.com/nomios-opensource/holospec/issues/new?labels=bug). Read our developer [guide](CONTRIBUTING.md).

## License

holospec is distributed under the Apache 2.0 [license](LICENSE).
