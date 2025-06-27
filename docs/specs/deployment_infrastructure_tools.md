# Deployment and Infrastructure Management Tools Specification

This document outlines the specifications for new tools that enable OCode to interact with deployment environments, manage infrastructure, and configure CI/CD pipelines. These tools extend OCode's capabilities beyond code development to cover the full software delivery lifecycle.

## 1. Deployment Tools

### 1.1. `deploy_application`

**Description:** Automates the deployment of an application to a specified environment. This tool abstracts away the complexities of different deployment targets (e.g., Kubernetes, AWS Lambda, Azure App Service, Docker Compose, SSH-based deployments), providing a unified interface for application delivery.

**Parameters:**

*   **`application_path`** (string, **required**): The absolute path to the application's source code, build artifacts, or deployment package (e.g., a Docker image tag, a JAR file, a zip archive).
*   **`environment_type`** (string, **required**): The type of deployment environment.
    *   **Enum:** `kubernetes`, `aws_lambda`, `azure_app_service`, `docker_compose`, `ssh`, `gcp_cloud_run`, `heroku`.
*   **`environment_config`** (object, **required**): A dictionary containing configuration details specific to the chosen `environment_type`.
    *   **For `kubernetes`:** `cluster_name` (string), `namespace` (string, optional), `kubeconfig_path` (string, optional), `manifest_path` (string, path to K8s YAMLs).
    *   **For `aws_lambda`:** `function_name` (string), `region` (string), `runtime` (string), `handler` (string), `zip_file_path` (string, path to deployment package).
    *   **For `azure_app_service`:** `app_name` (string), `resource_group` (string), `plan_name` (string), `region` (string), `deployment_source` (string, e.g., Git URL, local path).
    *   **For `docker_compose`:** `compose_file_path` (string, path to `docker-compose.yml`), `project_name` (string, optional).
    *   **For `ssh`:** `host` (string), `username` (string), `private_key_path` (string, optional), `remote_path` (string, target directory on remote host), `pre_deploy_script` (string, optional), `post_deploy_script` (string, optional).
    *   **For `gcp_cloud_run`:** `service_name` (string), `region` (string), `image_tag` (string), `project_id` (string).
    *   **For `heroku`:** `app_name` (string), `buildpack` (string, optional), `git_remote` (string, optional).
*   **`build_command`** (string, *optional*): A shell command to execute for building the application before deployment (e.g., `npm run build`, `mvn clean install`). This command will be run in the `application_path`.
*   **`pre_deploy_commands`** (array of strings, *optional*): A list of shell commands to execute on the local machine before the main deployment action.
*   **`post_deploy_commands`** (array of strings, *optional*): A list of shell commands to execute on the local machine after the main deployment action.
*   **`dry_run`** (boolean, *optional*, default: `false`): If `true`, simulates the deployment process without making actual changes to the environment. Provides a report of what *would* happen.

**Example Usage:**

```
deploy_application(
    application_path="./dist/my-app.zip",
    environment_type="aws_lambda",
    environment_config={
        "function_name": "my-webapp-function",
        "region": "us-east-1",
        "runtime": "nodejs18.x",
        "handler": "index.handler",
        "zip_file_path": "./dist/my-app.zip"
    },
    build_command="npm install && npm run build"
)

deploy_application(
    application_path=".",
    environment_type="docker_compose",
    environment_config={
        "compose_file_path": "./docker-compose.prod.yml",
        "project_name": "my-service"
    },
    pre_deploy_commands=["docker login"]
)

deploy_application(
    application_path="./k8s-manifests",
    environment_type="kubernetes",
    environment_config={
        "cluster_name": "my-prod-cluster",
        "namespace": "production",
        "manifest_path": "./k8s-manifests/deployment.yaml"
    },
    dry_run=True
)
```

**Integration Notes:**
*   Will heavily utilize `bash` or `shell_command` for executing CLI tools specific to each `environment_type` (e.g., `kubectl`, `aws cli`, `az cli`, `docker-compose`, `gcloud`, `heroku`).
*   Can use `file_read` to read deployment manifests or configuration files and `json_yaml` to parse/modify them dynamically.
*   `git_tools` might be used to ensure the latest code is pulled before building/deploying.
*   `test_runner` and `lint` could be integrated as pre-deployment checks.
*   Error handling will be crucial, with detailed output on deployment failures.

## 2. Infrastructure Management Tools

### 2.1. `manage_infrastructure`

**Description:** Provisions, updates, or tears down infrastructure resources using Infrastructure as Code (IaC) principles. This tool provides an interface to interact with popular IaC frameworks, enabling declarative management of cloud and on-premise resources.

**Parameters:**

*   **`action`** (string, **required**): The IaC operation to perform.
    *   **Enum:** `apply` (create/update resources), `plan` (show proposed changes), `destroy` (remove resources), `validate` (check configuration syntax).
*   **`iac_path`** (string, **required**): The absolute path to the directory containing the IaC configuration files (e.g., Terraform `.tf` files, CloudFormation YAML/JSON templates, Pulumi program files).
*   **`iac_tool`** (string, **required**): The Infrastructure as Code tool to use.
    *   **Enum:** `terraform`, `cloudformation`, `pulumi`, `ansible`.
*   **`variables`** (object, *optional*): A dictionary of key-value pairs to pass as input variables to the IaC tool (e.g., Terraform `vars`, CloudFormation `parameters`).
*   **`environment`** (string, *optional*): A logical environment name (e.g., 'dev', 'staging', 'prod') which might map to specific IaC workspaces or configurations.
*   **`cloud_provider`** (string, *optional*): The target cloud provider. Useful for context or for tools that support multiple providers.
    *   **Enum:** `aws`, `azure`, `gcp`, `digitalocean`, `vultr`, `linode`.
*   **`dry_run`** (boolean, *optional*, default: `false`): If `true`, simulates the `apply` or `destroy` action without making actual changes. This is equivalent to `terraform plan` or `pulumi preview`.

**Example Usage:**

```
manage_infrastructure(
    action="apply",
    iac_path="./terraform/aws-vpc",
    iac_tool="terraform",
    variables={
        "region": "us-west-2",
        "vpc_cidr": "10.0.0.0/16"
    },
    environment="dev"
)

manage_infrastructure(
    action="plan",
    iac_path="./cloudformation/s3-bucket",
    iac_tool="cloudformation",
    variables={
        "BucketName": "my-unique-app-bucket"
    },
    cloud_provider="aws"
)

manage_infrastructure(
    action="destroy",
    iac_path="./pulumi/my-app",
    iac_tool="pulumi",
    environment="staging",
    dry_run=True
)
```

**Integration Notes:**
*   Primarily uses `bash` or `shell_command` to execute IaC CLI commands (e.g., `terraform`, `aws cloudformation`, `pulumi`, `ansible-playbook`).
*   `file_read` and `file_write` for managing IaC configuration files.
*   `json_yaml` for parsing/generating IaC templates (e.g., CloudFormation JSON/YAML).
*   Could integrate with `git_tools` for versioning IaC configurations.
*   Requires careful handling of sensitive information (e.g., API keys, secrets) which should be managed securely outside the tool's direct parameters.

## 3. CI/CD Configuration Tools

### 3.1. `configure_ci_cd`

**Description:** Configures or modifies Continuous Integration/Continuous Deployment pipelines. This tool provides a high-level interface to automate common CI/CD tasks, such as setting up build jobs, deployment stages, or integrating with testing and linting processes.

**Parameters:**

*   **`action`** (string, **required**): The CI/CD configuration action to perform.
    *   **Enum:** `create` (create a new pipeline/job), `update` (modify an existing pipeline/job), `delete` (remove a pipeline/job), `status` (get status of pipelines/jobs).
*   **`platform`** (string, **required**): The CI/CD platform or system.
    *   **Enum:** `github_actions`, `gitlab_ci`, `jenkins`, `azure_devops`, `travis_ci`, `circle_ci`.
*   **`config_path`** (string, *optional*): The absolute path to the CI/CD configuration file within the repository (e.g., `.github/workflows/main.yml`, `.gitlab-ci.yml`). Required for `create` and `update` actions that modify local files.
*   **`pipeline_name`** (string, *optional*): The name of the pipeline or job to configure. Required for actions targeting specific pipelines.
*   **`definition`** (string, *optional*): The content of the pipeline definition (e.g., YAML string for GitHub Actions, Groovy script for Jenkinsfile). Required for `create` and `update` actions.
*   **`repository_url`** (string, *optional*): The URL of the Git repository associated with the CI/CD pipeline. Required for platforms that manage pipelines externally (e.g., Jenkins, Azure DevOps).
*   **`branch`** (string, *optional*): The specific branch to configure CI/CD for. Defaults to the default branch if not specified.
*   **`options`** (object, *optional*): A dictionary of additional, platform-specific options (e.g., `{'trigger_on_push': true, 'cron_schedule': '0 0 * * *'}`).

**Example Usage:**

```
configure_ci_cd(
    action="create",
    platform="github_actions",
    config_path=".github/workflows/deploy.yml",
    pipeline_name="Deploy to Production",
    definition="""
name: Deploy to Production
on:
  push:
    branches:
      - main
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "Deploying..."
"""
)

configure_ci_cd(
    action="update",
    platform="gitlab_ci",
    config_path=".gitlab-ci.yml",
    pipeline_name="build_and_test",
    definition="""
stages:
  - build
  - test

build_job:
  stage: build
  script:
    - echo "Building..."

test_job:
  stage: test
  script:
    - echo "Testing..."
"""
)

configure_ci_cd(
    action="status",
    platform="jenkins",
    repository_url="https://github.com/my-org/my-repo"
)
```

**Integration Notes:**
*   Will use `file_read` and `file_write` to modify CI/CD configuration files directly within the repository.
*   `git_tools` will be essential for committing and pushing changes to the repository.
*   `bash` or `shell_command` will be used for interacting with platform-specific CLIs (e.g., Jenkins CLI, Azure DevOps CLI).
*   `json_yaml` will be useful for parsing and generating YAML/JSON-based pipeline definitions.
*   Could integrate with `test_runner` and `lint` to ensure that CI/CD configurations include appropriate quality checks.
