"""
Testing and code quality tools.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, List, Optional

from .base import Tool, ToolDefinition, ToolParameter, ToolResult


class ExecutionTool(Tool):
    """Tool for running tests in the project."""

    def __init__(self):
        self._definition = ToolDefinition(
            name="test_runner",
            description="Run tests in the project",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to test directory or file",
                    required=False,
                ),
                ToolParameter(
                    name="framework",
                    type="string",
                    description="Test framework to use (auto, pytest, unittest, jest, vitest, go, cargo, mocha, rspec, maven, gradle)",  # noqa: E501
                    required=False,
                ),
                ToolParameter(
                    name="pattern",
                    type="string",
                    description="Test pattern or filter to run specific tests",
                    required=False,
                ),
                ToolParameter(
                    name="verbose",
                    type="boolean",
                    description="Enable verbose output",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="timeout",
                    type="number",
                    description="Test execution timeout in seconds",
                    required=False,
                    default=300,
                ),
            ],
        )
        super().__init__()

    @property
    def definition(self):
        """Return the test_runner tool specification.

        Returns:
            ToolDefinition with parameters for running tests including
            path, framework selection, verbosity, and timeout options.
        """
        return self._definition

    def _detect_test_framework(self, path: str) -> str:
        """Auto-detect the appropriate test framework with enhanced detection."""
        test_path = Path(path)

        # Enhanced framework detection with priority order
        frameworks_detected = []

        # Python frameworks detection
        if (test_path / "pytest.ini").exists():
            frameworks_detected.append(("pytest", 10))
        if (test_path / "tox.ini").exists():
            frameworks_detected.append(("pytest", 8))
        if (test_path / "setup.cfg").exists():
            try:
                with open(test_path / "setup.cfg") as f:
                    content = f.read()
                    if "[tool:pytest]" in content:
                        frameworks_detected.append(("pytest", 9))
            except Exception:  # nosec
                pass

        if (test_path / "pyproject.toml").exists():
            try:
                with open(test_path / "pyproject.toml") as f:
                    content = f.read()
                    if "[tool.pytest" in content:
                        frameworks_detected.append(("pytest", 9))
                    elif "pytest" in content:
                        frameworks_detected.append(("pytest", 7))
            except Exception:  # nosec
                pass

        # JavaScript/TypeScript frameworks
        if (test_path / "package.json").exists():
            try:
                with open(test_path / "package.json") as f:
                    package_data = json.load(f)
                    deps = {
                        **package_data.get("dependencies", {}),
                        **package_data.get("devDependencies", {}),
                    }

                    if "jest" in deps:
                        frameworks_detected.append(("jest", 10))
                    elif "vitest" in deps:
                        frameworks_detected.append(("vitest", 10))
                    elif "mocha" in deps:
                        frameworks_detected.append(("mocha", 8))
                    elif "karma" in deps:
                        frameworks_detected.append(("karma", 6))

                    # Check test scripts
                    scripts = package_data.get("scripts", {})
                    if "test" in scripts:
                        script = scripts["test"]
                        if "jest" in script:
                            frameworks_detected.append(("jest", 9))
                        elif "vitest" in script:
                            frameworks_detected.append(("vitest", 9))
                        elif "mocha" in script:
                            frameworks_detected.append(("mocha", 7))
            except Exception:  # nosec
                pass

        # Go test detection
        if (test_path / "go.mod").exists():
            frameworks_detected.append(("go", 10))

        # Rust test detection
        if (test_path / "Cargo.toml").exists():
            frameworks_detected.append(("cargo", 10))

        # Ruby test detection
        if (test_path / "Gemfile").exists():
            try:
                with open(test_path / "Gemfile") as f:
                    content = f.read()
                    if "rspec" in content:
                        frameworks_detected.append(("rspec", 9))
                    elif "minitest" in content:
                        frameworks_detected.append(("minitest", 8))
            except Exception:  # nosec
                pass

        # Java test detection
        if (test_path / "pom.xml").exists():
            frameworks_detected.append(("maven", 8))
        if (test_path / "build.gradle").exists() or (
            test_path / "build.gradle.kts"
        ).exists():
            frameworks_detected.append(("gradle", 8))

        # File pattern-based detection
        test_files = {
            "pytest": list(test_path.rglob("test_*.py"))
            + list(test_path.rglob("*_test.py")),
            "jest": list(test_path.rglob("*.test.js"))
            + list(test_path.rglob("*.spec.js"))
            + list(test_path.rglob("*.test.ts"))
            + list(test_path.rglob("*.spec.ts")),
            "go": list(test_path.rglob("*_test.go")),
            "cargo": list(test_path.rglob("**/tests/**/*.rs")),
            "rspec": list(test_path.rglob("**/spec/**/*_spec.rb")),
        }

        for framework, files in test_files.items():
            if files:
                frameworks_detected.append((framework, len(files)))

        # Return highest priority framework
        if frameworks_detected:
            return max(frameworks_detected, key=lambda x: x[1])[0]

        return "pytest"  # Default fallback

    async def _run_pytest(
        self, path: str, pattern: Optional[str], verbose: bool, timeout: int
    ) -> ToolResult:
        """Run pytest tests with enhanced reporting."""
        cmd_parts = ["python", "-m", "pytest"]

        if verbose:
            cmd_parts.append("-v")
        else:
            cmd_parts.append("-q")

        if pattern:
            cmd_parts.extend(["-k", pattern])

        # Add coverage if available
        cmd_parts.extend(["--tb=short", "--no-header"])

        # Check if coverage is available
        try:
            import coverage  # type: ignore # noqa: F401

            cmd_parts.extend(["--cov=" + path, "--cov-report=term-missing"])
        except ImportError:
            pass

        cmd_parts.append(path)

        command = " ".join(cmd_parts)

        try:
            process = await asyncio.create_subprocess_shell(
                command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            output = stdout.decode("utf-8") if stdout else ""
            error = stderr.decode("utf-8") if stderr else ""

            # Enhanced pytest output parsing
            lines = output.split("\n")
            summary_line = ""
            test_results = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
            coverage_percent = None

            for line in lines:
                # Parse test summary
                if " passed" in line or " failed" in line or " error" in line:
                    summary_line = line.strip()
                    # Extract numbers
                    import re

                    numbers = re.findall(r"(\d+) (\w+)", line)
                    for count, result_type in numbers:
                        if result_type in test_results:
                            test_results[result_type] = int(count)

                # Parse coverage
                if "TOTAL" in line and "%" in line:
                    try:
                        coverage_percent = int(line.split()[-1].replace("%", ""))
                    except Exception:  # nosec
                        pass

            success = process.returncode == 0
            total_tests = sum(test_results.values())

            return ToolResult(
                success=success,
                output=output,
                error=error if not success else None,
                metadata={
                    "framework": "pytest",
                    "return_code": process.returncode,
                    "summary": summary_line,
                    "test_results": test_results,
                    "total_tests": total_tests,
                    "coverage_percent": coverage_percent,
                },
            )

        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                output="",
                error=f"Tests timed out after {timeout} seconds",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Failed to run pytest: {str(e)}"
            )

    async def _run_jest(
        self, path: str, pattern: Optional[str], verbose: bool, timeout: int
    ) -> ToolResult:
        """Run Jest tests."""
        cmd_parts = ["npm", "test"]

        if pattern:
            cmd_parts.extend(["--", "--testNamePattern", pattern])

        if verbose:
            cmd_parts.append("--verbose")

        command = " ".join(cmd_parts)

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            output = stdout.decode("utf-8") if stdout else ""
            error = stderr.decode("utf-8") if stderr else ""

            success = process.returncode == 0

            return ToolResult(
                success=success,
                output=output,
                error=error if not success else None,
                metadata={"framework": "jest", "return_code": process.returncode},
            )

        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                output="",
                error=f"Tests timed out after {timeout} seconds",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Failed to run Jest: {str(e)}"
            )

    async def _run_go_test(
        self, path: str, pattern: Optional[str], verbose: bool, timeout: int
    ) -> ToolResult:
        """Run Go tests."""
        cmd_parts = ["go", "test"]

        if verbose:
            cmd_parts.append("-v")

        if pattern:
            cmd_parts.extend(["-run", pattern])

        cmd_parts.append("./...")

        command = " ".join(cmd_parts)

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            output = stdout.decode("utf-8") if stdout else ""
            error = stderr.decode("utf-8") if stderr else ""

            success = process.returncode == 0

            return ToolResult(
                success=success,
                output=output,
                error=error if not success else None,
                metadata={"framework": "go", "return_code": process.returncode},
            )

        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                output="",
                error=f"Tests timed out after {timeout} seconds",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Failed to run Go tests: {str(e)}"
            )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Run tests using specified framework."""
        path = kwargs.get("path", ".")
        framework = kwargs.get("framework", "auto")
        pattern = kwargs.get("pattern")
        verbose = kwargs.get("verbose", False)
        timeout = kwargs.get("timeout", 300)

        # Auto-detect framework if needed
        if framework == "auto":
            framework = self._detect_test_framework(path)

        # Run tests based on framework
        if framework == "pytest":
            return await self._run_pytest(path, pattern, verbose, timeout)
        elif framework == "jest":
            return await self._run_jest(path, pattern, verbose, timeout)
        elif framework == "vitest":
            return await self._run_vitest(path, pattern, verbose, timeout)
        elif framework == "go":
            return await self._run_go_test(path, pattern, verbose, timeout)
        elif framework == "cargo":
            return await self._run_cargo_test(path, pattern, verbose, timeout)
        elif framework == "unittest":
            # Python unittest
            command = f"python -m unittest discover {path}"
            if verbose:
                command += " -v"

            try:
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )

                output = stdout.decode("utf-8") if stdout else ""
                error = stderr.decode("utf-8") if stderr else ""

                return ToolResult(
                    success=process.returncode == 0,
                    output=output,
                    error=error if process.returncode != 0 else None,
                    metadata={
                        "framework": "unittest",
                        "return_code": process.returncode,
                    },
                )

            except Exception as e:
                return ToolResult(
                    success=False, output="", error=f"Failed to run unittest: {str(e)}"
                )
        else:
            return ToolResult(
                success=False,
                output="",
                error=f"Unsupported test framework: {framework}",
            )

    async def _run_vitest(
        self, path: str, pattern: Optional[str], verbose: bool, timeout: int
    ) -> ToolResult:
        """Run Vitest tests."""
        cmd_parts = ["npx", "vitest", "run"]

        if pattern:
            cmd_parts.extend(["--grep", pattern])

        if verbose:
            cmd_parts.append("--reporter=verbose")
        else:
            cmd_parts.append("--reporter=basic")

        # Add coverage if configured
        cmd_parts.append("--coverage")

        command = " ".join(cmd_parts)

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            output = stdout.decode("utf-8") if stdout else ""
            error = stderr.decode("utf-8") if stderr else ""

            # Enhanced vitest output parsing
            lines = output.split("\n")
            summary_line = ""
            test_results = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
            coverage_percent = None

            for line in lines:
                # Parse test summary (Vitest format)
                if "Test Files" in line and ("passed" in line or "failed" in line):
                    summary_line = line.strip()
                    # Extract numbers using regex
                    import re

                    numbers = re.findall(r"(\d+) (\w+)", line)
                    for count, result_type in numbers:
                        if result_type.lower() in test_results:
                            test_results[result_type.lower()] = int(count)

                # Parse coverage
                if "All files" in line and "%" in line:
                    try:
                        # Vitest coverage format: All files | 85.71 | 100 | 85.71 | 85.71  # noqa: E501
                        parts = line.split("|")
                        if len(parts) >= 2:
                            coverage_percent = float(parts[1].strip())
                    except Exception:  # nosec
                        pass

            success = process.returncode == 0
            total_tests = sum(test_results.values())

            return ToolResult(
                success=success,
                output=output,
                error=error if not success else None,
                metadata={
                    "framework": "vitest",
                    "return_code": process.returncode,
                    "summary": summary_line,
                    "test_results": test_results,
                    "total_tests": total_tests,
                    "coverage_percent": coverage_percent,
                },
            )

        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                output="",
                error=f"Tests timed out after {timeout} seconds",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Failed to run Vitest: {str(e)}"
            )

    async def _run_cargo_test(
        self, path: str, pattern: Optional[str], verbose: bool, timeout: int
    ) -> ToolResult:
        """Run Cargo tests."""
        cmd_parts = ["cargo", "test"]

        if pattern:
            cmd_parts.append(pattern)

        if verbose:
            cmd_parts.append("--verbose")

        # Add output format for better parsing
        cmd_parts.extend(["--", "--nocapture"])

        command = " ".join(cmd_parts)

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            output = stdout.decode("utf-8") if stdout else ""
            error = stderr.decode("utf-8") if stderr else ""

            # Enhanced cargo test output parsing
            lines = output.split("\n")
            summary_line = ""
            test_results = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}

            for line in lines:
                # Parse test summary (Cargo format)
                if "test result:" in line:
                    summary_line = line.strip()
                    # Extract numbers: "test result: ok. 5 passed; 0 failed; 0 ignored; 0 measured"  # noqa: E501
                    import re

                    if "passed" in line:
                        passed_match = re.search(r"(\d+) passed", line)
                        if passed_match:
                            test_results["passed"] = int(passed_match.group(1))
                    if "failed" in line:
                        failed_match = re.search(r"(\d+) failed", line)
                        if failed_match:
                            test_results["failed"] = int(failed_match.group(1))
                    if "ignored" in line:
                        ignored_match = re.search(r"(\d+) ignored", line)
                        if ignored_match:
                            test_results["skipped"] = int(ignored_match.group(1))

            success = process.returncode == 0
            total_tests = sum(test_results.values())

            return ToolResult(
                success=success,
                output=output,
                error=error if not success else None,
                metadata={
                    "framework": "cargo",
                    "return_code": process.returncode,
                    "summary": summary_line,
                    "test_results": test_results,
                    "total_tests": total_tests,
                },
            )

        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                output="",
                error=f"Tests timed out after {timeout} seconds",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Failed to run Cargo tests: {str(e)}"
            )


class LintTool(Tool):
    """Tool for running code linters and formatters."""

    def __init__(self):
        self._definition = ToolDefinition(
            name="lint",
            description="Run code linters and formatters",
            parameters=[
                ToolParameter(
                    name="tool",
                    type="string",
                    description="Linting tool: 'flake8', 'black', 'eslint', 'prettier', 'auto'",  # noqa: E501
                    required=False,
                    default="auto",
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to code files or directory",
                    required=False,
                    default=".",
                ),
                ToolParameter(
                    name="fix",
                    type="boolean",
                    description="Automatically fix issues when possible",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="config",
                    type="string",
                    description="Config file path",
                    required=False,
                ),
            ],
        )
        super().__init__()

    @property
    def definition(self):
        """Return the lint tool specification.

        Returns:
            ToolDefinition with parameters for running linters and formatters
            including tool selection, path, fix mode, and config options.
        """
        return self._definition

    def _detect_lint_tool(self, path: str) -> List[str]:
        """Detect which linting tools to use based on project files."""
        path_obj = Path(path)
        tools = []

        # Check for Python files
        if path_obj.suffix == ".py" or any(path_obj.glob("**/*.py")):
            if Path("pyproject.toml").exists() or Path("setup.cfg").exists():
                tools.append("black")
            tools.append("flake8")

        # Check for JavaScript/TypeScript files
        if any(path_obj.glob("**/*.js")) or any(path_obj.glob("**/*.ts")):
            if Path("package.json").exists():
                tools.append("eslint")
                tools.append("prettier")

        return tools if tools else ["flake8"]  # Default to flake8

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Run linting tool."""

        tools_to_run = []
        tool = kwargs.get("tool", "auto")
        if tool == "auto":
            tools_to_run = self._detect_lint_tool(kwargs.get("path", "."))
        else:
            tools_to_run = [tool]

        results = []

        for lint_tool in tools_to_run:
            try:
                if lint_tool == "flake8":
                    cmd = ["flake8", kwargs.get("path", ".")]
                    if kwargs.get("config"):
                        cmd.extend(["--config", kwargs.get("config")])

                elif lint_tool == "black":
                    cmd = ["black", kwargs.get("path", ".")]
                    if not kwargs.get("fix"):
                        cmd.append("--check")
                    if kwargs.get("config"):
                        cmd.extend(["--config", kwargs.get("config")])

                elif lint_tool == "eslint":
                    cmd = ["eslint", kwargs.get("path", ".")]
                    if kwargs.get("fix"):
                        cmd.append("--fix")
                    if kwargs.get("config"):
                        cmd.extend(["--config", kwargs.get("config")])

                elif lint_tool == "prettier":
                    cmd = ["prettier", kwargs.get("path", ".")]
                    if kwargs.get("fix"):
                        cmd.append("--write")
                    else:
                        cmd.append("--check")
                    if kwargs.get("config"):
                        cmd.extend(["--config", kwargs.get("config")])

                else:
                    results.append(f"Unsupported linting tool: {lint_tool}")
                    continue

                # Execute command
                process = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )

                stdout, stderr = await process.communicate()
                output = stdout.decode("utf-8") if stdout else ""
                error = stderr.decode("utf-8") if stderr else ""

                if process.returncode == 0:
                    results.append(f"{lint_tool}: ✓ No issues found")
                else:
                    results.append(f"{lint_tool}: Issues found\n{output}\n{error}")

            except FileNotFoundError:
                results.append(f"{lint_tool}: Tool not found. Please install it first.")
            except Exception as e:
                results.append(f"{lint_tool}: Error - {str(e)}")

        return ToolResult(
            success=True,
            output="\n\n".join(results),
            metadata={
                "tools_run": tools_to_run,
                "path": kwargs.get("path", "."),
                "fix_mode": kwargs.get("fix"),
                "config": kwargs.get("config"),
            },
        )


class CoverageTool(Tool):
    """Tool for measuring test coverage."""

    def __init__(self):
        self._definition = ToolDefinition(
            name="coverage",
            description="Measure and report test coverage",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to source code",
                    required=False,
                    default=".",
                ),
                ToolParameter(
                    name="format",
                    type="string",
                    description="Report format: 'text', 'html', 'xml'",
                    required=False,
                    default="text",
                ),
                ToolParameter(
                    name="min_coverage",
                    type="number",
                    description="Minimum coverage percentage required",
                    required=False,
                    default=80,
                ),
            ],
        )
        super().__init__()

    @property
    def definition(self):
        """Return the coverage tool specification.

        Returns:
            ToolDefinition with parameters for measuring test coverage
            including path, report format, and minimum coverage threshold.
        """
        return self._definition

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Measure test coverage."""
        try:
            # Run coverage with pytest
            cmd = [
                "python",
                "-m",
                "coverage",
                "run",
                "-m",
                "pytest",
                kwargs.get("path", "."),
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            await process.communicate()

            # Generate coverage report
            if kwargs.get("format") == "html":
                report_cmd = ["python", "-m", "coverage", "html"]
            elif kwargs.get("format") == "xml":
                report_cmd = ["python", "-m", "coverage", "xml"]
            else:
                report_cmd = ["python", "-m", "coverage", "report"]

            process = await asyncio.create_subprocess_exec(
                *report_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()
            output = stdout.decode("utf-8") if stdout else ""
            error = stderr.decode("utf-8") if stderr else ""

            # Extract coverage percentage
            coverage_percent = 0
            for line in output.split("\n"):
                if "TOTAL" in line and "%" in line:
                    try:
                        coverage_percent = int(line.split()[-1].replace("%", ""))
                    except Exception:  # nosec
                        pass

            success = coverage_percent >= kwargs.get("min_coverage", 80)

            return ToolResult(
                success=success,
                output=output,
                error=error if error else None,
                metadata={
                    "coverage_percent": coverage_percent,
                    "min_coverage": kwargs.get("min_coverage", 80),
                    "format": kwargs.get("format", "text"),
                },
            )

        except FileNotFoundError:
            return ToolResult(
                success=False,
                output="",
                error="Coverage tool not found. Install with: pip install coverage",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Coverage measurement failed: {str(e)}"
            )
