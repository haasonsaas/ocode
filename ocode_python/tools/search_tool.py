"""
Web search tool for grounding AI responses with current information.
Provides access to real-time web search results for enhanced context.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import quote_plus

import aiohttp
from bs4 import BeautifulSoup

from .base import ResourceLock, Tool, ToolDefinition, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Represents a single search result."""

    title: str
    url: str
    snippet: str
    timestamp: Optional[str] = None
    source: Optional[str] = None


class SearchTool(Tool):
    """Tool for performing web searches to ground AI responses."""

    def __init__(self):
        super().__init__()
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="web_search",
            description=(
                "Search the web for current information to enhance responses "
                "with real-time data"
            ),
            category="Search",
            resource_locks=[ResourceLock.NETWORK],
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="The search query to execute",
                    required=True,
                ),
                ToolParameter(
                    name="max_results",
                    type="number",
                    description="Maximum number of results to return",
                    required=False,
                    default=5,
                ),
                ToolParameter(
                    name="include_snippets",
                    type="boolean",
                    description="Whether to include content snippets",
                    required=False,
                    default=True,
                ),
            ],
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            headers = {
                "User-Agent": "OCode-CLI/1.0 (Web Search Tool)",
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;" "q=0.9,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            }
            self._session = aiohttp.ClientSession(
                headers=headers, timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def _search_duckduckgo(
        self, query: str, max_results: int = 5
    ) -> List[SearchResult]:
        """Perform search using DuckDuckGo API."""
        try:
            session = await self._get_session()

            # DuckDuckGo Instant Answer API
            params = {
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
            }

            async with session.get(
                "https://api.duckduckgo.com/", params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []

                    # Extract instant answer if available
                    if data.get("Abstract"):
                        results.append(
                            SearchResult(
                                title=data.get("Heading", "DuckDuckGo Summary"),
                                url=data.get("AbstractURL", ""),
                                snippet=data.get("Abstract", ""),
                                source="DuckDuckGo",
                            )
                        )

                    # Extract related topics
                    for topic in data.get("RelatedTopics", [])[:max_results]:
                        if isinstance(topic, dict) and "Text" in topic:
                            results.append(
                                SearchResult(
                                    title=topic.get("Text", "").split(" - ")[0],
                                    url=topic.get("FirstURL", ""),
                                    snippet=topic.get("Text", ""),
                                    source="DuckDuckGo",
                                )
                            )

                    return results[:max_results]

        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")

        return []

    async def _search_html_scraping(
        self, query: str, max_results: int = 5
    ) -> List[SearchResult]:
        """Fallback search using HTML scraping."""
        try:
            session = await self._get_session()

            # Use DuckDuckGo HTML search as fallback
            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

            async with session.get(search_url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")

                    results = []
                    for link in soup.find_all("a", class_="result__a")[:max_results]:
                        title = link.get_text(strip=True)
                        url = str(link.get("href", ""))

                        # Find snippet in parent container
                        snippet = ""
                        parent = link.find_parent("div", class_="result")
                        if parent:
                            snippet_elem = parent.find("a", class_="result__snippet")
                            if snippet_elem:
                                snippet = snippet_elem.get_text(strip=True)

                        if title and url:
                            results.append(
                                SearchResult(
                                    title=title,
                                    url=url,
                                    snippet=snippet,
                                    source="DuckDuckGo HTML",
                                )
                            )

                    return results

        except Exception as e:
            logger.warning(f"HTML scraping search failed: {e}")

        return []

    async def _enhance_with_content(
        self, results: List[SearchResult], include_snippets: bool
    ) -> List[SearchResult]:
        """Enhance search results with page content if requested."""
        if not include_snippets:
            return results

        enhanced_results = []
        session = await self._get_session()

        for result in results:
            enhanced_result = result

            # If snippet is empty or very short, try to fetch content
            if len(result.snippet) < 50 and result.url:
                try:
                    async with session.get(
                        result.url, timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            html = await response.text()
                            soup = BeautifulSoup(html, "html.parser")

                            # Remove script and style elements
                            for script in soup(["script", "style"]):
                                script.decompose()

                            # Get text content
                            text = soup.get_text()

                            # Clean up text and create snippet
                            lines = (line.strip() for line in text.splitlines())
                            chunks = (
                                phrase.strip()
                                for line in lines
                                for phrase in line.split("  ")
                            )
                            text = " ".join(chunk for chunk in chunks if chunk)

                            # Create snippet (first 200 characters)
                            if len(text) > 200:
                                snippet = text[:200] + "..."
                            else:
                                snippet = text

                            enhanced_result = SearchResult(
                                title=result.title,
                                url=result.url,
                                snippet=snippet or result.snippet,
                                timestamp=result.timestamp,
                                source=result.source,
                            )

                except Exception as e:
                    logger.debug(f"Failed to enhance content for {result.url}: {e}")

            enhanced_results.append(enhanced_result)

        return enhanced_results

    async def execute(self, **kwargs) -> ToolResult:
        """Execute web search and return results."""
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 5)
        include_snippets = kwargs.get("include_snippets", True)

        if not query:
            return ToolResult(
                success=False,
                output="",
                error="Query parameter is required",
                metadata={"error": "Missing query parameter"},
            )

        try:
            # Try primary search method
            results = await self._search_duckduckgo(query, max_results)

            # Fallback to HTML scraping if needed
            if not results:
                results = await self._search_html_scraping(query, max_results)

            if not results:
                return ToolResult(
                    success=False,
                    output="",
                    error="No search results found for the query.",
                    metadata={"query": query, "results_count": 0},
                )

            # Enhance results with content if requested
            if include_snippets:
                results = await self._enhance_with_content(results, include_snippets)

            # Format results for output
            formatted_results = []
            for i, result in enumerate(results, 1):
                formatted_result = {
                    "rank": i,
                    "title": result.title,
                    "url": result.url,
                    "snippet": result.snippet,
                    "source": result.source,
                }
                if result.timestamp:
                    formatted_result["timestamp"] = result.timestamp

                formatted_results.append(formatted_result)

            # Create summary text
            summary_lines = [f"Search results for '{query}':\n"]
            for fmt_result in formatted_results:
                summary_lines.append(f"{fmt_result['rank']}. {fmt_result['title']}")
                summary_lines.append(f"   URL: {fmt_result['url']}")
                if fmt_result["snippet"]:
                    summary_lines.append(f"   Summary: {fmt_result['snippet']}")
                summary_lines.append("")

            return ToolResult(
                success=True,
                output="\n".join(summary_lines),
                metadata={
                    "query": query,
                    "results_count": len(results),
                    "results": formatted_results,
                },
            )

        except Exception as e:
            logger.error(f"Search execution failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                output="",
                error=f"Search failed: {str(e)}",
                metadata={"query": query, "error": str(e)},
            )

    async def cleanup(self):
        """Clean up resources."""
        if self._session and not self._session.closed:
            await self._session.close()
