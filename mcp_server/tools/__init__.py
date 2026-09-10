"""The 5 priced MCP tools — one module per tool, per README's target repo
structure. Each module exposes a single async function with the same name
as its file; `mcp_server/server.py` registers each as an `@mcp.tool()` and
`mcp_server/x402_middleware.py` gates the call behind payment before it runs.
"""
