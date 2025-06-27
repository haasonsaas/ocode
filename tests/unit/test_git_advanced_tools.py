"""Tests for advanced git tools."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

from ocode_python.tools.git_advanced_tools import (
    GitAddTool,
    GitCloneTool,
    GitPullTool,
    GitPushTool,
    GitResetTool,
    GitStashTool,
    GitStatusJSONTool,
)


@pytest.fixture
def mock_git_repo(tmp_path):
    """Create a mock git repository for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Initialize repo
    repo = Repo.init(repo_path)

    # Create initial files
    (repo_path / "README.md").write_text("# Test Repository")
    (repo_path / "main.py").write_text("print('Hello World')")

    # Add and commit
    repo.index.add(["README.md", "main.py"])
    repo.index.commit("feat: initial commit with test files")

    yield repo_path

    # Cleanup
    repo.close()


@pytest.mark.unit
class TestGitAddTool:
    """Test GitAddTool functionality."""

    @pytest.mark.asyncio
    async def test_add_single_file(self, mock_git_repo):
        """Test adding a single file."""
        tool = GitAddTool()

        # Create a new file
        new_file = mock_git_repo / "new_file.txt"
        new_file.write_text("New content")

        result = await tool.execute(path=str(mock_git_repo), files=["new_file.txt"])

        assert result.success
        assert "Added 1 file(s) to staging area" in result.output
        assert result.metadata["staged_count"] == 1
        assert "new_file.txt" in result.metadata["staged_files"]

    @pytest.mark.asyncio
    async def test_add_all_files(self, mock_git_repo):
        """Test adding all files with '.'."""
        tool = GitAddTool()

        # Create multiple new files
        (mock_git_repo / "file1.txt").write_text("Content 1")
        (mock_git_repo / "file2.txt").write_text("Content 2")

        result = await tool.execute(path=str(mock_git_repo), files=["."])

        assert result.success
        assert result.metadata["staged_count"] >= 2

    @pytest.mark.asyncio
    async def test_add_with_update_flag(self, mock_git_repo):
        """Test adding only tracked files with update flag."""
        tool = GitAddTool()

        # Modify existing file
        (mock_git_repo / "README.md").write_text("# Updated README")

        # Create new untracked file
        (mock_git_repo / "untracked.txt").write_text("Should not be added")

        result = await tool.execute(path=str(mock_git_repo), files=["."], update=True)

        assert result.success
        # Only README.md should be staged, not untracked.txt
        assert "README.md" in result.metadata["staged_files"]
        assert "untracked.txt" not in result.metadata["staged_files"]

    @pytest.mark.asyncio
    async def test_add_no_files_error(self):
        """Test error when no files specified."""
        tool = GitAddTool()

        result = await tool.execute(path=".", files=[])

        assert not result.success
        assert "No files specified" in result.error


@pytest.mark.unit
class TestGitPullTool:
    """Test GitPullTool functionality."""

    @pytest.mark.asyncio
    async def test_pull_success(self):
        """Test successful pull operation."""
        tool = GitPullTool()

        with patch("ocode_python.tools.git_advanced_tools.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.active_branch.name = "main"
            mock_repo.git.pull.return_value = "Already up to date."
            mock_repo.head.commit.hexsha = "abc123def456"

            result = await tool.execute(path=".", remote="origin", branch="main")

            assert result.success
            assert "Already up to date" in result.output
            assert result.metadata["remote"] == "origin"
            assert result.metadata["branch"] == "main"
            assert result.metadata["rebase"] is False

            mock_repo.git.pull.assert_called_once_with("origin", "main")

    @pytest.mark.asyncio
    async def test_pull_with_rebase(self):
        """Test pull with rebase option."""
        tool = GitPullTool()

        with patch("ocode_python.tools.git_advanced_tools.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.active_branch.name = "main"
            mock_repo.git.pull.return_value = (
                "Successfully rebased and updated refs/heads/main."
            )
            mock_repo.head.commit.hexsha = "abc123def456"

            result = await tool.execute(path=".", rebase=True)

            assert result.success
            assert result.metadata["rebase"] is True

            mock_repo.git.pull.assert_called_once_with("origin", "main", rebase=True)

    @pytest.mark.asyncio
    async def test_pull_git_error(self):
        """Test pull with git command error."""
        tool = GitPullTool()

        with patch("ocode_python.tools.git_advanced_tools.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.active_branch.name = "main"

            error = GitCommandError(
                "pull", 1, stderr="error: Your local changes would be overwritten"
            )
            mock_repo.git.pull.side_effect = error

            result = await tool.execute(path=".")

            assert not result.success
            assert "Your local changes would be overwritten" in result.error


@pytest.mark.unit
class TestGitPushTool:
    """Test GitPushTool functionality."""

    @pytest.mark.asyncio
    async def test_push_success(self):
        """Test successful push operation."""
        tool = GitPushTool()

        with patch("ocode_python.tools.git_advanced_tools.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.active_branch.name = "main"
            mock_repo.git.push.return_value = "Everything up-to-date"
            mock_repo.head.commit.hexsha = "abc123def456"

            result = await tool.execute(path=".")

            assert result.success
            assert "Pushed to origin/main" in result.output

            mock_repo.git.push.assert_called_once_with("origin", "main")

    @pytest.mark.asyncio
    async def test_push_with_force(self):
        """Test force push."""
        tool = GitPushTool()

        with patch("ocode_python.tools.git_advanced_tools.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.active_branch.name = "feature"
            mock_repo.git.push.return_value = "forced update"
            mock_repo.head.commit.hexsha = "abc123def456"

            result = await tool.execute(path=".", force=True)

            assert result.success
            assert result.metadata["force"] is True

            mock_repo.git.push.assert_called_once_with("origin", "feature", force=True)

    @pytest.mark.asyncio
    async def test_push_set_upstream(self):
        """Test push with set upstream."""
        tool = GitPushTool()

        with patch("ocode_python.tools.git_advanced_tools.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.active_branch.name = "new-feature"
            mock_repo.git.push.return_value = (
                "Branch 'new-feature' set up to track remote"
            )
            mock_repo.head.commit.hexsha = "abc123def456"

            result = await tool.execute(path=".", set_upstream=True)

            assert result.success

            mock_repo.git.push.assert_called_once_with(
                "origin", "new-feature", set_upstream=True
            )


@pytest.mark.unit
class TestGitCloneTool:
    """Test GitCloneTool functionality."""

    @pytest.mark.asyncio
    async def test_clone_success(self, tmp_path):
        """Test successful repository cloning."""
        tool = GitCloneTool()

        with patch(
            "ocode_python.tools.git_advanced_tools.Repo.clone_from"
        ) as mock_clone:
            mock_repo = MagicMock()
            mock_repo.active_branch.name = "main"
            mock_repo.head.commit.hexsha = "abc123def456"
            mock_clone.return_value = mock_repo

            result = await tool.execute(
                repository_url="https://github.com/test/repo.git",
                destination_path=str(tmp_path / "cloned_repo"),
            )

            assert result.success
            assert "Cloned repository to" in result.output
            assert result.metadata["branch"] == "main"
            assert result.metadata["remote_url"] == "https://github.com/test/repo.git"

    @pytest.mark.asyncio
    async def test_clone_with_branch(self, tmp_path):
        """Test cloning specific branch."""
        tool = GitCloneTool()

        with patch(
            "ocode_python.tools.git_advanced_tools.Repo.clone_from"
        ) as mock_clone:
            mock_repo = MagicMock()
            mock_repo.active_branch.name = "develop"
            mock_repo.head.commit.hexsha = "def456abc123"
            mock_clone.return_value = mock_repo

            result = await tool.execute(
                repository_url="https://github.com/test/repo.git",
                destination_path=str(tmp_path / "cloned_repo"),
                branch="develop",
            )

            assert result.success
            assert result.metadata["branch"] == "develop"

            mock_clone.assert_called_once_with(
                "https://github.com/test/repo.git",
                str(tmp_path / "cloned_repo"),
                branch="develop",
            )

    @pytest.mark.asyncio
    async def test_clone_shallow(self, tmp_path):
        """Test shallow clone with depth."""
        tool = GitCloneTool()

        with patch(
            "ocode_python.tools.git_advanced_tools.Repo.clone_from"
        ) as mock_clone:
            mock_repo = MagicMock()
            mock_repo.active_branch.name = "main"
            mock_repo.head.commit.hexsha = "abc123def456"
            mock_clone.return_value = mock_repo

            result = await tool.execute(
                repository_url="https://github.com/test/repo.git", depth=1
            )

            assert result.success

            # Check that depth was passed
            _, _, kwargs = mock_clone.mock_calls[0]
            assert kwargs["depth"] == 1

    @pytest.mark.asyncio
    async def test_clone_no_url_error(self):
        """Test error when no repository URL provided."""
        tool = GitCloneTool()

        result = await tool.execute(repository_url=None)

        assert not result.success
        assert "Repository URL is required" in result.error


@pytest.mark.unit
class TestGitResetTool:
    """Test GitResetTool functionality."""

    @pytest.mark.asyncio
    async def test_reset_soft(self):
        """Test soft reset."""
        tool = GitResetTool()

        with patch("ocode_python.tools.git_advanced_tools.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.head.commit.hexsha = "abc123def456"

            result = await tool.execute(path=".", mode="soft", commit="HEAD~1")

            assert result.success
            assert "Reset (soft) to" in result.output

            mock_repo.git.reset.assert_called_once_with("--soft", "HEAD~1")

    @pytest.mark.asyncio
    async def test_reset_hard(self):
        """Test hard reset."""
        tool = GitResetTool()

        with patch("ocode_python.tools.git_advanced_tools.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.head.commit.hexsha = "abc123def456"

            result = await tool.execute(path=".", mode="hard", commit="HEAD")

            assert result.success

            mock_repo.git.reset.assert_called_once_with("--hard", "HEAD")

    @pytest.mark.asyncio
    async def test_reset_dry_run(self):
        """Test dry run mode."""
        tool = GitResetTool()

        with patch("ocode_python.tools.git_advanced_tools.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo

            mock_commit = MagicMock()
            mock_commit.hexsha = "abc123def456"
            mock_commit.summary = "Test commit"

            mock_repo.head.commit.hexsha = "def456abc123"
            mock_repo.commit.return_value = mock_commit

            result = await tool.execute(path=".", mode="hard", dry_run=True)

            assert result.success
            assert "DRY RUN" in result.output
            assert "Would reset (hard)" in result.output
            assert result.metadata["dry_run"] is True

            # Ensure reset was not actually called
            mock_repo.git.reset.assert_not_called()

    @pytest.mark.asyncio
    async def test_reset_invalid_mode(self):
        """Test error on invalid reset mode."""
        tool = GitResetTool()

        result = await tool.execute(path=".", mode="invalid")

        assert not result.success
        assert "Invalid mode" in result.error


@pytest.mark.unit
class TestGitStashTool:
    """Test GitStashTool functionality."""

    @pytest.mark.asyncio
    async def test_stash_save(self):
        """Test saving changes to stash."""
        tool = GitStashTool()

        with patch("ocode_python.tools.git_advanced_tools.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.git.stash.return_value = "Saved working directory and index state"

            result = await tool.execute(
                path=".", action="save", message="Work in progress"
            )

            assert result.success
            assert result.metadata["action"] == "save"

            mock_repo.git.stash.assert_called_once_with("save", "Work in progress")

    @pytest.mark.asyncio
    async def test_stash_save_with_untracked(self):
        """Test saving with untracked files."""
        tool = GitStashTool()

        with patch("ocode_python.tools.git_advanced_tools.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.git.stash.return_value = "Saved"

            result = await tool.execute(path=".", action="save", include_untracked=True)

            assert result.success

            mock_repo.git.stash.assert_called_once_with("-u", "save")

    @pytest.mark.asyncio
    async def test_stash_list(self):
        """Test listing stash entries."""
        tool = GitStashTool()

        with patch("ocode_python.tools.git_advanced_tools.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo
            stash_list = (
                "stash@{0}: WIP on main: abc123 Test commit\n"
                "stash@{1}: On feature: def456 Another commit"
            )
            mock_repo.git.stash.return_value = stash_list

            result = await tool.execute(path=".", action="list")

            assert result.success
            assert result.metadata["stash_count"] == 2
            assert len(result.metadata["entries"]) == 2

    @pytest.mark.asyncio
    async def test_stash_pop(self):
        """Test popping from stash."""
        tool = GitStashTool()

        with patch("ocode_python.tools.git_advanced_tools.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.git.stash.return_value = "Dropped refs/stash@{0}"

            result = await tool.execute(path=".", action="pop")

            assert result.success

            mock_repo.git.stash.assert_called_once_with("pop")

    @pytest.mark.asyncio
    async def test_stash_apply_specific(self):
        """Test applying specific stash entry."""
        tool = GitStashTool()

        with patch("ocode_python.tools.git_advanced_tools.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.git.stash.return_value = "Applied stash@{1}"

            result = await tool.execute(path=".", action="apply", stash_id="stash@{1}")

            assert result.success

            mock_repo.git.stash.assert_called_once_with("apply", "stash@{1}")

    @pytest.mark.asyncio
    async def test_stash_clear(self):
        """Test clearing all stash entries."""
        tool = GitStashTool()

        with patch("ocode_python.tools.git_advanced_tools.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo

            result = await tool.execute(path=".", action="clear")

            assert result.success
            assert "Cleared all stash entries" in result.output

            mock_repo.git.stash.assert_called_once_with("clear")

    @pytest.mark.asyncio
    async def test_stash_invalid_action(self):
        """Test error on invalid stash action."""
        tool = GitStashTool()

        result = await tool.execute(path=".", action="invalid")

        assert not result.success
        assert "Invalid action" in result.error


@pytest.mark.unit
class TestGitStatusJSONTool:
    """Test GitStatusJSONTool functionality."""

    @pytest.mark.asyncio
    async def test_status_json_format(self, mock_git_repo):
        """Test JSON output format."""
        tool = GitStatusJSONTool()

        # Create some changes
        (mock_git_repo / "README.md").write_text("# Modified README")
        (mock_git_repo / "new_file.txt").write_text("New file")

        result = await tool.execute(path=str(mock_git_repo), format="json")

        assert result.success

        # Parse JSON output
        status_data = json.loads(result.output)

        assert "branch" in status_data
        assert "commit" in status_data
        assert "staged_files" in status_data
        assert "modified_files" in status_data
        assert "untracked_files" in status_data
        assert "summary" in status_data

        # Check summary
        assert isinstance(status_data["summary"]["is_clean"], bool)
        assert status_data["summary"]["modified_count"] >= 0
        assert status_data["summary"]["untracked_count"] >= 0

    @pytest.mark.asyncio
    async def test_status_text_format(self, mock_git_repo):
        """Test text output format (default)."""
        tool = GitStatusJSONTool()

        result = await tool.execute(path=str(mock_git_repo))

        assert result.success
        assert "Branch:" in result.output
        assert "Commit:" in result.output

        # Should not be JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(result.output)

    @pytest.mark.asyncio
    async def test_status_clean_repo(self, mock_git_repo):
        """Test status of clean repository."""
        tool = GitStatusJSONTool()

        result = await tool.execute(path=str(mock_git_repo), format="json")

        assert result.success

        status_data = json.loads(result.output)
        assert status_data["summary"]["is_clean"] is True

    @pytest.mark.asyncio
    async def test_status_with_various_changes(self, mock_git_repo):
        """Test status with different types of changes."""
        tool = GitStatusJSONTool()
        repo = Repo(mock_git_repo)

        # Create various changes
        # Modified file
        (mock_git_repo / "README.md").write_text("# Changed README")

        # New file (untracked)
        (mock_git_repo / "untracked.txt").write_text("Untracked")

        # Staged new file
        (mock_git_repo / "staged_new.txt").write_text("Staged new")
        repo.index.add(["staged_new.txt"])

        # Renamed file (stage it)
        (mock_git_repo / "main.py").rename(mock_git_repo / "app.py")
        repo.index.add(["app.py"])
        repo.index.remove(["main.py"])

        result = await tool.execute(path=str(mock_git_repo), format="json")

        assert result.success

        status_data = json.loads(result.output)
        assert status_data["summary"]["is_clean"] is False
        assert len(status_data["untracked_files"]) > 0
        assert len(status_data["modified_files"]) > 0

        repo.close()

    @pytest.mark.asyncio
    async def test_status_not_git_repo(self, tmp_path):
        """Test error when not in a git repository."""
        tool = GitStatusJSONTool()

        result = await tool.execute(path=str(tmp_path))

        assert not result.success
        assert "Not a git repository" in result.error
