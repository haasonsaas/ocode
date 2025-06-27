"""
Advanced Git integration tools.

This module provides advanced Git operations including add, pull, push, clone,
reset, and stash functionality with structured output support.
"""

import contextlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from git import InvalidGitRepositoryError, Repo
from git.exc import GitCommandError

from .base import ResourceLock, Tool, ToolDefinition, ToolParameter, ToolResult


class GitAddTool(Tool):
    """Tool for adding files to git staging area."""

    @property
    def definition(self) -> ToolDefinition:
        """Define the git_add tool specification."""
        return ToolDefinition(
            name="git_add",
            description="Add files to git staging area",
            category="Git Operations",
            resource_locks=[ResourceLock.GIT],
            parameters=[
                ToolParameter(
                    name="files",
                    type="array",
                    description="List of files/patterns to add (use ['.'] to add all)",
                    required=True,
                ),
                ToolParameter(
                    name="update",
                    type="boolean",
                    description="Only add files that are already tracked",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="Repository path (default: current directory)",
                    required=False,
                    default=".",
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Add files to git staging area."""
        path = kwargs.get("path", ".")
        files = kwargs.get("files", [])
        update_only = kwargs.get("update", False)
        repo = None

        try:
            repo = Repo(path, search_parent_directories=True)

            if not files:
                return ToolResult(
                    success=False, output="", error="No files specified to add"
                )

            # Handle the update flag
            if update_only:
                # Only add tracked files
                repo.git.add(files, update=True)
            else:
                # Add all specified files
                repo.index.add(files)

            # Get list of staged files
            staged = [item.a_path for item in repo.index.diff("HEAD")]

            return ToolResult(
                success=True,
                output=f"Added {len(staged)} file(s) to staging area",
                metadata={
                    "staged_files": staged,
                    "staged_count": len(staged),
                },
            )

        except InvalidGitRepositoryError:
            return ToolResult(success=False, output="", error="Not a git repository")
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Git add failed: {str(e)}"
            )
        finally:
            if repo is not None:
                with contextlib.suppress(Exception):
                    repo.close()


class GitPullTool(Tool):
    """Tool for pulling changes from remote repository."""

    @property
    def definition(self) -> ToolDefinition:
        """Define the git_pull tool specification."""
        return ToolDefinition(
            name="git_pull",
            description="Pull changes from remote repository",
            category="Git Operations",
            resource_locks=[ResourceLock.GIT],
            parameters=[
                ToolParameter(
                    name="remote",
                    type="string",
                    description="Name of the remote",
                    required=False,
                    default="origin",
                ),
                ToolParameter(
                    name="branch",
                    type="string",
                    description="Name of the branch to pull",
                    required=False,
                ),
                ToolParameter(
                    name="rebase",
                    type="boolean",
                    description="Rebase onto the upstream branch",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="Repository path (default: current directory)",
                    required=False,
                    default=".",
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Pull changes from remote repository."""
        path = kwargs.get("path", ".")
        remote = kwargs.get("remote", "origin")
        branch = kwargs.get("branch")
        rebase = kwargs.get("rebase", False)
        repo = None

        try:
            repo = Repo(path, search_parent_directories=True)

            # Get current branch if not specified
            if not branch:
                branch = repo.active_branch.name

            # Build pull command
            pull_info = None
            if rebase:
                pull_info = repo.git.pull(remote, branch, rebase=True)
            else:
                pull_info = repo.git.pull(remote, branch)

            # Parse the output
            output_lines = []
            if "Already up to date" in pull_info:
                output_lines.append("Already up to date.")
            else:
                output_lines.append(f"Pulled from {remote}/{branch}")
                if pull_info:
                    output_lines.append(pull_info)

            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                metadata={
                    "remote": remote,
                    "branch": branch,
                    "rebase": rebase,
                    "current_commit": repo.head.commit.hexsha[:8],
                },
            )

        except InvalidGitRepositoryError:
            return ToolResult(success=False, output="", error="Not a git repository")
        except GitCommandError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Git pull failed: {e.stderr if e.stderr else str(e)}",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Git pull failed: {str(e)}"
            )
        finally:
            if repo is not None:
                with contextlib.suppress(Exception):
                    repo.close()


class GitPushTool(Tool):
    """Tool for pushing changes to remote repository."""

    @property
    def definition(self) -> ToolDefinition:
        """Define the git_push tool specification."""
        return ToolDefinition(
            name="git_push",
            description="Push changes to remote repository",
            category="Git Operations",
            resource_locks=[ResourceLock.GIT],
            parameters=[
                ToolParameter(
                    name="remote",
                    type="string",
                    description="Name of the remote",
                    required=False,
                    default="origin",
                ),
                ToolParameter(
                    name="branch",
                    type="string",
                    description="Name of the branch to push",
                    required=False,
                ),
                ToolParameter(
                    name="force",
                    type="boolean",
                    description="Force push (use with caution)",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="set_upstream",
                    type="boolean",
                    description="Set upstream tracking for the branch",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="Repository path (default: current directory)",
                    required=False,
                    default=".",
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Push changes to remote repository."""
        path = kwargs.get("path", ".")
        remote = kwargs.get("remote", "origin")
        branch = kwargs.get("branch")
        force = kwargs.get("force", False)
        set_upstream = kwargs.get("set_upstream", False)
        repo = None

        try:
            repo = Repo(path, search_parent_directories=True)

            # Get current branch if not specified
            if not branch:
                branch = repo.active_branch.name

            # Build push command
            push_args = [remote, branch]
            push_kwargs = {}

            if force:
                push_kwargs["force"] = True

            if set_upstream:
                push_kwargs["set_upstream"] = True

            # Execute push
            push_info = repo.git.push(*push_args, **push_kwargs)

            # Parse output
            output_lines = [f"Pushed to {remote}/{branch}"]
            if push_info:
                output_lines.append(push_info)

            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                metadata={
                    "remote": remote,
                    "branch": branch,
                    "force": force,
                    "current_commit": repo.head.commit.hexsha[:8],
                },
            )

        except InvalidGitRepositoryError:
            return ToolResult(success=False, output="", error="Not a git repository")
        except GitCommandError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Git push failed: {e.stderr if e.stderr else str(e)}",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Git push failed: {str(e)}"
            )
        finally:
            if repo is not None:
                with contextlib.suppress(Exception):
                    repo.close()


class GitCloneTool(Tool):
    """Tool for cloning git repositories."""

    @property
    def definition(self) -> ToolDefinition:
        """Define the git_clone tool specification."""
        return ToolDefinition(
            name="git_clone",
            description="Clone a git repository",
            category="Git Operations",
            resource_locks=[ResourceLock.GIT],
            parameters=[
                ToolParameter(
                    name="repository_url",
                    type="string",
                    description="URL of the repository to clone",
                    required=True,
                ),
                ToolParameter(
                    name="destination_path",
                    type="string",
                    description="Directory to clone into",
                    required=False,
                ),
                ToolParameter(
                    name="branch",
                    type="string",
                    description="Specific branch to clone",
                    required=False,
                ),
                ToolParameter(
                    name="depth",
                    type="number",
                    description="Create a shallow clone with history truncated to specified number of commits",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Clone a git repository."""
        repository_url = kwargs.get("repository_url")
        destination_path = kwargs.get("destination_path")
        branch = kwargs.get("branch")
        depth = kwargs.get("depth")

        if not repository_url:
            return ToolResult(
                success=False, output="", error="Repository URL is required"
            )

        try:
            # Determine destination path
            if not destination_path:
                # Extract repo name from URL
                repo_name = repository_url.rstrip("/").split("/")[-1]
                if repo_name.endswith(".git"):
                    repo_name = repo_name[:-4]
                destination_path = repo_name

            # Build clone arguments
            clone_kwargs = {}
            if branch:
                clone_kwargs["branch"] = branch
            if depth:
                clone_kwargs["depth"] = depth

            # Clone the repository
            repo = Repo.clone_from(repository_url, destination_path, **clone_kwargs)

            # Get basic info about cloned repo
            result_info = {
                "destination": os.path.abspath(destination_path),
                "branch": repo.active_branch.name,
                "commit": repo.head.commit.hexsha[:8],
                "remote_url": repository_url,
            }

            output_lines = [
                f"Cloned repository to {result_info['destination']}",
                f"Branch: {result_info['branch']}",
                f"Commit: {result_info['commit']}",
            ]

            # Close the repo
            repo.close()

            return ToolResult(
                success=True, output="\n".join(output_lines), metadata=result_info
            )

        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Git clone failed: {str(e)}"
            )


class GitResetTool(Tool):
    """Tool for resetting git repository state."""

    @property
    def definition(self) -> ToolDefinition:
        """Define the git_reset tool specification."""
        return ToolDefinition(
            name="git_reset",
            description="Reset git repository to a specific state",
            category="Git Operations",
            resource_locks=[ResourceLock.GIT],
            parameters=[
                ToolParameter(
                    name="mode",
                    type="string",
                    description="Reset mode: 'soft', 'mixed', 'hard'",
                    required=True,
                ),
                ToolParameter(
                    name="commit",
                    type="string",
                    description="Target commit (default: HEAD)",
                    required=False,
                    default="HEAD",
                ),
                ToolParameter(
                    name="dry_run",
                    type="boolean",
                    description="Simulate the action without making changes",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="Repository path (default: current directory)",
                    required=False,
                    default=".",
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Reset git repository state."""
        path = kwargs.get("path", ".")
        mode = kwargs.get("mode")
        commit = kwargs.get("commit", "HEAD")
        dry_run = kwargs.get("dry_run", False)
        repo = None

        if mode not in ["soft", "mixed", "hard"]:
            return ToolResult(
                success=False,
                output="",
                error="Invalid mode. Use 'soft', 'mixed', or 'hard'",
            )

        try:
            repo = Repo(path, search_parent_directories=True)

            # Get current state for comparison
            current_commit = repo.head.commit.hexsha[:8]

            if dry_run:
                # Simulate the reset
                target_commit = repo.commit(commit)
                output_lines = [
                    f"DRY RUN: Would reset ({mode}) to {target_commit.hexsha[:8]}",
                    f"Current commit: {current_commit}",
                    f"Target commit: {target_commit.hexsha[:8]} - {str(target_commit.summary)}",
                ]

                # Show what would be affected
                if mode == "hard":
                    output_lines.append(
                        "Warning: All uncommitted changes would be lost!"
                    )
                elif mode == "mixed":
                    output_lines.append("Staged changes would be unstaged")
                else:  # soft
                    output_lines.append("All changes would remain staged")

                return ToolResult(
                    success=True,
                    output="\n".join(output_lines),
                    metadata={
                        "dry_run": True,
                        "mode": mode,
                        "current_commit": current_commit,
                        "target_commit": target_commit.hexsha[:8],
                    },
                )

            # Perform actual reset
            repo.git.reset(f"--{mode}", commit)

            new_commit = repo.head.commit.hexsha[:8]

            return ToolResult(
                success=True,
                output=f"Reset ({mode}) to {new_commit}",
                metadata={
                    "mode": mode,
                    "previous_commit": current_commit,
                    "current_commit": new_commit,
                },
            )

        except InvalidGitRepositoryError:
            return ToolResult(success=False, output="", error="Not a git repository")
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Git reset failed: {str(e)}"
            )
        finally:
            if repo is not None:
                with contextlib.suppress(Exception):
                    repo.close()


class GitStashTool(Tool):
    """Tool for managing git stash."""

    @property
    def definition(self) -> ToolDefinition:
        """Define the git_stash tool specification."""
        return ToolDefinition(
            name="git_stash",
            description="Manage git stash for temporary storage of changes",
            category="Git Operations",
            resource_locks=[ResourceLock.GIT],
            parameters=[
                ToolParameter(
                    name="action",
                    type="string",
                    description="Action: 'save', 'list', 'pop', 'apply', 'drop', 'clear'",
                    required=True,
                ),
                ToolParameter(
                    name="message",
                    type="string",
                    description="Message for 'save' action",
                    required=False,
                ),
                ToolParameter(
                    name="stash_id",
                    type="string",
                    description="Stash entry to apply/drop (e.g., 'stash@{0}')",
                    required=False,
                ),
                ToolParameter(
                    name="include_untracked",
                    type="boolean",
                    description="Include untracked files in stash",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="Repository path (default: current directory)",
                    required=False,
                    default=".",
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Manage git stash."""
        path = kwargs.get("path", ".")
        action = kwargs.get("action")
        message = kwargs.get("message")
        stash_id = kwargs.get("stash_id")
        include_untracked = kwargs.get("include_untracked", False)
        repo = None

        try:
            repo = Repo(path, search_parent_directories=True)

            if action == "save":
                # Save changes to stash
                stash_args = []
                if include_untracked:
                    stash_args.append("-u")
                if message:
                    stash_args.extend(["save", message])
                else:
                    stash_args.append("save")

                result = repo.git.stash(*stash_args)

                return ToolResult(
                    success=True,
                    output=result if result else "Created new stash entry",
                    metadata={"action": "save", "message": message},
                )

            elif action == "list":
                # List stash entries
                try:
                    stash_list = repo.git.stash("list")
                    if not stash_list:
                        return ToolResult(
                            success=True,
                            output="No stash entries found",
                            metadata={"stash_count": 0},
                        )

                    entries = stash_list.strip().split("\n")
                    return ToolResult(
                        success=True,
                        output=stash_list,
                        metadata={"stash_count": len(entries), "entries": entries},
                    )
                except Exception:
                    return ToolResult(
                        success=True,
                        output="No stash entries found",
                        metadata={"stash_count": 0},
                    )

            elif action == "pop":
                # Pop latest stash or specified stash
                args = ["pop"]
                if stash_id:
                    args.append(stash_id)

                result = repo.git.stash(*args)

                return ToolResult(
                    success=True,
                    output=result,
                    metadata={"action": "pop", "stash_id": stash_id},
                )

            elif action == "apply":
                # Apply stash without removing it
                args = ["apply"]
                if stash_id:
                    args.append(stash_id)

                result = repo.git.stash(*args)

                return ToolResult(
                    success=True,
                    output=result,
                    metadata={"action": "apply", "stash_id": stash_id},
                )

            elif action == "drop":
                # Drop a stash entry
                args = ["drop"]
                if stash_id:
                    args.append(stash_id)

                result = repo.git.stash(*args)

                return ToolResult(
                    success=True,
                    output=(
                        result if result else f"Dropped stash {stash_id or 'stash@{0}'}"
                    ),
                    metadata={"action": "drop", "stash_id": stash_id},
                )

            elif action == "clear":
                # Clear all stash entries
                repo.git.stash("clear")

                return ToolResult(
                    success=True,
                    output="Cleared all stash entries",
                    metadata={"action": "clear"},
                )

            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Invalid action: {action}. Use 'save', 'list', 'pop', 'apply', 'drop', or 'clear'",
                )

        except InvalidGitRepositoryError:
            return ToolResult(success=False, output="", error="Not a git repository")
        except GitCommandError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Git stash failed: {e.stderr if e.stderr else str(e)}",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Git stash failed: {str(e)}"
            )
        finally:
            if repo is not None:
                with contextlib.suppress(Exception):
                    repo.close()


class GitStatusJSONTool(Tool):
    """Enhanced git status with JSON output support."""

    @property
    def definition(self) -> ToolDefinition:
        """Define the enhanced git_status tool specification."""
        return ToolDefinition(
            name="git_status_json",
            description="Get git repository status with optional JSON output",
            category="Git Operations",
            resource_locks=[ResourceLock.GIT],
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Repository path (default: current directory)",
                    required=False,
                    default=".",
                ),
                ToolParameter(
                    name="format",
                    type="string",
                    description="Output format: 'text' or 'json'",
                    required=False,
                    default="text",
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Get git status with optional JSON output."""
        path = kwargs.get("path", ".")
        output_format = kwargs.get("format", "text")
        repo = None

        try:
            repo = Repo(path, search_parent_directories=True)

            # Gather status information
            status_data: Dict[str, Any] = {
                "branch": repo.active_branch.name,
                "commit": repo.head.commit.hexsha,
                "commit_short": repo.head.commit.hexsha[:8],
                "commit_message": repo.head.commit.summary,
                "author": str(repo.head.commit.author),
                "staged_files": [],
                "modified_files": [],
                "untracked_files": [],
                "deleted_files": [],
                "renamed_files": [],
            }

            # Get file statuses
            # Staged files
            for item in repo.index.diff("HEAD"):
                if item.change_type == "A":
                    status_data["staged_files"].append(item.a_path)
                elif item.change_type == "M":
                    status_data["staged_files"].append(item.a_path)
                elif item.change_type == "D":
                    status_data["deleted_files"].append(item.a_path)
                elif item.change_type == "R":
                    status_data["renamed_files"].append(
                        {"from": item.a_path, "to": item.b_path}
                    )

            # Modified files (not staged)
            for item in repo.index.diff(None):
                status_data["modified_files"].append(item.a_path)

            # Untracked files
            status_data["untracked_files"] = repo.untracked_files

            # Calculate summary
            status_data["summary"] = {
                "staged_count": len(status_data["staged_files"]),
                "modified_count": len(status_data["modified_files"]),
                "untracked_count": len(status_data["untracked_files"]),
                "deleted_count": len(status_data["deleted_files"]),
                "renamed_count": len(status_data["renamed_files"]),
                "is_clean": (
                    len(status_data["staged_files"]) == 0
                    and len(status_data["modified_files"]) == 0
                    and len(status_data["untracked_files"]) == 0
                    and len(status_data["deleted_files"]) == 0
                    and len(status_data["renamed_files"]) == 0
                ),
            }

            if output_format == "json":
                return ToolResult(
                    success=True,
                    output=json.dumps(status_data, indent=2),
                    metadata=status_data["summary"],
                )
            else:
                # Format as text
                lines = [
                    f"Branch: {status_data['branch']}",
                    f"Commit: {status_data['commit_short']} - {str(status_data['commit_message'])}",
                    f"Author: {status_data['author']}",
                    "",
                ]

                if status_data["staged_files"]:
                    lines.append("Staged files:")
                    for f in status_data["staged_files"]:
                        lines.append(f"  + {f}")
                    lines.append("")

                if status_data["modified_files"]:
                    lines.append("Modified files:")
                    for f in status_data["modified_files"]:
                        lines.append(f"  M {f}")
                    lines.append("")

                if status_data["deleted_files"]:
                    lines.append("Deleted files:")
                    for f in status_data["deleted_files"]:
                        lines.append(f"  - {f}")
                    lines.append("")

                if status_data["renamed_files"]:
                    lines.append("Renamed files:")
                    for r in status_data["renamed_files"]:
                        lines.append(f"  R {r.get('from', '')} -> {r.get('to', '')}")
                    lines.append("")

                if status_data["untracked_files"]:
                    lines.append("Untracked files:")
                    for f in status_data["untracked_files"]:
                        lines.append(f"  ? {f}")
                    lines.append("")

                if status_data["summary"]["is_clean"]:
                    lines.append("Working directory clean")

                return ToolResult(
                    success=True,
                    output="\n".join(lines).strip(),
                    metadata=status_data["summary"],
                )

        except InvalidGitRepositoryError:
            return ToolResult(success=False, output="", error="Not a git repository")
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Git status failed: {str(e)}"
            )
        finally:
            if repo is not None:
                with contextlib.suppress(Exception):
                    repo.close()
