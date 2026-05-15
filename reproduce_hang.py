import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import sys
import os

async def main():
    # Construct path to the server.py
    server_path = os.path.join("napari-mcp", "src", "napari_mcp", "server.py")
    
    # Ensure we use the local napari-mcp source
    env = os.environ.copy()
    local_src = os.path.abspath(os.path.join("napari-mcp", "src"))
    env["PYTHONPATH"] = local_src + os.pathsep + env.get("PYTHONPATH", "")
    print(f"Using PYTHONPATH: {env['PYTHONPATH']}")
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_path],
        env=env,
        stderr=sys.stderr # Capture server stderr
    )
    
    print("Connecting to napari-mcp server...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Initialized session. Calling init_viewer...")
            
            # This is expected to hang based on user report
            try:
                result = await asyncio.wait_for(
                    session.call_tool("init_viewer", arguments={}),
                    timeout=60
                )
                print(f"Result: {result}")
            except asyncio.TimeoutError:
                print("Timed out calling init_viewer (Expected Hang)")
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
