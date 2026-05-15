---
name: "pymol-molecular-visualization"
description: "Reference manual for driving a running PyMOL instance via the MCP Socket Plugin (localhost:9876). Covers the cmd.* API surface, selection language, representations (cartoon/sticks/surface), coloring (spectrum/cbc/util.cb*), structural alignment (align/super), measurements (distance/get_distance), scenes, PNG export, and common figure recipes. Consult this file when the PyMol-Software-Operator subagent needs details beyond what its own definition contains. Prefer Bio.PDB or MDAnalysis for headless trajectory/structure analysis without a GUI; use this skill when interactive visualization or publication-quality rendering is the goal."
license: "BSD-3-Clause-like (PyMOL Open-Source); skill content CC-BY-4.0"
---

# PyMOL Molecular Visualization — Reference Manual

> **Purpose.** This file is a reference manual, consulted on demand by the `PyMol-Software-Operator` subagent. The subagent definition holds the always-loaded behavioral rules (launch flow, helper-script invocation, safety catches). This file holds the deeper material: API surface, selection language, parameter tables, recipes, and troubleshooting.

## Overview

PyMOL is the standard tool for interactive molecular visualization, structural alignment, and publication-quality ray-traced rendering of proteins, nucleic acids, and small molecules. This toolkit drives a **running PyMOL GUI session** through the MCP Socket Plugin: a stdlib-only helper script (`scripts/pymol_send.py`) sends arbitrary Python `cmd.*` calls over `localhost:9876`, the plugin `exec()`s the code inside PyMOL, and captured stdout (or a `_result` variable) is returned to the caller. PyMOL is stateful — each call sees prior loads, selections, and view changes.

## When this skill applies

- Loading a PDB structure (`cmd.fetch` by ID, or `cmd.load` for a local file) and producing a styled cartoon/sticks/surface figure
- Rendering a ray-traced PNG for a publication or presentation
- Structurally aligning two proteins (`cmd.align` / `cmd.super`) and reporting RMSD, aligned atom count, and a side-by-side image
- Computing distances, angles, dihedrals, or bounding boxes between selections
- Coloring a structure by chain, secondary structure, B-factor, or a custom expression
- Building and recalling named scenes (`cmd.scene`) to script a multi-panel figure
- Inspecting chains, residues, atom counts, or PDB strings of objects already loaded
- Extracting a sub-structure (e.g. a binding pocket within 5 Å of a ligand) into a new object for downstream rendering

Use `biopython-molecular-biology` or `mdanalysis-trajectory` instead when you need headless structure/trajectory analysis with no GUI; use this skill when the user explicitly wants PyMOL or a rendered image. For docking pose generation, use `autodock-vina-docking` first; visualize the output `.pdbqt`/`.sdf` poses with this skill.

## Prerequisites

- **PyMOL installed and on `PATH`** with the MCP Socket Plugin available. PyMOL is normally launched once per session via `pymol -d "mcp_start"` — the subagent's `pymol_launch.py` helper handles this automatically.
- **Helper scripts**: `scripts/pymol_send.py` and `scripts/pymol_launch.py` bundled with this skill. Stdlib only, no `pip install`.
- **Python**: Any 3.x interpreter for the helpers. On Windows use `py -3`; on macOS/Linux use `python3`. Avoid bare `python` on Windows — it's often the Microsoft Store stub.
- **Network**: The PyMOL plugin binds to `localhost` only. Do not expose port 9876 — the plugin `exec()`s any Python it receives.

In the snippets below, `$PYMOL_SCRIPTS_DIR` is the absolute path to the `scripts/` directory that the subagent resolves on its first task in a session. On Windows, quote the full path because backslashes and spaces are common.

## Two operational rules

These two rules are repeated from the subagent definition because every recipe in this file depends on them:

1. **`cmd.reinitialize` is blocked.** It hard-crashes the plugin. `pymol_send.py` rejects it before sending. Use `cmd.delete('all')` to clear the workspace instead.
2. **`cmd.fetch` calls must pass `async_=0`.** The default returns before the download finishes, so subsequent commands see "object not found." The `--fetch-pdb` convenience subcommand sets this automatically.

## Core API

The plugin's `exec` environment has `cmd` already imported. All snippets below show **the Python you put in `--code` or stdin**, not what runs locally.

### Module 1: Loading structures

```python
# By PDB ID (always async_=0 over the socket).
cmd.fetch('1ubq', 'ubq', async_=0)

# From a local file (path on the machine running PyMOL).
cmd.load('/data/my_model.pdb', 'model')
cmd.load('/data/my_traj.dcd',  'traj', state=1)   # trajectory frame
```

The `pymol_send.py --fetch-pdb <ID> [--name <obj>]` convenience handles the common fetch-and-orient case in one shot — see the subagent definition for the call shape.

### Module 2: Selection language

PyMOL's selection mini-language is the workhorse. Selections can be ad-hoc strings or saved as named selections via `cmd.select`.

```python
# Common operators: chain, resi, resn, name, ss, polymer, organic, solvent,
# byres, within, and/or/not.
cmd.select('binding_pocket', 'byres polymer within 4 of resn HEM')
cmd.select('helices',        'ss H and polymer')
cmd.select('catalytic_triad','(resi 57+102+195) and chain A and name CA')

_result = cmd.count_atoms('binding_pocket')
cmd.deselect()
```

```python
# Iterate residues — write results into a Python list via the local namespace.
residues = []
cmd.iterate('chain A and name CA',
            'residues.append((resi, resn))',
            space={'residues': residues})
_result = residues[:5]   # → [('1', 'MET'), ('2', 'GLN'), ...]
```

### Module 3: Representations (`show_as`, `show`, `hide`)

Prefer `show_as` over `show` + `hide` pairs — it's the only-representation setter and avoids leftover artifacts.

```python
cmd.show_as('cartoon', 'polymer')
cmd.show_as('sticks',  'organic')        # ligands as sticks
cmd.show_as('spheres', 'resn HEM')       # heme as spheres

# Additive modifications.
cmd.show('surface', 'chain A and polymer')
cmd.set('transparency', 0.4, 'chain A')
```

```python
# Common reps: cartoon, sticks, spheres, surface, mesh, lines, ribbon, dots,
# nb_spheres (non-bonded), licorice, putty (cartoon scaled by B-factor).
cmd.show_as('putty', 'polymer')
cmd.set('cartoon_putty_scale_min', 0.1)
cmd.set('cartoon_putty_scale_max', 4.0)
```

### Module 4: Coloring

```python
# Solid color.
cmd.color('skyblue', 'chain A')
cmd.color('salmon',  'chain B')

# Gradient over an expression. expr ∈ {'count', 'b', 'q', 'pc', any cmd.iterate-able expr}.
cmd.spectrum('count', 'rainbow', 'polymer')        # N→C rainbow
cmd.spectrum('b',     'blue_white_red', 'polymer') # color by B-factor
```

```python
# Color-by-chain and color-by-atom helpers.
cmd.util.cbc('all')          # color by chain (carbons differ per chain)
cmd.util.cbaw('organic')     # color by atom, white carbons
cmd.util.cbag('resn HEM')    # green carbons
# Other variants: cbac (cyan), cbam (magenta), cbay (yellow), cbas (salmon),
# cbab (slate), cbao (orange), cbap (purple), cbak (pink).
```

### Module 5: Alignment and measurement

`cmd.align` does sequence-aware alignment + structure superposition. `cmd.super` is sequence-independent (better for distant homologs). Both return a tuple — capture via `_result`.

```python
# Sequence-aware: aligns by residue type first, then superposes by Cα.
cmd.fetch('1crn', 'crn', async_=0)
cmd.fetch('1ejg', 'ejg', async_=0)
_result = cmd.align('ejg', 'crn')
# → (rmsd, n_atoms, n_cycles, rmsd_pre, n_atoms_pre, score, n_residues)
```

```python
# Sequence-independent — use for distant homologs or when align fails.
_result = cmd.super('ejg', 'crn')

# Measurements.
cmd.distance('d1',
             'crn and resi 22 and name CA',
             'crn and resi 25 and name CA')
_result = cmd.get_distance('crn and resi 22 and name CA',
                           'crn and resi 25 and name CA')
# Bounding box: ((xmin,ymin,zmin),(xmax,ymax,zmax)).
_result = cmd.get_extent('polymer')
```

### Module 6: View, scenes, rendering

PyMOL's view is a 3×3 rotation + translation + clipping; persist or restore via `get_view`/`set_view`. Scenes capture the full visualization state under a name.

```python
cmd.orient('polymer')         # auto-orient on principal axes
cmd.zoom('polymer', buffer=5) # tight crop with 5 Å padding
cmd.center('chain A')

_result = cmd.get_view()      # 18-tuple — copy/paste back into cmd.set_view(...)
```

```python
# Scenes capture reps, colors, view, and visibility under a key.
cmd.scene('overview', action='store')
cmd.show_as('surface', 'chain A')
cmd.scene('surface_view', action='store')
cmd.scene('overview',     action='recall')

# Ray-traced PNG. ray=1 forces ray-tracing; dpi controls embedded metadata.
cmd.bg_color('white')
cmd.set('ray_opaque_background', 0)   # transparent background (PNG alpha)
cmd.png('/tmp/figure.png', width=2400, height=1800, ray=1, dpi=300)
```

## Key concepts

### State is persistent across sends

Each `pymol_send.py` invocation reaches into the same long-running PyMOL process. Loads, selections, scenes, view changes — all persist. This is the point of the bridge (you build figures incrementally) but it means you must clean up between unrelated tasks: `cmd.delete('all')` before starting fresh, or new renders inherit leftover objects and reps.

### Reading values back via `_result`

The plugin captures stdout. Side-effect calls (`cmd.show`, `cmd.color`, `cmd.png`) emit nothing, so the helper exits with empty stdout. To return a value to the caller, assign it to a variable named `_result` — the plugin reads that name when stdout is empty and returns `str(_result)`. This is how you branch on chain lists, RMSD values, atom counts, etc.

```python
_result = cmd.get_chains('ubq')      # ['A']
_result = cmd.align('mob', 'tgt')[0] # rmsd as a float
```

### Silent errors

PyMOL frequently prints errors like `Selector-Error: Invalid selection name 'foo'` or `ExecutiveLoad-Error: Unable to open file` to stdout **without raising**. The plugin reports `executed: True` for these, and the helper exits 0. `pymol_send.py` scans output against `SILENT_ERROR_PATTERNS` (selection errors, object-not-found, file errors, parameter errors, syntax errors, fetch errors) and writes a `WARNING:` line to stderr. Always check stderr in addition to the exit code.

## Local structure library (`./structures/`)

This skill is designed around a **canonical local library of pre-curated PDB files** that lives at `./structures/` (relative to the project root). When the user names a protein without a path, **always look here first** — this avoids redundant network fetches, captures organism/family context the user has already curated, and ensures the same exact file is used across runs.

### Layout

```
./structures/
├── <protein_family>_<organism>/
│   ├── <protein_name>_<UniProt_ID>.pdb
│   ├── <protein_name>_<UniProt_ID>.pdb
│   ├── manifest.csv
│   ├── manifest.json
│   └── manifest.tsv
├── <protein_family>_<organism>/
│   └── ...
```

- **Folders** group structures by family and source organism, e.g. `kinase_human/`, `gpcr_mouse/`, `hemoglobin_human/`.
- **Files** are named `<protein_name>_<UniProt_ID>.pdb`, e.g. `EGFR_P00533.pdb`, `HBA1_P69905.pdb`. The UniProt ID disambiguates isoforms and species variants.
- **Manifests** (`manifest.csv`, `manifest.json`, `manifest.tsv`) sit alongside the PDB files and carry per-structure metadata (source PDB ID, resolution, construct boundaries, mutations, ligands present, notes). All three formats encode the same content — pick whichever parses easiest for the task.

### Resolution order

When the user asks to load a protein, follow this order:

1. **Glob `./structures/*/<protein>_*.pdb`** (case-insensitive). Prefer the exact name match; on ambiguity, also try `./structures/*/*<protein>*_*.pdb` and surface the matches.
2. **If exactly one match**, load it with `cmd.load('<absolute_path>', '<obj_name>')`. Use the protein name (lowercased) as the object name unless the user specifies otherwise.
3. **If multiple matches** (e.g. same protein across organisms or families), read the relevant `manifest.csv`/`manifest.json`/`manifest.tsv` to disambiguate and pick the right one, or list the candidates and ask the user.
4. **If zero matches**, fall back to `cmd.fetch(<pdb_id>, async_=0)` only when the user supplied a PDB ID or explicitly asked to fetch from the RCSB.

Do **not** silently fetch from the network when a local match exists — the local file is canonical.

### Recipe: Resolve and load a protein from `./structures/`

Run the glob in the shell first to confirm the path, then `cmd.load` it:

```bash
# In the shell — resolve the file path before sending to PyMOL.
PROTEIN_NAME="EGFR"
MATCHES=( ./structures/*/"${PROTEIN_NAME}"_*.pdb )
case "${#MATCHES[@]}" in
  0) echo "no local match for ${PROTEIN_NAME}; consider cmd.fetch with a PDB ID" ;;
  1) echo "loading: ${MATCHES[0]}" ;;
  *) printf 'multiple matches:\n'; printf '  %s\n' "${MATCHES[@]}" ;;
esac
```

Then send the load over the socket using the absolute path:

```python
import os
pdb_path = os.path.abspath('./structures/kinase_human/EGFR_P00533.pdb')
cmd.delete('all')
cmd.load(pdb_path, 'egfr')
cmd.show_as('cartoon', 'egfr')
cmd.orient('egfr')
_result = {
    'object':  'egfr',
    'source':  pdb_path,
    'chains':  cmd.get_chains('egfr'),
    'n_atoms': cmd.count_atoms('egfr'),
}
```

### Recipe: Consult the manifest for extra metadata

```python
import csv, os
folder = os.path.abspath('./structures/kinase_human')
with open(os.path.join(folder, 'manifest.csv'), newline='') as f:
    rows = list(csv.DictReader(f))
_result = [r for r in rows if r.get('uniprot_id') == 'P00533']
```

Equivalent JSON path:

```python
import json, os
with open(os.path.abspath('./structures/kinase_human/manifest.json')) as f:
    manifest = json.load(f)
_result = [entry for entry in manifest if entry.get('uniprot_id') == 'P00533']
```

## Common recipes

### Recipe: Publication figure for a single structure

```python
cmd.delete('all')
cmd.fetch('4hhb', 'hb', async_=0)            # hemoglobin
cmd.remove('solvent')

cmd.show_as('cartoon', 'polymer')
cmd.show_as('sticks',  'resn HEM')
cmd.show_as('spheres', 'resn HEM and name FE')

cmd.color('lightblue', 'chain A or chain C')
cmd.color('lightpink', 'chain B or chain D')
cmd.util.cbag('resn HEM')
cmd.color('orange', 'resn HEM and name FE')

# Surface around one heme pocket.
cmd.select('pocket', 'byres polymer within 5 of (resn HEM and chain A)')
cmd.show('surface', 'pocket')
cmd.set('transparency', 0.5, 'pocket')

cmd.bg_color('white')
cmd.orient('chain A and resn HEM')
cmd.zoom('chain A and resn HEM', buffer=8)
cmd.set('ray_shadows', 0)
cmd.png('/tmp/hb_pocket.png', width=2400, height=1800, ray=1, dpi=300)
print('saved /tmp/hb_pocket.png')
```

### Recipe: Pairwise alignment + RMSD report

```python
cmd.delete('all')
cmd.fetch('1ake', 'ake',        async_=0)
cmd.fetch('4ake', 'ake_closed', async_=0)

align_stats = cmd.align('ake_closed', 'ake')
rmsd, n_atoms = align_stats[0], align_stats[1]
print(f'RMSD={rmsd:.3f} A over {n_atoms} atoms')

cmd.show_as('cartoon', 'all')
cmd.color('skyblue', 'ake')
cmd.color('salmon',  'ake_closed')
cmd.bg_color('white')
cmd.orient('ake')
cmd.png('/tmp/ake_aligned.png', width=1800, height=1200, ray=1, dpi=300)

_result = {'rmsd': round(rmsd, 3), 'n_atoms': int(n_atoms)}
```

### Recipe: Batch-render a set of PDB IDs

```python
import os
os.makedirs('/tmp/batch', exist_ok=True)

pdb_ids = ['1ubq', '1crn', '1lyz', '4hhb']
results = []
for pdb in pdb_ids:
    name = f'obj_{pdb}'
    cmd.delete(name)
    cmd.fetch(pdb, name, async_=0)
    cmd.show_as('cartoon', name)
    cmd.spectrum('count', 'rainbow', name)
    cmd.bg_color('white')
    cmd.orient(name)
    out = f'/tmp/batch/{pdb}.png'
    cmd.png(out, width=1200, height=900, ray=1, dpi=200)
    results.append((pdb, out, cmd.count_atoms(f'{name} and polymer')))
    cmd.delete(name)        # free memory between iterations

for pdb, out, n in results:
    print(f'{pdb}\t{n} atoms\t{out}')
```

### Recipe: Transparent-background figure for a slide

```python
cmd.bg_color('white')
cmd.set('ray_opaque_background', 0)
cmd.set('ray_shadows', 0)
cmd.png('/tmp/slide_fig.png', width=2400, height=1800, ray=1, dpi=300)
```

### Recipe: Color by B-factor (putty cartoon)

```python
cmd.show_as('putty', 'polymer')
cmd.spectrum('b', 'blue_white_red', 'polymer')
cmd.set('cartoon_putty_scale_min', 0.5)
cmd.set('cartoon_putty_scale_max', 3.0)
```

### Recipe: Extract a binding pocket as a new object

```python
cmd.select('pocket_sel', 'byres polymer within 5 of resn HEM')
cmd.create('pocket', 'pocket_sel')
cmd.show_as('sticks', 'pocket')
cmd.zoom('pocket', buffer=2)
_result = cmd.count_atoms('pocket')
```

### Recipe: Read structure metadata back to the caller

```python
info = {
    'objects':         cmd.get_object_list(),
    'chains_ubq':      cmd.get_chains('ubq'),
    'n_polymer_atoms': cmd.count_atoms('ubq and polymer'),
    'extent':          cmd.get_extent('ubq'),
}
_result = info
```

## Key parameters

| Parameter | Module | Default | Range / Options | Effect |
|-----------|--------|---------|-----------------|--------|
| `cmd.fetch(async_=)` | Load | `1` | `0`, `1` | `0` = synchronous; **always required over the socket** |
| `cmd.png(ray=)` | Render | `0` | `0`, `1` | `1` = full ray-trace (publication quality); `0` = fast OpenGL grab |
| `cmd.png(width, height, dpi=)` | Render | viewport, `-1` dpi | any positive int | Image dimensions and embedded DPI |
| `cmd.spectrum(palette=)` | Color | `'rainbow'` | `'rainbow'`, `'blue_white_red'`, `'yellow_white_blue'`, `'rmb'`, `'wrb'`, … | Built-in gradient palettes |
| `cmd.show_as(rep=)` | Representation | — | `cartoon`, `sticks`, `spheres`, `surface`, `mesh`, `lines`, `ribbon`, `dots`, `nb_spheres`, `licorice`, `putty` | Sets the only representation for a selection |
| `cmd.zoom(buffer=)` | View | `0` | `0`–`20` Å | Padding in Å around the framed selection |
| `cmd.set('ray_shadows', …)` | Render | `1` | `0`, `1`, `2` | `0` = no shadows (cleaner figures); `2` = matte shadows |
| `cmd.set('ray_opaque_background', …)` | Render | `1` | `0`, `1` | `0` = transparent PNG background |
| `cmd.set('transparency', …)` | Representation | `0` | `0.0`–`1.0` | Surface transparency (0 = opaque, 1 = invisible) |
| `cmd.align/super (cycles=)` | Align | `5` | `0`–`10` | Outlier-rejection refinement cycles; `0` = single pass |

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Cannot connect to PyMOL at localhost:9876` (exit 2) | Plugin not started, or PyMOL not running | Run `pymol_launch.py`. If it exits 1, PyMOL is installed but the MCP plugin didn't autostart — open PyMOL and type `mcp_start` in its command bar. If it exits 2, install PyMOL or add it to `PATH`. |
| `'pymol' binary not found in PATH` (launcher exit 2) | PyMOL not installed or not on PATH | Install PyMOL or extend `PATH` to include its install directory, then retry. |
| `WARNING: possible silent PyMOL error — SELECTION_ERROR` (exit 0) | Selection referenced a name that doesn't exist or matched zero atoms | `_result = cmd.get_object_list()` to verify object names; check selection syntax (e.g. `chain A` vs `chain a` for case-sensitive PDBs). |
| `cmd.fetch` returns but next command says "object not found" | `async_` defaulted to `1`, returning before the download finished | Pass `async_=0` explicitly, or use `pymol_send.py --fetch-pdb`. |
| `cmd.png` writes a black or blank image | Viewport not initialized, or `ray=0` with no GL context refresh | Call `cmd.orient(...)` and `cmd.zoom(...)` first; pass `ray=1` for headless-safe rendering. |
| Render takes minutes for one PNG | `ray=1` with high `width`/`height` and many shadow rays | Lower `width`/`height` for drafts; `cmd.set('ray_shadows', 0)`; reduce `ray_trace_mode`. |
| `cmd.align` fails with "no atoms in selection" | Mobile or target was deleted, or a selection-language typo | Confirm both objects exist (`_result = cmd.get_object_list()`); fall back to `cmd.super` for distant homologs. |
| Helper response truncated mid-JSON | Very large payload (e.g. `cmd.get_pdbstr` on a 100k-atom structure) | Save to disk via `cmd.save('/tmp/x.pdb', sel)` and read the file from the caller. |
| Stale artifacts in a fresh render (old colors, leftover surfaces) | Persistent state from prior sends in the same PyMOL session | `cmd.delete('all')` for a full reset, or `cmd.delete('name')` to drop one object. |
| Single-line `--code` fails with shell-quoting errors on Windows | Embedded quotes/parentheses mangled by `cmd.exe` or PowerShell | Pipe via stdin with a heredoc instead of `--code`; the helper reads stdin when `--code` is omitted. |
| `ERROR: cmd.reinitialize() is blocked` (exit 1) | Code blob contained `cmd.reinitialize` | Replace with `cmd.delete('all')` — the same reset without the crash. |
| `cmd.load` silently failed / "Unable to open file" for a `./structures/` path | Relative path resolved against PyMOL's CWD, not the agent's | Always pass an absolute path: `os.path.abspath('./structures/<family>_<organism>/<protein>_<UniProt>.pdb')`. |
| Glob in `./structures/*/<protein>_*.pdb` returned multiple files | Same protein name across organisms or families | Read the relevant `manifest.{csv,json,tsv}` to pick the right one, or list candidates and ask the user. |

## Bundled resources

- `scripts/pymol_send.py` — stdlib-only Python helper. Opens a TCP socket to the PyMOL MCP Socket Plugin on `localhost:9876`, ships a code blob, prints captured stdout (or `_result`). Detects silent PyMOL errors via `SILENT_ERROR_PATTERNS` and emits `WARNING:` on stderr. Includes a `--fetch-pdb` convenience that wraps `cmd.fetch(..., async_=0) + show_as cartoon + orient`. Blocks `cmd.reinitialize` locally before sending. Exit codes: `0` success, `1` PyMOL/exec error, `2` connection error.
- `scripts/pymol_launch.py` — stdlib-only launcher. Checks `localhost:9876`; if unavailable, spawns `pymol -d "mcp_start"` detached and waits for the socket. No-op when PyMOL is already listening. Exit codes: `0` ready, `1` did not come up, `2` `pymol` binary not found.
- `./structures/` — project-root directory holding the curated local PDB library. Subfolders follow `<protein_family>_<organism>/`, files follow `<protein_name>_<UniProt_ID>.pdb`, with per-folder `manifest.csv`/`manifest.json`/`manifest.tsv` describing the contents. Always check here before reaching for `cmd.fetch`.

## Related skills

- **biopython-molecular-biology** — headless PDB/structure parsing, Bio.PDB analysis, and sequence work without a GUI; pair with this skill when you analyze in BioPython and visualize in PyMOL.
- **mdanalysis-trajectory** — MD trajectory analysis (RMSD, RMSF, contacts) on `.dcd`/`.xtc`; render representative frames in PyMOL.
- **autodock-vina-docking** — produce docked ligand poses (`.pdbqt`/`.sdf`); load and visualize them with this skill.
- **pdb-database** — query the RCSB PDB API for metadata before fetching structures into PyMOL.
- **rdkit-cheminformatics** — generate 3D conformers (`.sdf`) for small molecules; load with `cmd.load(..., 'lig')` for visualization.

## References

- [PyMOL Open-Source Wiki](https://pymolwiki.org/) — community-maintained reference for the `cmd.*` API, selection language, and rendering settings.
- [PyMOL Selection Language](https://pymolwiki.org/index.php/Selection_Algebra) — full operator reference (`byres`, `within`, `ss`, `polymer`, `organic`, …).
- [PyMOL `cmd` API reference](https://pymol.org/pymol-command-ref.html) — official command reference.
- [PyMOL Ray-Tracing Settings](https://pymolwiki.org/index.php/Ray) — `ray_shadows`, `ray_trace_mode`, `ray_opaque_background`, and other rendering knobs.
