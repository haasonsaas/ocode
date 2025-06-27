## 3. Git Operations Tools Improvements

### 3.1. General Git Tools (`git_status`, `git_commit`, `git_diff`, `git_branch`)

**Description:** Enhance existing Git tools with more advanced commands and structured output.

**Improvements:**

*   **Advanced Commands:** Implement `git_add`, `git_pull`, `git_push`, `git_clone`, `git_reset`, `git_stash`.
*   **Structured Output:** Provide more structured and easily parsable output for Git commands, especially for `git_status` and `git_log`.
*   **Dry Run Option:** Add a `dry_run` option for destructive Git commands (e.g., `git_reset`, `git_clean`).

**New/Modified Parameters:**

*   **`git_add`**:
    *   **`files`** (array of strings, **required**): List of files/patterns to add.
    *   **`update`** (boolean, *optional*, default: `false`): Only add files that are already tracked.
*   **`git_pull`**:
    *   **`remote`** (string, *optional*, default: `origin`): Name of the remote.
    *   **`branch`** (string, *optional*): Name of the branch to pull.
    *   **`rebase`** (boolean, *optional*, default: `false`): Rebase onto the upstream branch.
*   **`git_push`**:
    *   **`remote`** (string, *optional*, default: `origin`): Name of the remote.
    *   **`branch`** (string, *optional*): Name of the branch to push.
    *   **`force`** (boolean, *optional*, default: `false`): Force push (use with caution).
*   **`git_clone`**:
    *   **`repository_url`** (string, **required**): URL of the repository to clone.
    *   **`destination_path`** (string, *optional*): Directory to clone into.
    *   **`branch`** (string, *optional*): Specific branch to clone.
*   **`git_reset`**:
    *   **`mode`** (string, **required**): Reset mode: `soft`, `mixed`, `hard`, `merge`, `keep`.
    *   **`commit`** (string, *optional*): Target commit (default: `HEAD`).
*   **`git_stash`**:
    *   **`action`** (string, **required**): Action: `save`, `list`, `pop`, `apply`, `drop`.
    *   **`message`** (string, *optional*): Message for `save` action.
    *   **`stash_id`** (string, *optional*): Stash entry to apply/drop (e.g., `stash@{0}`).
*   **`git_status`**:
    *   **`format`** (string, *optional*, default: `text`): Output format: `text`, `json`.
*   **`git_diff`**:
    *   **`output_format`** (string, *optional*, default: `unified`): Diff output format: `unified`, `json`.
*   **`dry_run`** (boolean, *optional*, default: `false`): For destructive commands, simulate the action without making changes.

**Example Usage:**

```python
# Add all changes to staging
git_add(files=["."])

# Pull changes from origin/main with rebase
git_pull(remote="origin", branch="main", rebase=True)

# Clone a repository
git_clone(repository_url="https://github.com/octocat/Spoon-Knife.git", destination_path="./my-repo")

# Soft reset to a previous commit (dry run)
git_reset(mode="soft", commit="HEAD~1", dry_run=True)

# Get git status in JSON format
git_status(format="json")
```

**Integration Notes:**

*   These commands will primarily interact with the `git` CLI via `bash` or `shell_command`.
*   Parsing and generating structured output (especially JSON) for Git commands will require careful handling of CLI output.
*   `dry_run` for destructive commands is crucial for safety and will involve using `--dry-run` flags where available or simulating the action.
*   Error handling should clearly distinguish between Git errors (e.g., merge conflicts) and tool execution errors.

## 4. Testing & Quality Tools Improvements

### 4.1. `test_runner`

**Description:** Expand test framework support and provide more granular control over test execution.

**Improvements:**

*   **Expanded Framework Support:** Add support for more languages and testing frameworks (e.g., Java/JUnit, C#/NUnit, Rust/Cargo test, PHPUnit, RSpec).
*   **Granular Control:** Allow running specific test cases, classes, or methods.
*   **Integrated Coverage:** Automatically generate and report code coverage after tests.

**Modified Parameters:**

*   **`path`** (string, *optional*): Path to test directory or file.
*   **`framework`** (string, *optional*): Test framework to use (e.g., `pytest`, `unittest`, `jest`, `junit`, `cargo`, `phpunit`, `rspec`).
*   **`verbose`** (boolean, *optional*, default: `false`): Enable verbose output.
*   **`timeout`** (number, *optional*, default: `300`): Test execution timeout in seconds.
*   **`test_filter`** (string, *optional*): Filter for specific tests (e.g., `test_my_feature`, `MyClass.test_method`). Syntax will be framework-dependent.
*   **`generate_coverage`** (boolean, *optional*, default: `false`): If `true`, runs tests with coverage and generates a report.
*   **`coverage_format`** (string, *optional*, default: `text`): Format for coverage report: `text`, `html`, `xml`, `json`.

**Example Usage:**

```python
# Run specific pytest tests with verbose output and coverage
test_runner(path="./tests/unit", framework="pytest", test_filter="test_auth_module", verbose=True, generate_coverage=True, coverage_format="html")

# Run all Java JUnit tests
test_runner(path="./src/main/java", framework="junit")
```

**Integration Notes:**

*   Framework detection will need to be more sophisticated, potentially looking at build files (`pom.xml`, `build.gradle`, `Cargo.toml`, `package.json`) or common test file naming conventions.
*   Running tests and generating coverage will involve executing external commands via `bash` or `shell_command`.
*   Parsing test and coverage reports will be crucial for providing structured results.

---

### 4.2. `lint`

**Description:** Broaden support for more linters and formatters and provide more control over their execution.

**Improvements:**

*   **Expanded Tool Support:** Add support for more linters and formatters across different languages (e.g., `ruff`, `mypy`, `eslint`, `prettier`, `black`, `flake8`, `stylelint`, `clang-format`).
*   **Custom Configuration:** Allow specifying custom configuration files for linters.
*   **Diff Output:** Provide a `diff` output for formatting changes when `fix=false`.

**Modified Parameters:**

*   **`tool`** (string or array of strings, **required**): Linting tool(s) to use (e.g., `flake8`, `black`, `eslint`, `prettier`, `auto`).
*   **`path`** (string, *optional*, default: `.`): Path to code files or directory.
*   **`fix`** (boolean, *optional*, default: `false`): Automatically fix issues when possible.
*   **`config_path`** (string, *optional*): Path to a custom configuration file for the linter.
*   **`output_format`** (string, *optional*, default: `text`): Output format: `text`, `json`, `diff`.
*   **`rules`** (array of strings, *optional*): Specific linting rules to enable or disable.

**Example Usage:**

```python
# Run Black formatter and fix issues
lint(tool="black", path="./src", fix=True)

# Run ESLint and Prettier, show diff of changes
lint(tool=["eslint", "prettier"], path="./src", fix=False, output_format="diff")

# Run MyPy with a custom config file
lint(tool="mypy", path="./src", config_path="./mypy.ini")
```

**Integration Notes:**

*   Executing linters will involve `bash` or `shell_command`.
*   Parsing linter output (especially for `json` or `diff` formats) will require specific parsers for each tool.
*   `config_path` will need to be passed correctly to the respective linter CLI.

---

### 4.3. `coverage`

**Description:** Improve test coverage measurement and reporting, and integrate with test execution.

**Improvements:**

*   **Integrated with `test_runner`:** Allow `coverage` to be run as part of a `test_runner` execution, simplifying the workflow.
*   **Multiple Report Formats:** Support various coverage reporting formats (e.g., Cobertura XML for CI/CD integration, LCOV).
*   **Threshold Enforcement:** Automatically fail if coverage falls below a specified threshold.

**Modified Parameters:**

*   **`path`** (string, *optional*, default: `.`): Path to source code for coverage analysis.
*   **`format`** (string, *optional*, default: `text`): Report format: `text`, `html`, `xml`, `json`, `cobertura`, `lcov`.
*   **`min_coverage`** (number, *optional*, default: `80`): Minimum coverage percentage required for success.
*   **`output_path`** (string, *optional*): Directory to save the coverage report (for `html`, `xml`, etc.).
*   **`test_command`** (string, *optional*): The command to run tests (if not using `test_runner` integration).
*   **`source_files`** (array of strings, *optional*): Specific files or directories to include in coverage analysis.

**Example Usage:**

```python
# Generate HTML coverage report for Python code
coverage(path="./src", format="html", output_path="./coverage_report")

# Run tests and check if coverage is above 90%
test_runner(path="./tests", framework="pytest", generate_coverage=True, min_coverage=90)
```

**Integration Notes:**

*   Deep integration with `test_runner` will require `test_runner` to return coverage data or to trigger `coverage` commands internally.
*   Parsing coverage reports to extract the percentage will be necessary for threshold enforcement.
*   Requires the underlying coverage tools (e.g., `coverage.py` for Python, `nyc` for JavaScript) to be installed and configured.
