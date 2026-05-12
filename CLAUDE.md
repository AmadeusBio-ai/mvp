# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

AmadeusBio.ai is a **Claude Code plugin for bioinformatics**, not an application. The repo ships three kinds of artifact, all consumed by a coding agent rather than compiled or run as a service:

- **Subagents** (`agents/*.md`) — markdown definitions with YAML frontmatter (`name`, `description`, `model`, `color`) that Claude Code loads as specialized agents.
- **Skills** (`skills/<name>/SKILL.md` plus optional `scripts/` and `references/`) — on-demand reference manuals that a subagent reads when it needs deeper detail than its own definition contains.
- **A PyMOL-side plugin** (`pymol-mcp-socket-plugin/__init__.py` + `.ui`) — installed *inside* PyMOL via its Plugin Manager, not run from this repo. It opens a TCP server on `localhost:9876` and `exec()`s whatever Python it receives.

There is no build, lint, or test step. Changes are pure markdown/Python edits; validation is "load the skill in Claude Code and try the workflow."

## The PyMOL bridge — the load-bearing piece

The PyMOL workflow is the part of this repo most likely to bite you. Read `skills/pymol-molecular-visualization/SKILL.md` and the matching subagent definition (`skills/pymol-molecular-visualization/PyMol-Software-Operator.md`) before touching anything PyMOL-related. The architecture is:

```
Claude Code subagent
   └─ shells out to scripts/pymol_send.py  ──TCP localhost:9876──▶  PyMOL MCP Socket Plugin
                                                                       └─ exec()s code, returns stdout or _result
```

Two rules are non-negotiable and are enforced both in the helper script and in the subagent prompt:

1. **`cmd.reinitialize` is blocked.** It hard-crashes the plugin. Use `cmd.delete('all')` to clear state. `pymol_send.py` rejects any payload containing the string before it touches the socket.
2. **`cmd.fetch` must pass `async_=0`.** The default returns before the download finishes, so the next command silently runs against a missing object. The `pymol_send.py --fetch-pdb` convenience sets this automatically.

Returning values: side-effect calls (`cmd.show`, `cmd.png`) emit no stdout, so the plugin falls back to reading a local variable named `_result` and returns `str(_result)`. Use `_result` when the caller needs a value; use `print(...)` for progress lines. Don't mix them — `_result` is only consulted when stdout is empty.

Silent errors: PyMOL prints many error messages to stdout *without raising* (selection typos, missing objects, file errors). The helper scans output against `SILENT_ERROR_PATTERNS` and emits `WARNING:` on stderr — always check stderr in addition to exit code (`0` success, `1` PyMOL/exec error, `2` connection/transport error).

State is persistent across sends — every `pymol_send.py` invocation hits the same long-running PyMOL process. `cmd.delete('all')` before starting an unrelated task or you'll leak leftover objects, colors, and reps into the next figure.

## Two subagent definitions for PyMOL — pick the right one

There are two `PyMol-Software-Operator.md` files. They are **not** identical:

- `skills/pymol-molecular-visualization/PyMol-Software-Operator.md` — source of truth. References `pymol_send.py` + `pymol_launch.py` (the actual scripts that exist).
- `agents/PyMol-Software-Operator.md` — older/shorter copy that references a `pymol_safe_load.py` script which does **not** exist in this repo. Treat this one as stale and edit it to match the skill-dir version if you touch it.

## Launching PyMOL

`scripts/pymol_launch.py` is a no-op when something is already listening on `localhost:9876`, otherwise it spawns `pymol -d "mcp_start"` detached. Exit codes: `0` ready, `1` PyMOL installed but the MCP plugin didn't autostart (user must open PyMOL and type `mcp_start` in the command bar), `2` no `pymol` binary on `PATH`.

On Windows, `pymol` typically means `pyMOLWin.exe`. The expected setup (per `content/docs/PyMolDoc.md`) is a `pymol.bat` wrapper on `PATH`:

```bat
@echo off
pyMOLWin.exe %*
```

## Repo layout

| Path | Purpose |
|------|---------|
| `agents/` | Top-level subagent markdown definitions (currently a stale copy of the PyMOL operator). |
| `skills/<name>/SKILL.md` | Reference manuals for individual skills. Frontmatter must include `name`, `description`, `license`. |
| `skills/<name>/scripts/` | Stdlib-only Python helpers shelled out to by the agent (no `pip install`). |
| `skills/<name>/references/` | Long-form reference material that doesn't fit inside `SKILL.md`. |
| `pymol-mcp-socket-plugin/` | PyMOL-side plugin — installed inside PyMOL via Plugin Manager, not invoked from here. |
| `content/docs/` | Project-level docs (installation, roadmap, website copy). |
| `src/assets/` | Logos (referenced by `README.md`). |

## Skills currently in the repo

- `pymol-molecular-visualization` — drives a live PyMOL session over the socket (see above).
- `alphafold-database-access` — AlphaFold DB REST/BioPython access, pLDDT/PAE analysis, bulk proteome downloads via GCS.
- `uniprot-protein-database` — UniProt REST API: search, FASTA retrieval, ID mapping (Ensembl/PDB/RefSeq), Swiss-Prot annotations.

The skill frontmatter `description` field is what Claude Code matches against — keep it specific and routing-friendly (it should disambiguate from sibling skills, not just describe what the skill is about).

## Conventions when editing skills/agents

- Helper scripts in `skills/*/scripts/` must stay **stdlib only** so they run without `pip install`.
- Use **absolute paths** for PyMOL outputs (`cmd.png`, `cmd.save`) — PyMOL's CWD is wherever the GUI was launched from, not the agent's CWD.
- When adding a recipe to a `SKILL.md`, send commands **one logical step at a time during validation**, then combine. PyMOL's `exec()` runs the whole blob in one shot, and the first failing line aborts the rest with a hard-to-read traceback.
- Frontmatter `description` fields should explicitly call out when a sibling skill (e.g. `biopython-molecular-biology` for headless analysis, `pdb-database` for experimental structures) is the better choice — these routing hints are how the agent picks between overlapping skills.
