# Code Transformation Tools Specification

This document outlines the specifications for new tools designed to enhance OCode's capabilities in code generation, scaffolding, and refactoring. These tools aim to automate common software engineering tasks, improve developer productivity, and enable more intelligent code modifications.

## 1. Code Generation / Scaffolding Tools

### 1.1. `scaffold_project`

**Description:** Generates a new project structure based on a specified language/framework or a predefined template. This tool automates the initial setup of a project, including directory creation, basic file structures, and configuration files.

**Parameters:**

*   **`project_name`** (string, **required**): The name of the new project. This will typically be used as the root directory name.
*   **`language`** (string, **required**): The primary programming language for the project (e.g., 'python', 'javascript', 'typescript', 'go', 'java').
*   **`framework`** (string, *optional*): The specific framework to use for the project (e.g., 'react', 'nextjs', 'django', 'flask', 'fastapi', 'spring-boot'). If not provided, a basic project structure for the given language will be generated.
*   **`path`** (string, *optional*): The absolute path where the new project directory should be created. Defaults to the current working directory.
*   **`template_url`** (string, *optional*): A URL to a Git repository or a compressed archive containing a custom project template. If provided, this template will override the default framework-specific structures.
*   **`options`** (object, *optional*): A dictionary of additional, framework-specific options for project generation (e.g., `{'typescript': true, 'eslint': true}` for a React project).

**Example Usage:**

```
scaffold_project(project_name="my-react-app", language="javascript", framework="react", path="/Users/username/projects")
scaffold_project(project_name="my-api", language="python", framework="fastapi")
scaffold_project(project_name="custom-project", language="javascript", template_url="https://github.com/my-templates/js-template.git")
```

**Integration Notes:**
*   Will heavily utilize `file_write` for creating files and directories.
*   May use `curl` or `git_clone` (if a new git tool is added) to fetch `template_url`.
*   Could integrate with `lint` or `test_runner` for initial setup verification.

---

### 1.2. `generate_component`

**Description:** Generates a specific code component (e.g., a class, a function, a React component, a database model) within an existing project. This tool helps maintain consistency and accelerates development by creating boilerplate code for common architectural patterns.

**Parameters:**

*   **`component_type`** (string, **required**): The type of component to generate (e.g., 'class', 'function', 'react_component', 'vue_component', 'model', 'controller', 'service', 'test_file').
*   **`name`** (string, **required**): The name of the component (e.g., 'User', 'AuthService', 'ProductCard').
*   **`language`** (string, *optional*): The programming language of the component. If not provided, the tool should attempt to infer it from the `path` or project context.
*   **`path`** (string, **required**): The absolute path to the directory where the component file(s) should be created.
*   **`options`** (object, *optional*): A dictionary of additional, component-specific options (e.g., `{'with_styles': true, 'with_tests': true, 'api_endpoint': '/users'}`).

**Example Usage:**

```
generate_component(component_type="react_component", name="UserProfile", path="/src/components", options={'with_styles': true})
generate_component(component_type="class", name="DatabaseConnector", language="python", path="/src/utils")
generate_component(component_type="model", name="Order", language="python", path="/src/models", options={'fields': ['id:int', 'item:str', 'quantity:int']})
```

**Integration Notes:**
*   Will use `file_write` to create the component files.
*   Can use `code_grep` to analyze existing code for context (e.g., import paths, existing component patterns).
*   Could integrate with `lint` for immediate formatting and `test_runner` for generating basic test stubs.

---

## 2. Refactoring / Code Transformation Tools

### 2.1. `refactor_code`

**Description:** Performs common code refactoring patterns to improve code quality, maintainability, and readability. This tool goes beyond simple text replacement by understanding code structure and semantics.

**Parameters:**

*   **`action`** (string, **required**): The specific refactoring action to perform.
    *   `rename_symbol`: Renames a variable, function, class, or other symbol across one or more files.
    *   `extract_method`: Extracts a block of code into a new method/function.
    *   `change_signature`: Modifies the signature (parameters) of a function or method.
    *   `inline_variable`: Replaces a variable with its value.
    *   `apply_style_guide`: Applies a specific code style guide (e.g., PEP 8, Airbnb JavaScript Style Guide).
*   **`file_path`** (string, *optional*): The absolute path to the primary file where the refactoring is initiated. Required for actions like `extract_method`.
*   **`symbol_name`** (string, *optional*): The current name of the symbol to be refactored (for `rename_symbol`, `inline_variable`).
*   **`new_name`** (string, *optional*): The new name for the symbol (for `rename_symbol`).
*   **`start_line`** (number, *optional*): The starting line number of the code block for actions like `extract_method`.
*   **`end_line`** (number, *optional*): The ending line number of the code block for actions like `extract_method`.
*   **`new_method_name`** (string, *optional*): The name for the new method/function (for `extract_method`).
*   **`target_files`** (array, *optional*): A list of glob patterns or absolute file paths to apply the refactoring to. If not provided, the tool should attempt to infer relevant files (e.g., all files in the project for `rename_symbol`).
*   **`language`** (string, *optional*): The programming language of the code being refactored. If not provided, the tool should attempt to infer it.
*   **`options`** (object, *optional*): Additional action-specific options (e.g., `{'scope': 'project'}` for `rename_symbol`, `{'make_private': true}` for `extract_method`).

**Example Usage:**

```
refactor_code(action="rename_symbol", symbol_name="old_variable_name", new_name="new_variable_name", file_path="/src/utils/helper.py", language="python")
refactor_code(action="extract_method", file_path="/src/main.js", start_line=10, end_line=25, new_method_name="processData", language="javascript")
refactor_code(action="apply_style_guide", file_path="/src/app.py", language="python", options={'style_guide': 'pep8'})
```

**Integration Notes:**
*   This tool will be highly complex and will require deep integration with language-specific parsers (ASTs) for accurate semantic understanding.
*   Will use `file_read` to get code content and `file_edit` (or a more advanced internal modification mechanism) to apply changes.
*   **Crucially**, it must integrate with `test_runner` to run tests before and after refactoring to ensure no regressions are introduced.
*   `lint` should be run after refactoring to ensure style consistency.
*   `code_grep` will be essential for identifying occurrences of symbols or code patterns.
*   Error handling will be critical, especially for partial refactorings or syntax errors.
*   Consider a "dry run" mode to preview changes before applying.

This specification provides a solid foundation for developing these powerful new capabilities.
