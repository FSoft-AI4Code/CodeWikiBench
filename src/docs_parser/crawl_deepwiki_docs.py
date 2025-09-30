import asyncio
import json
import os
import argparse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.types import CallToolResult, Tool as MCPTool


class MCPClient(BaseModel):
    """A collection of tools that connects to an MCP server and manages available tools through the Model Context Protocol."""

    session: Optional[ClientSession] = None
    description: str = 'MCP client tools for server interaction'
    name: str = Field(default='')

    server_url: str
    server_params: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

    def __init__(
        self,
        server_url: str,
        timeout: float = 180.0,
        read_timeout: float = 45.0,
    ):
        """Initialize the MCPClient with server URL and available agents.

        Args:
            server_url: The URL of the MCP server.
            available_for_agents: List of agent names that can use this tools from this MCP client.
            timeout: Connection timeout in seconds. Default is 5 seconds.
            read_timeout: The read timeout for the SSE connection. Default is 2 minutes.
        """
        server_params = {
            'url': server_url,
            'timeout': timeout,
            'sse_read_timeout': read_timeout,
        }
        
        # Properly initialize the Pydantic model
        super().__init__(
            server_url=server_url,
            server_params=server_params
        )
            

    async def connect_sse(self) -> None:

        if self.session:
            await self.close_session()

        print('Connecting to MCP server')

        try:
            async with sse_client(**self.server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    self.session = session
                    await self._initialize_and_list_tools()
        except Exception as e:
            print(f'Error connecting to {self.server_url}: {str(e)}')
            raise

    async def _initialize_and_list_tools(self) -> None:
        """Initialize session and populate tool map."""
        if not self.session:
            raise RuntimeError('Session not initialized.')

        await self.session.initialize()
        response = await self.session.list_tools()

        # resgist mcp tools
        self.regist_mcp_tools(response.tools)

        # print(
        #     f'Connected to server with tools: {response.tools}'
        # )
        print("Connected to server with tools")

    async def call_tool(self, tool_name: str, args: Dict) -> CallToolResult:
        """Call a tool on the MCP server with automatic reconnection on failure.

        Args:
            tool_name: Name of the tool to call.
            args: Arguments to pass to the tool.

        Returns:
            The tool execution result.

        Raises:
            ValueError: If the tool is not found.
            RuntimeError: If connection failed and couldn't be restored.
        """

        try:
            # Check if we need to reconnect
            read_timeout: float = self.server_params['sse_read_timeout']
            tool_result = await asyncio.wait_for(
                self.execute_call_tool(tool_name=tool_name, args=args),
                read_timeout + 1.0,  # noqa: E226
            )
            return tool_result
        except Exception as e:
            print(f'Tool call to {tool_name} failed: {str(e)}')
            return CallToolResult(
                content=[
                    {
                        'text': f'Tool call to {tool_name} failed: {str(e)}',
                        'type': 'text',
                    }
                ],
                isError=True,
            )
        finally:
            await self.close_session()

    async def execute_call_tool(self, tool_name: str, args: Dict) -> CallToolResult:
        async with sse_client(**self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                self.session = session
                if not self.session:
                    raise RuntimeError(
                        'Failed to reconnect to MCP server. Session is None.'
                    )
                await self.session.initialize()
                tool_result = await self.session.call_tool(name=tool_name, arguments=args)
                if tool_result.isError:
                    print(
                        f'Tool call to {tool_name} failed: {tool_result.content}'
                    )
                return tool_result

    async def close_session(self) -> None:
        try:
            if self.session:
                if hasattr(self.session, 'close'):
                    await self.session.close()
            self.session = None
        except Exception as e:
            print(f'Error during close session: {str(e)}')

    async def disconnect(self) -> None:
        """Disconnect from the MCP server and clean up resources."""
        await self.close_session()

    def regist_mcp_tools(self, mcp_tools: List[MCPTool]) -> None:

        # tools: List[Tool] = []
        
        for mcp_tool in mcp_tools:
            name = mcp_tool.name
            description = mcp_tool.description

            # Get the schema information
            input_schema = mcp_tool.inputSchema

            # Build the OpenAI parameters structure
            openai_parameters = {
                'type': 'object',
                'properties': {},
                'required': input_schema.get('required', []),
            }

            # Process properties
            properties = input_schema.get('properties', {})
            defs = input_schema.get('$defs', {})

            for prop_name, prop_details in properties.items():
                # Check if it's a reference to a defined type
                if '$ref' in prop_details:
                    ref_path = prop_details['$ref']

                    # Extract the type name from the reference path
                    # Format is typically "#/$defs/TypeName"
                    type_name = ref_path.split('/')[-1]

                    # Get the definition for this type
                    if type_name in defs:
                        type_def = defs[type_name]

                        # Create a nested object for this property
                        openai_parameters['properties'][prop_name] = {
                            'type': type_def.get('type', 'object'),
                            'properties': {},
                            'required': [],  # OpenAI format doesn't require nested required fields
                        }
                        # Handle enum type
                        if 'enum' in type_def:
                            openai_parameters['properties'][prop_name]['enum'] = type_def[
                                'enum'
                            ]

                        # Handle default value
                        if 'default' in type_def:
                            openai_parameters['properties'][prop_name]['default'] = (
                                type_def['default']
                            )

                        # Handle description
                        if 'description' in type_def:
                            openai_parameters['properties'][prop_name]['description'] = (
                                type_def['description']
                            )

                        # Handle title
                        if 'title' in type_def:
                            openai_parameters['properties'][prop_name]['title'] = type_def[
                                'title'
                            ]

                        # Handle minimum
                        if 'minimum' in type_def:
                            openai_parameters['properties'][prop_name]['minimum'] = (
                                type_def['minimum']
                            )

                        # Handle maximum
                        if 'maximum' in type_def:
                            openai_parameters['properties'][prop_name]['maximum'] = (
                                type_def['maximum']
                            )

                        # Add the nested properties
                        for nested_prop, nested_details in type_def.get(
                            'properties', {}
                        ).items():
                            prop_type = nested_details.get('type')
                            prop_desc = nested_details.get('description', '')

                            openai_parameters['properties'][prop_name]['properties'][
                                nested_prop
                            ] = {'type': prop_type, 'description': prop_desc}
                else:
                    # It's a direct property
                    openai_parameters['properties'][prop_name] = {
                        'type': prop_details.get('type', 'string'),
                        'description': prop_details.get('description', ''),
                    }

import os
from typing import Dict
from urllib.parse import urlparse


class GitHubRepoProcessor:
    """Handles GitHub repository processing."""
    
    @staticmethod
    def is_valid_github_url(url: str) -> bool:
        """Validate if the URL is a valid GitHub repository URL."""
        try:
            parsed = urlparse(url)
            if parsed.netloc.lower() not in ['github.com', 'www.github.com']:
                return False
            
            path_parts = parsed.path.strip('/').split('/')
            if len(path_parts) < 2:
                return False
            
            # Check if it's a valid repo path (owner/repo)
            return len(path_parts) >= 2 and all(part for part in path_parts[:2])
        except Exception:
            return False
    
    @staticmethod
    def get_repo_info(url: str) -> Dict[str, str]:
        """Extract repository information from GitHub URL."""
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        
        owner = path_parts[0]
        repo = path_parts[1]
        
        # Remove .git suffix if present
        if repo.endswith('.git'):
            repo = repo[:-4]
        
        return {
            'owner': owner,
            'repo': repo,
            'full_name': f"{owner}/{repo}",
            'clone_url': f"https://github.com/{owner}/{repo}.git"
        }


async def pull_content_and_save(url: str, output_dir: str):
    client = MCPClient(
        server_url="https://mcp.deepwiki.com/sse",
        timeout=30,
        read_timeout=60,
    )
    await client.connect_sse()

    repo_name = GitHubRepoProcessor.get_repo_info(url)['full_name']

    read_wiki_structure_result = await client.call_tool("read_wiki_structure", {"repoName": repo_name})
    
    headers = read_wiki_structure_result.content[0].text.strip().split("\n")[2:]
    for i in range(len(headers)):
        header = headers[i].split("- ")[-1]
        header = header.split(" ")[0] + "-" + " ".join(header.split(" ")[1:])
        headers[i] = header

    read_wiki_contents_result = await client.call_tool("read_wiki_contents", {"repoName": repo_name})
    # print(f"read_wiki_contents_result: {read_wiki_contents_result}")
    # save the result to a md file
    for i, content in enumerate(read_wiki_contents_result.content):
        with open(os.path.join(output_dir, f"content_{i}.md"), "w") as f:
            f.write(headers[i] + "\n\n" + content.text.strip())

    await client.disconnect()

    



if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, required=True)
    parser.add_argument("--output-dir", type=str, required=True)
    
    args = parser.parse_args()

    url = args.url
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    asyncio.run(pull_content_and_save(url, output_dir))
    