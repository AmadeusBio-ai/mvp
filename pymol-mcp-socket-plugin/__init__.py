'''
PyMOL MCP Plugin

A plugin that listens for socket connections and executes PyMOL commands received via socket.
The plugin also provides a basic UI for interaction.
'''

from __future__ import absolute_import
from __future__ import print_function

import os
import socket
import json
import threading
import time
import traceback
import io
from contextlib import redirect_stdout
from pymol import cmd

# Global variables
dialog = None
socket_server = None
received_commands = []
listening = False
current_port = 9876  # Default port

class SocketServer:
    def __init__(self, host='localhost', port=9876):
        self.host = host
        self.port = port
        self.socket = None
        self.client = None
        self.running = False
        self.thread = None
        self.command_callback = None
        
    def start(self, command_callback=None):
        if self.running:
            return False
            
        self.command_callback = command_callback
        self.running = True
        self.thread = threading.Thread(target=self._run_server)
        self.thread.daemon = True
        self.thread.start()
        return True
        
    def _run_server(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)
            self.socket.settimeout(1.0)
            
            print(f"PyMOL MCP Socket server listening on {self.host}:{self.port}")
            
            while self.running:
                try:
                    self.client, address = self.socket.accept()
                    print(f"Connected to client: {address}")
                    self.client.settimeout(1.0)
                    
                    buffer = b''
                    while self.running:
                        try:
                            data = self.client.recv(4096)
                            if not data:
                                break
                                
                            buffer += data
                            
                            try:
                                command = json.loads(buffer.decode('utf-8'))
                                buffer = b''
                                result = self._handle_command(command)
                                response = json.dumps({
                                    "status": "success", 
                                    "result": result if result else "Command executed"
                                })
                                self.client.sendall(response.encode('utf-8'))
                            except json.JSONDecodeError:
                                continue
                                
                        except socket.timeout:
                            continue
                        except Exception as e:
                            print(f"Error receiving data: {str(e)}")
                            break
                    
                    if self.client:
                        self.client.close()
                        self.client = None
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"Error accepting connection: {str(e)}")
                    
        except Exception as e:
            print(f"Socket server error: {str(e)}")
            traceback.print_exc()
        finally:
            if self.socket:
                self.socket.close()
            self.running = False
            print("Socket server stopped")
    
    def _handle_command(self, command):
        if not command:
            return
            
        cmd_type = command.get("type")
        cmd_code = command.get("code", "")
        
        global received_commands
        received_commands.append(cmd_code)
        
        if self.command_callback and cmd_code:
            return self.command_callback(cmd_code)
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(2.0)
        if self.client:
            self.client.close()
        if self.socket:
            self.socket.close()
        self.socket = None
        self.client = None
        self.thread = None

# --- GLOBAL EXECUTION FUNCTION ---
def execute_pymol_command(code):
    try:
        print(f"Executing PyMOL command from MCP:\n{code}")
        exec_globals = {"cmd": cmd, "__builtins__": __builtins__}
        output_buffer = io.StringIO()
        with redirect_stdout(output_buffer):
            exec(code, exec_globals)
        
        output = output_buffer.getvalue()
        if output:
            print(f"Command output: {output}")
            return {"executed": True, "output": output}
        else:
            if '_result' in exec_globals:
                result = str(exec_globals['_result'])
                print(f"Command result: {result}")
                return {"executed": True, "output": result}
            return {"executed": True, "output": "Command executed successfully (no output)"}
    except Exception as e:
        error_msg = f"Error executing PyMOL command: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return {"executed": False, "error": error_msg}

# --- NEW NATIVE PYMOL COMMAND ---
def mcp_start_server(port=None):
    """Command to start the MCP server, exposed to PyMOL CLI"""
    global socket_server, listening, current_port
    
    if port:
        current_port = int(port)
        
    if not listening:
        socket_server = SocketServer(port=current_port)
        if socket_server.start(execute_pymol_command):
            listening = True
            print(f"PyMOL MCP Socket server started and listening on port {current_port}")
    else:
        print(f"Server is already listening on port {current_port}")

# Register the command with PyMOL so it can be called via the CLI
cmd.extend("mcp_start", mcp_start_server)

# --- GUI FUNCTIONS ---
def run_plugin_gui():
    global dialog
    if dialog is None:
        dialog = make_dialog()
    dialog.show()

def update_status_label(form, text):
    form.label_status.setText(text)
    if "Not listening" in text:
        form.label_status.setStyleSheet("color: red;")
    elif "Listening" in text:
        form.label_status.setStyleSheet("color: green;")
    else:
        form.label_status.setStyleSheet("")

def make_dialog():
    from pymol.Qt import QtWidgets
    from pymol.Qt.utils import loadUi
    
    global listening, current_port, socket_server, received_commands
    
    dialog = QtWidgets.QDialog()
    uifile = os.path.join(os.path.dirname(__file__), 'pymol_mcp_plugin.ui')
    form = loadUi(uifile, dialog)
    
    form.input_port.setValue(current_port)
    
    if listening:
        form.button_toggle_listening.setText("Stop Listening")
        update_status_label(form, f"Listening on port {current_port}")
    else:
        form.button_toggle_listening.setText("Start Listening")
        update_status_label(form, "Not listening")
    
    def toggle_listening():
        global socket_server, listening, current_port
        
        if not listening:
            port = form.input_port.value()
            current_port = port
            socket_server = SocketServer(port=port)
            if socket_server.start(execute_pymol_command):
                listening = True
                form.button_toggle_listening.setText("Stop Listening")
                update_status_label(form, f"Listening on port {port}")
        else:
            if socket_server:
                socket_server.stop()
            listening = False
            form.button_toggle_listening.setText("Start Listening")
            update_status_label(form, "Not listening")
    
    def close_dialog():
        dialog.close()
    
    form.button_toggle_listening.clicked.connect(toggle_listening)
    form.button_close.clicked.connect(close_dialog)
    
    return dialog

# --- PLUGIN INITIALIZATION ---
def __init_plugin__(app=None):
    from pymol.plugins import addmenuitemqt
    addmenuitemqt('PyMol MCP Socket Plugin', run_plugin_gui)
    print("PyMOL MCP Plugin loaded. Run 'mcp_start' to boot the socket server.")