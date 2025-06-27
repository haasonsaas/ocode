"""
Curl tool for downloading files and making HTTP requests.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import aiohttp

from .base import ResourceLock, Tool, ToolDefinition, ToolParameter, ToolResult
from ..utils.retry_handler import retry_async


class CurlTool(Tool):
    """Tool for making HTTP requests and downloading files."""

    @property
    def definition(self) -> ToolDefinition:
        """Define the curl tool specification.

        Returns:
            ToolDefinition with parameters for making HTTP requests including
            URL, method, headers, data, authentication, timeout, and output options.
        """
        return ToolDefinition(
            name="curl",
            description="Make HTTP requests and download files",
            resource_locks=[ResourceLock.NETWORK],
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="URL to request",
                    required=True,
                ),
                ToolParameter(
                    name="method",
                    type="string",
                    description="HTTP method (GET, POST, PUT, DELETE, etc.)",
                    required=False,
                    default="GET",
                ),
                ToolParameter(
                    name="output_file",
                    type="string",
                    description="Save response to file (-o flag)",
                    required=False,
                ),
                ToolParameter(
                    name="headers",
                    type="object",
                    description="HTTP headers as key-value pairs",
                    required=False,
                ),
                ToolParameter(
                    name="data",
                    type="string",
                    description="Request body data",
                    required=False,
                ),
                ToolParameter(
                    name="json_data",
                    type="object",
                    description="JSON data to send (will set Content-Type: application/json)",  # noqa: E501
                    required=False,
                ),
                ToolParameter(
                    name="follow_redirects",
                    type="boolean",
                    description="Follow HTTP redirects (-L flag)",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="timeout",
                    type="number",
                    description="Request timeout in seconds",
                    required=False,
                    default=30,
                ),
                ToolParameter(
                    name="include_headers",
                    type="boolean",
                    description="Include response headers in output (-i flag)",
                    required=False,
                    default=False,
                ),
            ],
        )

    @retry_async(
        max_attempts=3,
        base_delay=1.0,
        max_delay=30.0,
        retryable_exceptions=(
            aiohttp.ClientError,
            asyncio.TimeoutError,
            ConnectionError,
            OSError,
        )
    )
    async def _make_request(self, **kwargs: Any) -> ToolResult:
        """Make HTTP request with retry logic."""
        url = kwargs.get("url", "")
        method = kwargs.get("method", "GET")
        output_file = kwargs.get("output_file")
        headers = kwargs.get("headers")
        data = kwargs.get("data")
        json_data = kwargs.get("json_data")
        follow_redirects = kwargs.get("follow_redirects", True)
        timeout = kwargs.get("timeout", 30)
        include_headers = kwargs.get("include_headers", False)

        if not url:
            return ToolResult(success=False, output="", error="URL is required")
        
        # Prepare headers
        request_headers = headers or {}

        # Prepare data
        request_data = None
        if json_data:
            request_data = json.dumps(json_data)
            request_headers["Content-Type"] = "application/json"
        elif data:
            request_data = data

        # Configure timeout
        timeout_config = aiohttp.ClientTimeout(total=timeout)

        # Make the request
        async with aiohttp.ClientSession(
            timeout=timeout_config,
            connector=aiohttp.TCPConnector(limit=10, limit_per_host=5),
        ) as session:

            async with session.request(
                method.upper(),
                url,
                headers=request_headers,
                data=request_data,
                allow_redirects=follow_redirects,
            ) as response:

                # Get response content
                if output_file:
                    # Stream to file
                    output_path = Path(output_file)
                    output_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(output_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)

                    file_size = output_path.stat().st_size
                    output_text = f"Downloaded {file_size} bytes to {output_file}"

                else:
                    # Get response text
                    response_text = await response.text()

                    # Format output
                    if include_headers:
                        version_str = (
                            "HTTP/1.1"  # Default if version is not available
                        )
                        if response.version:
                            version_str = f"{response.version.major}.{response.version.minor}"  # noqa: E501
                        header_lines = [
                            f"{version_str} {response.status} {response.reason}"
                        ]
                        for name, value in response.headers.items():
                            header_lines.append(f"{name}: {value}")
                        header_lines.append(
                            ""
                        )  # Empty line between headers and body

                        output_text = "\n".join(header_lines) + response_text
                    else:
                        output_text = response_text

                # Prepare metadata
                metadata = {
                    "url": url,
                    "method": method.upper(),
                    "status_code": response.status,
                    "status_text": response.reason,
                    "content_type": response.headers.get("Content-Type", ""),
                    "content_length": response.headers.get("Content-Length", ""),
                    "response_headers": dict(response.headers),
                }

                if output_file:
                    metadata["output_file"] = output_file
                    metadata["file_size"] = file_size

                # Check for successful status codes
                if 200 <= response.status < 300:
                    return ToolResult(
                        success=True, output=output_text, metadata=metadata
                    )
                else:
                    return ToolResult(
                        success=False,
                        output=output_text,
                        error=f"HTTP {response.status}: {response.reason}",
                        metadata=metadata,
                    )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute curl command with retry logic for network failures."""
        try:
            return await self._make_request(**kwargs)
        except Exception as e:
            # Final fallback if retries are exhausted
            return ToolResult(
                success=False, 
                output="", 
                error=f"Network request failed after retries: {str(e)}"
            )
