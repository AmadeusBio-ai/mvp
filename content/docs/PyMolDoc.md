# PyMOL Plugin Installation & Usage

## Updating the Plugin
If you have an older version of the plugin currently running in PyMOL, you must update it to ensure compatibility with the `mcp_start` command.

### Installation Steps
1. **Open PyMOL**.
2. **Open Plugin Manager**: Navigate to `Plugin` > `Plugin Manager`.
3. **Remove Old Version**: 
   - Go to the `Installed Plugins` tab.
   - Locate and remove the previous version of the MCP plugin.
4. **Install New Version**: 
   - Go to the `Install New Plugin` tab.
   - Select the directory containing the updated `__init__.py` and `.ui` files.
5. **Restart PyMOL**: Close PyMOL completely to finalize the installation.

## Running from the Command Line
Once the plugin is installed and the `mcp_start` command is registered, you can launch it directly from your terminal.

### Usage
Open your terminal or command prompt and execute:

```bash
pymol -d "mcp_start"
```

# Adding PyMOL to System PATH

Configuring PyMOL in your system's `PATH` allows you to execute the `pymol` command and pass arguments (e.g., `-c` for headless mode) directly from any terminal interface.

## Windows

The Windows installation utilizes `pyMOLWin.exe`. To enable the standard `pymol` command and ensure command-line arguments are passed correctly, you must update the `PATH` and create a batch wrapper.

**1. Update Environment Variables**

* Identify the PyMOL installation directory containing `pyMOLWin.exe` (e.g., `C:\Program Files\PyMOL\PyMOL` or `C:\Users\<User>\AppData\Local\Schrodinger\PyMOL2`).
* Add this directory to your system's `PATH` variable (`System Properties` > `Environment Variables` > `Path` > `Edit` > `New`).

**2. Create the Batch Wrapper**

* Inside the PyMOL directory, create a new text file named `pymol.bat`.
* Add the following script to forward execution and pass all appended flags (`%*`):
```bat
@echo off
pyMOLWin.exe %*

```



## macOS

macOS encapsulates PyMOL within an `.app` bundle. Create a symbolic link in `/usr/local/bin` to expose the internal executable to your terminal globally.

```bash
sudo ln -s /Applications/PyMOL.app/Contents/MacOS/PyMOL /usr/local/bin/pymol

```

## Linux

Installations via package managers (`apt`, `snap`, `conda`) typically configure the `PATH` automatically. For manual binary or source installations, append the executable's directory to your shell profile.

```bash
# Append to ~/.bashrc or ~/.zshrc
export PATH="/path/to/extracted/pymol/folder:$PATH"

# Apply the configuration
source ~/.bashrc

```

## Verification

Open a new terminal or command prompt session and verify the setup by triggering PyMOL in headless (`-c`) and quiet (`-q`) mode:

```bash
pymol -cq

```

*(If successful, the terminal will process the command without launching the GUI or printing startup logs.)*