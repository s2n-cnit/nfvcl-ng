# Building the documentation locally

The documentation is built with [Sphinx](https://www.sphinx-doc.org/) from
the `docs/source` directory. The supported local workflow uses `uv` and the
documentation dependency group declared in `pyproject.toml`.

## Prerequisites

- Install `uv`.
- Use Python 3.14, as required by the project.
- Run the commands below from the repository root.

## Install documentation dependencies

Synchronize the project environment, including the documentation tools:

```bash
uv sync --group docs
```

## Build the HTML documentation

Build the site into `docs/build/html`:

```bash
uv run --group docs sphinx-build -b html docs/source docs/build/html
```

To audit warnings while working on the documentation, optionally treat all
Sphinx warnings as errors:

```bash
uv run --group docs sphinx-build -W -b html docs/source docs/build/html
```

Open `docs/build/html/index.html` in a browser after the build completes.
Alternatively, serve the generated site locally:

```bash
python -m http.server --directory docs/build/html 8000
```

Then browse to <http://localhost:8000>.

## Read the Docs

Read the Docs uses `.readthedocs.yaml`. It selects Python 3.14, installs the
requirements in `docs/source/sphinx_requirements.txt`, and installs the
repository package so autodoc can import the complete `src` API tree. The
configuration mocks infrastructure-only imports in `docs/source/conf.py`, so
the hosted build does not need OpenStack, Kubernetes, or Proxmox services.

After changing the documentation dependencies or the source package metadata,
run the local build above and trigger a Read the Docs rebuild from the project
dashboard.

## Regenerate API reference pages

The complete API reference is generated from every Python module under
``src``. Regenerate it after adding or moving source modules:

```bash
uv run --group docs sphinx-apidoc --force --separate --module-first --no-toc \
  -o docs/source/api/source src
```

Run the normal HTML build again after regeneration. The API pages use mocked
infrastructure dependencies configured in `docs/source/conf.py`, so building
the documentation does not require a running OpenStack or Kubernetes cluster.

The strict command is useful for investigating new warnings, but the current
generated API reference and some older pages contain known import, duplicate
object, and cross-reference warnings. The normal command is therefore the
supported local build check until those existing warnings are cleaned up.

## Troubleshooting

- Run commands from the repository root so Sphinx can resolve the configured
  source and output paths.
- If `sphinx-build` is not found, run `uv sync --group docs` and use the
  `uv run --group docs ...` form above.
- A strict build fails on warnings; fix missing references, files, or
  formatting rather than omitting `-W`.