8.1-Build System & Dependencies

# Page: Build System & Dependencies

# Build System & Dependencies

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [.github/workflows/clean-up.yml](.github/workflows/clean-up.yml)
- [.github/workflows/fe-unit-tests.yml](.github/workflows/fe-unit-tests.yml)
- [.github/workflows/lint-fix.yml](.github/workflows/lint-fix.yml)
- [.github/workflows/lint.yml](.github/workflows/lint.yml)
- [.github/workflows/stale.yml](.github/workflows/stale.yml)
- [Development.md](Development.md)
- [Makefile](Makefile)
- [README.md](README.md)
- [README_CN.md](README_CN.md)
- [README_JA.md](README_JA.md)
- [containers/build.sh](containers/build.sh)
- [containers/dev/compose.yml](containers/dev/compose.yml)
- [docker-compose.yml](docker-compose.yml)
- [frontend/package-lock.json](frontend/package-lock.json)
- [frontend/package.json](frontend/package.json)
- [poetry.lock](poetry.lock)
- [pyproject.toml](pyproject.toml)

</details>



This document covers the build system architecture, dependency management, and development workflow orchestration in OpenHands. It details the tools and processes used to manage Python backend dependencies, frontend JavaScript/TypeScript dependencies, Docker containerization, and CI/CD automation.

For information about deployment and production infrastructure, see [CI/CD & Deployment](#8.2). For details about the development environment setup and contribution workflow, see [Development & Contributing](#8).

## Overview

OpenHands uses a multi-language build system orchestrated primarily through a `Makefile` with Poetry managing Python dependencies and npm handling frontend dependencies. The system supports both local development and containerized deployment scenarios.

### Build System Architecture

```mermaid
graph TB
    subgraph "Build Orchestration"
        MAKE["Makefile<br/>Primary Build Interface"]
        SCRIPTS["Build Scripts<br/>containers/build.sh"]
    end
    
    subgraph "Python Backend"
        POETRY["Poetry<br/>pyproject.toml"]
        LOCK_PY["poetry.lock<br/>Dependency Lock"]
        GROUPS["Dependency Groups<br/>main, dev, test, runtime, evaluation"]
    end
    
    subgraph "Frontend"
        NPM["npm<br/>package.json"]
        LOCK_JS["package-lock.json<br/>Dependency Lock"]
        SCRIPTS_JS["Build Scripts<br/>dev, build, test"]
    end
    
    subgraph "Containerization"
        DOCKERFILE_APP["containers/app/Dockerfile<br/>Application Container"]
        DOCKERFILE_RUNTIME["containers/runtime/Dockerfile<br/>Runtime Container"]
        COMPOSE_DEV["containers/dev/compose.yml<br/>Development"]
        COMPOSE_PROD["docker-compose.yml<br/>Production"]
    end
    
    subgraph "CI/CD"
        GH_ACTIONS["GitHub Actions<br/>Automated Workflows"]
        LINT[".github/workflows/lint.yml"]
        BUILD_WORKFLOWS["Build & Test Workflows"]
    end
    
    MAKE --> POETRY
    MAKE --> NPM
    MAKE --> DOCKERFILE_APP
    MAKE --> DOCKERFILE_RUNTIME
    
    POETRY --> LOCK_PY
    NPM --> LOCK_JS
    
    SCRIPTS --> DOCKERFILE_APP
    SCRIPTS --> DOCKERFILE_RUNTIME
    
    GH_ACTIONS --> MAKE
    GH_ACTIONS --> POETRY
    GH_ACTIONS --> NPM
```

Sources: [Makefile:1-372](), [pyproject.toml:1-199](), [frontend/package.json:1-152](), [containers/build.sh:1-183]()

## Python Dependency Management

OpenHands uses Poetry as its primary Python dependency management tool, configured through `pyproject.toml` with dependencies locked in `poetry.lock`.

### Poetry Configuration Structure

```mermaid
graph TB
    subgraph "pyproject.toml Structure"
        BUILD_SYSTEM["build-system<br/>poetry-core.masonry.api"]
        TOOL_POETRY["tool.poetry<br/>Project Metadata"]
        DEPENDENCIES["tool.poetry.dependencies<br/>Runtime Dependencies"]
        GROUPS["tool.poetry.group.*<br/>Dependency Groups"]
        EXTRAS["tool.poetry.extras<br/>Optional Features"]
        SCRIPTS["tool.poetry.scripts<br/>CLI Entrypoints"]
    end
    
    subgraph "Dependency Groups"
        DEV["dev<br/>Development Tools"]
        TEST["test<br/>Testing Framework"]
        RUNTIME["runtime<br/>Jupyter/Notebook"]
        EVALUATION["evaluation<br/>Benchmarking"]
        TESTGENEVAL["testgeneval<br/>Test Generation"]
    end
    
    subgraph "Core Dependencies"
        LITELLM["litellm ^1.74.3<br/>LLM Integration"]
        FASTAPI["fastapi<br/>Web Framework"]
        DOCKER_PY["docker<br/>Container Interface"]
        AIOHTTP["aiohttp >=3.9.0<br/>HTTP Client"]
    end
    
    TOOL_POETRY --> DEPENDENCIES
    TOOL_POETRY --> GROUPS
    TOOL_POETRY --> EXTRAS
    DEPENDENCIES --> LITELLM
    DEPENDENCIES --> FASTAPI
    DEPENDENCIES --> DOCKER_PY
    DEPENDENCIES --> AIOHTTP
    
    GROUPS --> DEV
    GROUPS --> TEST
    GROUPS --> RUNTIME
    GROUPS --> EVALUATION
```

Sources: [pyproject.toml:1-199](), [poetry.lock:1-948]()

### Python Version and Core Requirements

The project requires Python `^3.12,<3.14` as specified in [pyproject.toml:28](). Key dependency categories include:

- **LLM Integration**: `litellm`, `openai`, `anthropic` with specific version constraints
- **Web Framework**: `fastapi`, `uvicorn`, `python-socketio` for the backend server
- **Container Interface**: `docker` for runtime management
- **Development Tools**: `ruff`, `mypy`, `pre-commit` in the dev group
- **Testing**: `pytest` with various plugins in the test group

### Dependency Group Usage

The `install-python-dependencies` target in the Makefile installs dependencies based on the `POETRY_GROUP` environment variable:

```bash
# Install specific group
poetry install --only ${POETRY_GROUP}

# Default: install main groups
poetry install --with dev,test,runtime
```

Sources: [Makefile:139-175](), [pyproject.toml:108-178]()

## Frontend Dependency Management

The frontend uses npm for dependency management with Node.js >= 22.0.0 requirement defined in [frontend/package.json:6-8]().

### Frontend Build System Structure

```mermaid
graph TB
    subgraph "package.json Configuration"
        DEPENDENCIES["dependencies<br/>Runtime Libraries"]
        DEV_DEPS["devDependencies<br/>Build Tools"]
        SCRIPTS["scripts<br/>Build Commands"]
        ENGINES["engines<br/>Node.js >= 22.0.0"]
    end
    
    subgraph "Core Frontend Dependencies"
        REACT["react ^19.1.1<br/>UI Framework"]
        REACT_ROUTER["@react-router/*<br/>Routing System"]
        REDUX["@reduxjs/toolkit<br/>State Management"]
        VITE["vite ^7.1.4<br/>Build Tool"]
        TAILWIND["tailwindcss<br/>CSS Framework"]
    end
    
    subgraph "Build Scripts"
        DEV_SCRIPT["dev<br/>Development Server"]
        BUILD_SCRIPT["build<br/>Production Build"]
        TEST_SCRIPT["test<br/>Unit Testing"]
        LINT_SCRIPT["lint<br/>Code Quality"]
        TYPECHECK["typecheck<br/>TypeScript Validation"]
    end
    
    subgraph "Development Tools"
        TYPESCRIPT["typescript ^5.9.2<br/>Type System"]
        ESLINT["eslint ^8.57.0<br/>Linting"]
        PRETTIER["prettier ^3.6.2<br/>Formatting"]
        PLAYWRIGHT["@playwright/test<br/>E2E Testing"]
        HUSKY["husky<br/>Git Hooks"]
    end
    
    DEPENDENCIES --> REACT
    DEPENDENCIES --> REACT_ROUTER
    DEPENDENCIES --> REDUX
    DEPENDENCIES --> VITE
    
    DEV_DEPS --> TYPESCRIPT
    DEV_DEPS --> ESLINT
    DEV_DEPS --> PRETTIER
    DEV_DEPS --> PLAYWRIGHT
    
    SCRIPTS --> DEV_SCRIPT
    SCRIPTS --> BUILD_SCRIPT
    SCRIPTS --> TEST_SCRIPT
    SCRIPTS --> LINT_SCRIPT
```

Sources: [frontend/package.json:1-152](), [frontend/package-lock.json:1-748]()

### Frontend Build Scripts

The frontend defines several npm scripts for different development phases:

| Script | Purpose | Command |
|--------|---------|---------|
| `dev` | Development server | `react-router dev` with i18n setup |
| `build` | Production build | `react-router build` with optimization |
| `test` | Unit testing | `vitest run` |
| `lint` | Code quality check | `eslint` + `prettier` + `tsc` |
| `typecheck` | TypeScript validation | `react-router typegen && tsc` |

Sources: [frontend/package.json:63-82]()

## Build Orchestration

The `Makefile` serves as the primary build orchestration tool, providing a unified interface for all build operations across the polyglot codebase.

### Makefile Target Dependencies

```mermaid
graph TD
    subgraph "Primary Targets"
        BUILD["build<br/>Complete Build Process"]
        RUN["run<br/>Start Application"]
        LINT["lint<br/>Code Quality Checks"]
        TEST["test<br/>Run Test Suites"]
    end
    
    subgraph "Dependency Checks"
        CHECK_DEPS["check-dependencies<br/>Verify System Requirements"]
        CHECK_PYTHON["check-python<br/>Python 3.12 Validation"]
        CHECK_NODEJS["check-nodejs<br/>Node.js >= 22 Validation"]
        CHECK_DOCKER["check-docker<br/>Docker Installation"]
        CHECK_POETRY["check-poetry<br/>Poetry >= 1.8 Validation"]
    end
    
    subgraph "Installation Targets"
        INSTALL_PYTHON["install-python-dependencies<br/>Poetry Install"]
        INSTALL_FRONTEND["install-frontend-dependencies<br/>npm install"]
        INSTALL_PRECOMMIT["install-pre-commit-hooks<br/>Code Quality Setup"]
    end
    
    subgraph "Build Targets"
        BUILD_FRONTEND["build-frontend<br/>Production Frontend"]
        START_BACKEND["start-backend<br/>uvicorn Server"]
        START_FRONTEND["start-frontend<br/>Development Server"]
    end
    
    BUILD --> CHECK_DEPS
    BUILD --> INSTALL_PYTHON
    BUILD --> INSTALL_FRONTEND
    BUILD --> INSTALL_PRECOMMIT
    BUILD --> BUILD_FRONTEND
    
    CHECK_DEPS --> CHECK_PYTHON
    CHECK_DEPS --> CHECK_NODEJS
    CHECK_DEPS --> CHECK_DOCKER
    CHECK_DEPS --> CHECK_POETRY
    
    RUN --> BUILD
    RUN --> START_BACKEND
    RUN --> START_FRONTEND
    
    LINT --> INSTALL_PRECOMMIT
```

Sources: [Makefile:24-370]()

### Key Makefile Variables

The Makefile defines several configurable variables for build customization:

| Variable | Default | Purpose |
|----------|---------|---------|
| `BACKEND_HOST` | "127.0.0.1" | Backend server bind address |
| `BACKEND_PORT` | 3000 | Backend server port |
| `FRONTEND_HOST` | "127.0.0.1" | Frontend server bind address |
| `FRONTEND_PORT` | 3001 | Frontend development server port |
| `PYTHON_VERSION` | 3.12 | Required Python version |
| `PRE_COMMIT_CONFIG_PATH` | "./dev_config/python/.pre-commit-config.yaml" | Pre-commit configuration |

Sources: [Makefile:4-16]()

## Container Build System

OpenHands uses Docker for both development and production environments, with specialized build scripts and configurations for different deployment scenarios.

### Container Build Architecture

```mermaid
graph TB
    subgraph "Build Script System"
        BUILD_SH["containers/build.sh<br/>Universal Build Script"]
        CONFIG_SH["containers/*/config.sh<br/>Image Configuration"]
    end
    
    subgraph "Container Types"
        APP_CONTAINER["openhands<br/>containers/app/Dockerfile"]
        RUNTIME_CONTAINER["runtime<br/>containers/runtime/Dockerfile"]
        DEV_CONTAINER["dev<br/>containers/dev/Dockerfile"]
    end
    
    subgraph "Docker Compose Configurations"
        DEV_COMPOSE["containers/dev/compose.yml<br/>Development Environment"]
        PROD_COMPOSE["docker-compose.yml<br/>Production Deployment"]
    end
    
    subgraph "Build Parameters"
        IMAGE_NAME["-i image_name<br/>Container Image Name"]
        ORG_NAME["-o org_name<br/>Registry Organization"]
        PUSH_FLAG["--push<br/>Registry Push"]
        LOAD_FLAG["--load<br/>Local Load"]
        TAG_SUFFIX["-t tag_suffix<br/>Version Suffix"]
    end
    
    BUILD_SH --> CONFIG_SH
    BUILD_SH --> APP_CONTAINER
    BUILD_SH --> RUNTIME_CONTAINER
    
    CONFIG_SH --> IMAGE_NAME
    CONFIG_SH --> ORG_NAME
    
    BUILD_SH --> PUSH_FLAG
    BUILD_SH --> LOAD_FLAG
    BUILD_SH --> TAG_SUFFIX
    
    DEV_COMPOSE --> DEV_CONTAINER
    PROD_COMPOSE --> APP_CONTAINER
```

Sources: [containers/build.sh:1-183](), [containers/dev/compose.yml:1-40](), [docker-compose.yml:1-24]()

### Container Build Script Usage

The `containers/build.sh` script provides a unified interface for building different container images:

```bash
# Build application container
./containers/build.sh -i openhands --load

# Build and push runtime container
./containers/build.sh -i runtime -o all-hands-ai --push

# Build with custom tag
./containers/build.sh -i openhands -t dev-$(git rev-parse --short HEAD)
```

The script automatically handles:
- Multi-platform builds (linux/amd64, linux/arm64)
- Registry caching for faster builds
- Git-based tagging from `GITHUB_REF_NAME` and `RELEVANT_SHA`
- Build argument injection (`OPENHANDS_BUILD_VERSION`)

Sources: [containers/build.sh:24-183]()

## CI/CD Integration

The build system integrates with GitHub Actions for automated testing, linting, and container builds.

### CI/CD Workflow Structure

```mermaid
graph TB
    subgraph "Lint Workflows"
        LINT_WORKFLOW[".github/workflows/lint.yml<br/>Code Quality Enforcement"]
        LINT_FIX[".github/workflows/lint-fix.yml<br/>Automated Fixes"]
        LINT_FRONTEND["lint-frontend<br/>npm run lint"]
        LINT_PYTHON["lint-python<br/>pre-commit hooks"]
        LINT_ENTERPRISE["lint-enterprise-python<br/>Enterprise Code"]
        VERSION_CHECK["check-version-consistency<br/>Version Validation"]
    end
    
    subgraph "Test Workflows"
        FE_TESTS[".github/workflows/fe-unit-tests.yml<br/>Frontend Testing"]
        FE_TEST_JOB["fe-test<br/>npm run test:coverage"]
    end
    
    subgraph "Maintenance Workflows"
        STALE[".github/workflows/stale.yml<br/>Issue Management"]
        CLEANUP[".github/workflows/clean-up.yml<br/>Workflow Cleanup"]
    end
    
    subgraph "Build Dependencies"
        NODE_SETUP["useblacksmith/setup-node@v5<br/>Node.js 22"]
        PYTHON_SETUP["useblacksmith/setup-python@v6<br/>Python 3.12"]
        PRECOMMIT_INSTALL["pre-commit==3.7.0<br/>Code Quality Tools"]
    end
    
    LINT_WORKFLOW --> LINT_FRONTEND
    LINT_WORKFLOW --> LINT_PYTHON
    LINT_WORKFLOW --> LINT_ENTERPRISE
    LINT_WORKFLOW --> VERSION_CHECK
    
    LINT_FRONTEND --> NODE_SETUP
    LINT_PYTHON --> PYTHON_SETUP
    LINT_PYTHON --> PRECOMMIT_INSTALL
    
    FE_TESTS --> FE_TEST_JOB
    FE_TEST_JOB --> NODE_SETUP
```

Sources: [.github/workflows/lint.yml:1-88](), [.github/workflows/fe-unit-tests.yml:1-45](), [.github/workflows/lint-fix.yml:1-98]()

### Automated Quality Enforcement

The CI system enforces code quality through several mechanisms:

1. **Pre-commit Hooks**: Defined in `./dev_config/python/.pre-commit-config.yaml` and run via `pre-commit run --all-files`
2. **Frontend Linting**: Uses ESLint, Prettier, and TypeScript compilation checks
3. **Version Consistency**: Validates version numbers across documentation and configuration files
4. **Automated Fixes**: The `lint-fix` label triggers automated code formatting and correction

The lint workflows run on:
- All pushes to `main` branch
- All pull requests
- Specific path changes for frontend tests (`frontend/**`)

Sources: [.github/workflows/lint.yml:7-17](), [.github/workflows/fe-unit-tests.yml:6-14]()

## Development Workflow

The build system supports multiple development workflows through the Makefile interface and containerized environments.

### Local Development Setup

```mermaid
graph TD
    subgraph "Development Commands"
        MAKE_BUILD["make build<br/>Complete Environment Setup"]
        MAKE_RUN["make run<br/>Start Full Application"]
        MAKE_START_BACKEND["make start-backend<br/>Backend Only"]
        MAKE_START_FRONTEND["make start-frontend<br/>Frontend Only"]
    end
    
    subgraph "Configuration Setup"
        SETUP_CONFIG["make setup-config<br/>Interactive Configuration"]
        SETUP_CONFIG_BASIC["make setup-config-basic<br/>Default Configuration"]
        CONFIG_TOML["config.toml<br/>Runtime Configuration"]
    end
    
    subgraph "Container Development"
        DOCKER_DEV["make docker-dev<br/>Development Container"]
        DOCKER_RUN["make docker-run<br/>Production Container"]
        DEV_SH["./containers/dev/dev.sh<br/>Direct Container Access"]
    end
    
    subgraph "Quality Assurance"
        MAKE_LINT["make lint<br/>Code Quality Checks"]
        MAKE_TEST["make test<br/>Run Test Suites"]
        MAKE_CLEAN["make clean<br/>Cache Cleanup"]
    end
    
    MAKE_BUILD --> MAKE_RUN
    MAKE_RUN --> MAKE_START_BACKEND
    MAKE_RUN --> MAKE_START_FRONTEND
    
    SETUP_CONFIG --> CONFIG_TOML
    SETUP_CONFIG_BASIC --> CONFIG_TOML
    
    DOCKER_DEV --> DEV_SH
    
    MAKE_LINT --> MAKE_BUILD
    MAKE_TEST --> MAKE_BUILD
```

Sources: [Makefile:279-370](), [Development.md:51-140]()

### Environment Variables and Configuration

The build system respects several environment variables for customization:

| Variable | Purpose | Default |
|----------|---------|---------|
| `POETRY_GROUP` | Poetry dependency group to install | "dev,test,runtime" |
| `INSTALL_PLAYWRIGHT` | Control Playwright installation | true |
| `INSTALL_DOCKER` | Skip Docker requirement check | unset |
| `SANDBOX_RUNTIME_CONTAINER_IMAGE` | Override runtime container | ghcr.io/all-hands-ai/runtime:0.56-nikolaik |
| `WORKSPACE_BASE` | Workspace directory | "./workspace" |

These variables can be set to customize the build process for different environments or development scenarios.

Sources: [Makefile:139-175](), [containers/dev/compose.yml:10-17](), [docker-compose.yml:9-12]()