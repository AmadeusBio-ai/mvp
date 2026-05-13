![AmadeusBio.ai Logo Light](assets/Horizontal_Logo.svg#gh-light-mode-only)
![AmadeusBio.ai Logo Dark](assets/Horizontal_Logo_Dark.svg#gh-dark-mode-only)

# Overview

AmadeusBio.ai is a coding agent (i.e Claude Code) based plugin that provides the instructions and protocols for agents to perform bioinformatic analysis.

## Demo
[Watch the AmadeusBio Demo](https://www.youtube.com/watch?v=YzUysayUQHg)

## Current features include:
1. Operate local softwares such as PyMol using natural language.
2. Retrival of sequences, protein structures etc. from databases including Uniprot.
3. Plus everything that come with coding agent.

## Get Started

### Install as a Claude Code plugin
Clone the repo, then point Claude Code at it with `--plugin-dir`:

```bash
git clone [https://github.com/starryark/AmadeusBio.ai_mvp.git](https://github.com/starryark/AmadeusBio.ai_mvp.git)
claude --plugin-dir ./AmadeusBio.ai_mvp
```

### PyMOL side (one-time, only if you use the PyMOL agent)

The `pymol-molecular-visualization` skill talks to a live PyMOL session over `localhost:9876`. Install the PyMOL-side plugin once:

1. Open PyMOL → `Plugin` → `Plugin Manager` → `Install New Plugin`.
2. Select the `pymol-mcp-socket-plugin/` directory in this repo.
3. Restart PyMOL. Verify with `pymol -d "mcp_start"` from a terminal.

See [PyMol-Integration](https://www.google.com/search?q=/docs/PyMol-Integration) for full PATH/wrapper setup on Windows/macOS/Linux.


#### Credits

*Skills used from:* <https://github.com/jaechang-hits/SciAgent-Skills.git>

*PyMol-mcp adopted from:* <https://github.com/vrtejus/pymol-mcp.git>

*Agents dashboard adopted from:* <https://github.com/hoangsonww/Claude-Code-Agent-Monitor.git>

*Website build using template:* <https://github.com/fuma-nama/fumadocs.git>