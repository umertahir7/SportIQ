import asyncio

from mcp import Client

from app.mcp.server import mcp


def create_mcp_client():
    return Client(mcp)


async def list_available_tools():
    async with create_mcp_client() as client:
        result = await client.list_tools()

        return [
            tool.name
            for tool in result.tools
        ]


async def call_watchlist():
    async with create_mcp_client() as client:
        result = await client.call_tool(
            "get_watchlist",
            {},
        )

        return result.structured_content


async def main():
    tools = await list_available_tools()

    print("Available MCP tools:")

    for tool in tools:
        print(f"- {tool}")

    print("\nCalling get_watchlist through MCP...")

    watchlist = await call_watchlist()

    print("\nWatchlist:")
    print(watchlist)


if __name__ == "__main__":
    asyncio.run(main())