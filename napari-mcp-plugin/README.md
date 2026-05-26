# napari-mcp

A napari plugin that listens on a TCP socket and executes Python code received
from external clients (e.g. an MCP server) against the running napari viewer.
This is the napari analogue of the PyMOL MCP socket plugin.

## What it does

Once the plugin's dock widget is open, it runs a small JSON-over-TCP server
(default port `9877`). External clients send messages of the form:

```json
{"type": "execute", "code": "viewer.add_image(np.random.rand(256, 256))"}
```

and the plugin executes the `code` against the live `napari.Viewer`, returning
either a success result or an error message. Execution is marshalled to the
Qt GUI thread so calls like `viewer.add_image` are safe.

Names available inside the executed code:

| Name     | What it is                                |
|----------|-------------------------------------------|
| `viewer` | the active `napari.Viewer` instance       |
| `napari` | the `napari` module                       |
| `np`     | `numpy`                                   |

## Installation (local / editable)

From the repository root:

```bash
pip install -e .
```

This installs the package in editable mode in your current Python environment,
the same one napari is installed in. napari discovers the plugin via the
`napari.manifest` entry point declared in `pyproject.toml`.

To verify discovery:

```bash
napari --info
```

`napari-mcp` should appear in the `Plugins` list.

## Usage

### Open the widget from the menu

```bash
napari
```

Then choose `Plugins → napari-mcp: MCP Server`. The widget opens and the
server starts listening immediately.

### Auto-open the widget from the command line

```bash
napari -w napari-mcp 'MCP Server'
```

This is the closest equivalent to the PyMOL plugin's `mcp_start` command:
napari opens, the MCP Server widget is docked, and the socket server is
already listening on port 9877.

> The form `napari -d "mcp_start"` you may have seen does not exist in
> napari's CLI; `-w PLUGIN_NAME WIDGET_DISPLAY_NAME` is the supported way
> to auto-open a plugin widget at startup.

### Change the port

Edit the port in the widget's spinbox, click **Stop Listening**, then
**Start Listening** again.

## Quick test client

With the widget running, in a separate terminal:

```bash
python test_client.py
```

(or see `test_client.py` for the exact protocol).

## Wire protocol

Each request is a single JSON object encoded as UTF-8 bytes, sent over a TCP
connection to the configured port. The server responds with a single JSON
object.

**Request**

```json
{"type": "execute", "code": "viewer.add_points([[10,10],[50,50]])"}
```

**Success response**

```json
{"status": "success", "result": {"executed": true, "output": "..."}}
```

**Error response**

```json
{"status": "error", "message": "..."}
```

The protocol is identical to the reference PyMOL MCP plugin so the same MCP
server implementation can target both with minimal changes.

## Project layout

```
napari-mcp/
├── pyproject.toml
├── README.md
├── src/
│   └── napari_mcp/
│       ├── __init__.py
│       ├── napari.yaml          # npe2 manifest (commands + widgets)
│       ├── _socket_server.py    # threaded TCP server
│       ├── _executor.py         # GUI-thread-safe code executor
│       └── _widget.py           # dock widget; auto-starts the server
└── test_client.py              # tiny example client
```

## Notes & caveats

- **GUI-thread safety.** napari Qt objects are not thread-safe; the socket
  worker thread cannot touch them directly. The executor signals back to the
  GUI thread and blocks the worker until execution completes. This is the
  main napari-specific difference from the reference PyMOL plugin.
- **Security.** `exec()` runs arbitrary Python with full access to the
  viewer and to your Python environment. Bind to `localhost` only (the
  default) and don't expose the port to untrusted networks.
- **One client at a time.** Matches the PyMOL plugin's design. If you need
  concurrent clients, queue requests on the client side.

## License

MIT
