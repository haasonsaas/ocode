# Existing Tool Improvements Specification

This document details proposed improvements for existing OCode tools, aiming to enhance their functionality, efficiency, and user-friendliness.

## 1. File System Operations Tools Improvements

### 1.1. `file_read`

**Description:** Enhance file reading capabilities with support for specific line ranges and improved handling of different file types.

**Improvements:**

*   **Read Line Ranges:** Add `start_line` and `end_line` parameters to read specific line ranges from text files.
*   **Content Type Detection:** Implement automatic detection of binary vs. text files, with options for how to handle binary content (e.g., warn, return base64, skip).
*   **Streaming Support:** For very large files, provide a mechanism to read content in chunks or as a stream.

**Modified Parameters:**

*   **`path`** (string, **required**): Path to the file to read.
*   **`encoding`** (string, *optional*, default: `utf-8`): File encoding.
*   **`offset`** (number, *optional*, default: `0`): Start reading from this byte offset.
*   **`limit`** (number, *optional*, default: `-1`): Maximum number of bytes to read.
*   **`start_line`** (number, *optional*): 1-based starting line number for text files.
*   **`end_line`** (number, *optional*): 1-based ending line number for text files.
*   **`binary_mode`** (string, *optional*, default: `auto`): How to handle binary files: `auto` (detect and warn), `force_text` (attempt text decode), `force_binary` (return base64).

**Example Usage:**

```python
# Read lines 10 to 20 of a file
file_read(path="/path/to/my_script.py", start_line=10, end_line=20)

# Read a binary file as base64
file_read(path="/path/to/image.png", binary_mode="force_binary")
```

**Integration Notes:**

*   `start_line` and `end_line` will require efficient line-by-line reading without loading the entire file into memory.
*   Binary mode will need `base64` encoding/decoding.

---

### 1.2. `file_write`

**Description:** Enhance file writing with overwrite protection and binary content support.

**Improvements:**

*   **Overwrite Protection:** Add an `overwrite` parameter to prevent accidental data loss.
*   **Binary Content Support:** Allow writing raw binary data.

**Modified Parameters:**

*   **`path`** (string, **required**): Path to the file to write.
*   **`content`** (string or bytes, **required**): Content to write (can be string or bytes).
*   **`encoding`** (string, *optional*, default: `utf-8`): File encoding (for string content).
*   **`create_dirs`** (boolean, *optional*, default: `true`): Create parent directories if they don't exist.
*   **`append`** (boolean, *optional*, default: `false`): Append to file instead of overwriting.
*   **`overwrite`** (boolean, *optional*, default: `true`): If `false`, returns an error if the file already exists.

**Example Usage:**

```python
# Write content, but prevent overwrite if file exists
file_write(path="/path/to/new_file.txt", content="Hello", overwrite=False)

# Write binary data
file_write(path="/path/to/output.bin", content=b'\x00\x01\x02')
```

**Integration Notes:**

*   `overwrite=false` will require a file existence check before writing.
*   Handling `bytes` content will bypass encoding.

---

### 1.3. `file_edit`

**Description:** Improve in-place file editing with advanced replacement options and a dry-run mode.

**Improvements:**

*   **Regex Group Replacement:** Allow using regex capture groups in the `replacement` string.
*   **Dry Run Mode:** Add a `dry_run` option to preview changes without modifying the file.
*   **Transform Operation:** Introduce a `transform` operation that applies a given script or function to modify content.

**Modified Parameters:**

*   **`path`** (string, **required**): Path to the file to edit.
*   **`operation`** (string, **required**): Edit operation: `replace`, `insert`, `delete`, `append`, `prepend`, `transform`.
*   **`content`** (string, *optional*): Content to insert/append/prepend.
*   **`search_pattern`** (string, *optional*): Pattern to search for.
*   **`replacement`** (string, *optional*): Replacement text (supports regex groups).
*   **`line_number`** (number, *optional*): Specific line number.
*   **`line_range`** (object, *optional*): Line range `{"start": 1, "end": 10}`.
*   **`regex`** (boolean, *optional*, default: `false`): Treat `search_pattern` as regex.
*   **`case_sensitive`** (boolean, *optional*, default: `true`): Case-sensitive search.
*   **`whole_word`** (boolean, *optional*, default: `false`): Match whole words only.
*   **`max_replacements`** (number, *optional*, default: `0`): Maximum number of replacements (0 = unlimited).
*   **`backup`** (boolean, *optional*, default: `true`): Create backup file before editing.
*   **`dry_run`** (boolean, *optional*, default: `false`): Show changes without applying them.
*   **`transform_script`** (string, *optional*): Python script or function to apply for `transform` operation. The script will receive the file content as input and return the modified content.

**Example Usage:**

```python
# Replace using regex groups
file_edit(path="/path/to/log.txt", operation="replace", search_pattern="(ERROR): (.*)", replacement="[\1] - Message: \2")

# Dry run a deletion
file_edit(path="/path/to/config.ini", operation="delete", search_pattern="#old_setting", dry_run=True)

# Transform content using a Python script
file_edit(path="/path/to/data.json", operation="transform", transform_script="""
import json
data = json.loads(content)
data['status'] = 'processed'
return json.dumps(data, indent=2)
""")
```

**Integration Notes:**

*   `transform_script` will require a secure execution environment (e.g., sandboxed Python interpreter).
*   Regex group replacement will need careful implementation using `re.sub`.

---

### 1.4. `file_list` (and `ls`)

**Description:** Enhance directory listing with more filtering, sorting, and display options.

**Improvements:**

*   **Advanced Filtering:** Filter by file size, modification date, creation date, and ownership.
*   **Detailed Metadata:** Include file permissions, owner, and group information.
*   **Tree View:** Support for displaying directory contents in a tree-like structure.

**Modified Parameters:**

*   **`path`** (string, *optional*, default: `.`): Path to list.
*   **`recursive`** (boolean, *optional*, default: `false`): List files recursively.
*   **`include_hidden`** (boolean, *optional*, default: `false`): Include hidden files.
*   **`extensions`** (array, *optional*): Filter by file extensions.
*   **`pattern`** (string, *optional*): Glob pattern to filter files.
*   **`max_depth`** (number, *optional*, default: `-1`): Maximum directory depth for recursive listing.
*   **`min_size`** (string, *optional*): Minimum file size (e.g., `1KB`, `1MB`).
*   **`max_size`** (string, *optional*): Maximum file size.
*   **`modified_before`** (string, *optional*): ISO timestamp: only files modified before this time.
*   **`modified_after`** (string, *optional*): ISO timestamp: only files modified after this time.
*   **`created_before`** (string, *optional*): ISO timestamp: only files created before this time.
*   **`created_after`** (string, *optional*): ISO timestamp: only files created after this time.
*   **`owner`** (string, *optional*): Filter by file owner username.
*   **`group`** (string, *optional*): Filter by file group name.
*   **`sort_by`** (string, *optional*, default: `name`): Sort by: `name`, `size`, `modified`, `created`.
*   **`reverse_sort`** (boolean, *optional*, default: `false`): Reverse sort order.
*   **`show_tree`** (boolean, *optional*, default: `false`): Display as a tree structure when `recursive` is true.
*   **`long_format`** (boolean, *optional*, default: `true`): Show detailed permissions, size, date, etc.

**Example Usage:**

```python
# List all Python files modified in the last 24 hours, sorted by size
file_list(path=".", extensions=[".py"], modified_after="2023-10-26T00:00:00Z", sort_by="size", reverse_sort=True)

# Show a tree view of the current directory up to depth 2
ls(path=".", recursive=True, max_depth=2, show_tree=True)
```

**Integration Notes:**

*   Date/time filtering will require parsing ISO timestamps and comparing file system timestamps.
*   Tree view formatting will need careful recursive output generation.

---

### 1.5. `file_search` (and `grep`, `code_grep`)

**Description:** Improve file content searching with `gitignore` integration and performance optimizations.

**Improvements:**

*   **Respect `.gitignore`:** Automatically exclude files and directories specified in `.gitignore`.
*   **Max File Size:** Add a `max_file_size` parameter to skip searching in very large files.
*   **Count Only:** Option to return only the number of matches found, without the actual content.
*   **AST-based Code Search (`code_grep`):** For `code_grep`, enhance language-specific parsing to understand Abstract Syntax Trees (ASTs) for more accurate semantic searches (e.g., finding all references to a function, not just text matches).

**Modified Parameters:**

*   **`pattern`** (string, **required**): Text pattern to search for (supports regex).
*   **`path`** (string, *optional*, default: `.`): Path to search in.
*   **`extensions`** (array, *optional*): File extensions to search in.
*   **`case_sensitive`** (boolean, *optional*, default: `false`): Case sensitive search.
*   **`max_results`** (number, *optional*, default: `50`): Maximum number of results to return.
*   **`context_lines`** (number, *optional*, default: `0`): Number of context lines to show.
*   **`respect_gitignore`** (boolean, *optional*, default: `true`): Exclude files/dirs in `.gitignore`.
*   **`max_file_size`** (string, *optional*): Maximum file size to search (e.g., `10MB`).
*   **`count_only`** (boolean, *optional*, default: `false`): If `true`, returns only the count of matches.
*   **`language`** (string, *optional*): For `code_grep`, the programming language to enable AST-based search.

**Example Usage:**

```python
# Search for a pattern, respecting .gitignore and skipping large files
file_search(pattern="my_function", path=".", respect_gitignore=True, max_file_size="5MB")

# Count occurrences of a variable in Python files
code_grep(pattern="my_variable", language="python", count_only=True)
```

**Integration Notes:**

*   `.gitignore` parsing will require a library or custom implementation.
*   AST-based parsing for `code_grep` will be a significant undertaking, requiring language-specific parsers (e.g., `ast` for Python, `tree-sitter` bindings for others).

---

### 1.6. `cp`, `mv`, `rm`

**Description:** Add progress indicators and enhance safety for file operations.

**Improvements:**

*   **Progress Indicator:** For large file operations, provide a progress update.
*   **Force Option (`rm`):** Clarify and enhance the `force` option for `rm` to bypass specific safety checks.

**Modified Parameters:**

*   **`source`**, **`destination`**, **`path`** (as existing).
*   **`recursive`**, **`preserve`** (as existing).
*   **`progress`** (boolean, *optional*, default: `false`): Show progress for large operations.
*   **`force`** (boolean, *optional*, default: `false`): For `rm`, bypass additional safety checks (e.g., large directory confirmation).

**Example Usage:**

```python
# Copy a large directory with progress updates
cp(source="/large/data", destination="/backup/data", recursive=True, progress=True)

# Force remove a large directory
rm(path="/tmp/old_logs", recursive=True, force=True)
```

**Integration Notes:**

*   Progress indicators will require monitoring file I/O during operations.
*   `force` for `rm` needs careful implementation to avoid unintended data loss.

---

### 1.7. `glob` and `advanced_glob`

**Description:** Improve globbing with `.gitignore` integration and more flexible pattern matching.

**Improvements:**

*   **Respect `.gitignore`:** Automatically exclude files and directories specified in `.gitignore`.
*   **Multiple Patterns:** Allow specifying multiple include and exclude patterns.

**Modified Parameters:**

*   **`pattern`** (string or array of strings, **required**): Glob pattern(s) to match.
*   **`path`** (string, *optional*, default: `.`): Base path to search from.
*   **`recursive`** (boolean, *optional*, default: `true`): Enable recursive search.
*   **`include_dirs`** (boolean, *optional*, default: `false`): Include directories in results.
*   **`include_hidden`** (boolean, *optional*, default: `false`): Include hidden files.
*   **`max_results`** (number, *optional*, default: `100`): Maximum number of results.
*   **`exclude_patterns`** (array of strings, *optional*): Patterns to exclude from results.
*   **`file_extensions`** (array, *optional*): Filter by file extensions.
*   **`modified_since`** (string, *optional*): ISO timestamp.
*   **`size_range`** (object, *optional*): File size range filter.
*   **`respect_gitignore`** (boolean, *optional*, default: `true`): Exclude files/dirs in `.gitignore`.

**Example Usage:**

```python
# Find all Python and JavaScript files, respecting .gitignore
glob(pattern=["*.py", "*.js"], respect_gitignore=True)

# Find all markdown files except those in 'node_modules'
advanced_glob(pattern="*.md", exclude_patterns=["node_modules/**"])
```

**Integration Notes:**

*   `.gitignore` parsing will be a shared component with `file_search`.
*   Handling multiple patterns will require iterating through each and combining results.

---

### 1.8. `diff`

**Description:** Extend diff capabilities to compare directories and raw strings.

**Improvements:**

*   **Directory Comparison:** Allow comparing two directories, showing differences between files within them.
*   **String Comparison:** Enable direct comparison of two strings without writing them to files.
*   **Output Formats:** Provide options for different diff output formats (e.g., side-by-side, HTML).

**Modified Parameters:**

*   **`source1`** (string, **required**): Path to first file/directory or raw string.
*   **`source2`** (string, **required**): Path to second file/directory or raw string.
*   **`source1_type`** (string, *optional*, default: `auto`): Type of `source1`: `auto`, `file`, `directory`, `string`.
*   **`source2_type`** (string, *optional*, default: `auto`): Type of `source2`: `auto`, `file`, `directory`, `string`.
*   **`unified`** (boolean, *optional*, default: `true`): Use unified diff format.
*   **`context_lines`** (number, *optional*, default: `3`): Number of context lines.
*   **`output_format`** (string, *optional*, default: `text`): Output format: `text`, `html`, `side_by_side`.

**Example Usage:**

```python
# Compare two directories
diff(source1="/project/v1", source2="/project/v2", source1_type="directory", source2_type="directory")

# Compare two strings
diff(source1="Hello World", source2="Hello there World", source1_type="string", source2_type="string")

# Get HTML diff of two files
diff(source1="/file1.txt", source2="/file2.txt", output_format="html")
```

**Integration Notes:**

*   Directory comparison will involve iterating through files in both directories and running file diffs.
*   String comparison will use `difflib` directly.
*   HTML/side-by-side output will require formatting the `difflib` output.

---

### 1.9. `sort` and `uniq`

**Description:** Enhance text processing with column-based operations.

**Improvements:**

*   **Column-based Operations:** Support sorting and uniquing based on specific columns or fields within lines (e.g., for CSV data).

**Modified Parameters:**

*   **`file_path`** (string, *optional*): Path to file.
*   **`text`** (string, *optional*): Text to process.
*   **`reverse`** (boolean, *optional*, default: `false`): Reverse sort order.
*   **`numeric`** (boolean, *optional*, default: `false`): Sort numerically.
*   **`unique`** (boolean, *optional*, default: `false`): Output only unique lines.
*   **`column`** (number, *optional*): 1-based column number to sort/uniq by.
*   **`delimiter`** (string, *optional*, default: ` `): Delimiter for columns.

**Example Usage:**

```python
# Sort a CSV file by the second column
sort(file_path="/path/to/data.csv", column=2, delimiter=",")

# Get unique entries based on the first column of a tab-separated file
uniq(file_path="/path/to/logs.tsv", column=1, delimiter="\t")
```

**Integration Notes:**

*   Column-based operations will require splitting lines by the delimiter and then comparing/hashing the specified column.
