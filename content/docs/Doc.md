# AmadeusBio.ai - Agentic Bioinformatics System

## Overview
AmadeusBio.ai is an agentic system designed for advanced bioinformatics tasks, integrating various tools and APIs into a cohesive workflow.

## Component Guides

### PyMOL Integration
Based on [pymol-mcp](https://github.com/vrtejus/pymol-mcp) and integrated with Gemini CLI via specialized skills.

#### Installation & Setup
1. **Download**: Install PyMOL from [pymol.org](https://www.pymol.org/) (educational license available).
2. **Path Configuration**: Add `C:\Users\lyang\AppData\Local\Schrodinger\PyMOL2` to your system `PATH`.
3. **CLI Wrapper**: Create a `pymol.bat` file in your path with the following content:
   ```batch
   @echo off
   pyMOLWin.exe %*
   ```

#### Task List
- [ ] Implement agent check for running PyMOL instances.
- [ ] Automate `pymol -d "mcp_start"` to launch PyMOL if inactive.

### EMBL Clustal Omega API
Integration for multiple sequence alignment using the EMBL-EBI services.
- **Reference**: [Project Discussion](https://claude.ai/share/98617861-e33b-48da-8d76-c6c6d6a0a6ef)
- **Next Steps**: Create `SKILL.md` for the [EBI Python clients](https://github.com/ebi-jdispatcher/webservice-clients/tree/master/python).

### AlphaFold Prediction JSON Writer
Tools for preparing job submissions for AlphaFold.
- **Resources**: [Server README](https://github.com/google-deepmind/alphafold/blob/main/server/README.md) | [Example JSON](https://github.com/google-deepmind/alphafold/blob/main/server/example.json)
- **Requirements**:
  - Support for sequence editing and combinatorial variants.
  - File copy/paste specifications.
  - Adherence to submission best practices.

### Sequence Manipulation
Robust DNA and Protein sequence editing capabilities.
- **Features**: Natural language-guided sequence editing with high accuracy for both nucleotide and amino acid sequences.

### Batch Downloader
- **Protein Structure**: Automated downloading of structural data (e.g., from PDB).

## Development Roadmap
- [ ] Clone and integrate `BioSkills` and `SciAgent-Skills` skill sets.
- [ ] Establish a reproducible agent build process.
