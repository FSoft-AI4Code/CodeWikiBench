8-Development & Contributing

# Page: Development & Contributing

# Development & Contributing

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [.github/workflows/clean-up.yml](.github/workflows/clean-up.yml)
- [.github/workflows/enterprise-preview.yml](.github/workflows/enterprise-preview.yml)
- [.github/workflows/fe-unit-tests.yml](.github/workflows/fe-unit-tests.yml)
- [.github/workflows/ghcr-build.yml](.github/workflows/ghcr-build.yml)
- [.github/workflows/lint-fix.yml](.github/workflows/lint-fix.yml)
- [.github/workflows/lint.yml](.github/workflows/lint.yml)
- [.github/workflows/stale.yml](.github/workflows/stale.yml)
- [Makefile](Makefile)
- [containers/app/Dockerfile](containers/app/Dockerfile)
- [containers/app/entrypoint.sh](containers/app/entrypoint.sh)
- [containers/build.sh](containers/build.sh)
- [frontend/.eslintrc](frontend/.eslintrc)
- [frontend/.husky/pre-commit](frontend/.husky/pre-commit)
- [frontend/scripts/check-translation-completeness.cjs](frontend/scripts/check-translation-completeness.cjs)
- [openhands/runtime/builder/base.py](openhands/runtime/builder/base.py)
- [openhands/runtime/builder/docker.py](openhands/runtime/builder/docker.py)
- [openhands/runtime/builder/remote.py](openhands/runtime/builder/remote.py)
- [openhands/runtime/utils/request.py](openhands/runtime/utils/request.py)
- [openhands/runtime/utils/runtime_build.py](openhands/runtime/utils/runtime_build.py)
- [openhands/runtime/utils/runtime_templates/Dockerfile.j2](openhands/runtime/utils/runtime_templates/Dockerfile.j2)
- [openhands/utils/term_color.py](openhands/utils/term_color.py)
- [tests/runtime/test_aci_edit.py](tests/runtime/test_aci_edit.py)
- [tests/runtime/test_mcp_action.py](tests/runtime/test_mcp_action.py)

</details>



This document covers the development setup, build system, code quality processes, and contribution workflows for OpenHands. It provides technical details for developers who want to contribute to the project or understand how the build and deployment infrastructure works.

For information about the runtime system architecture, see [Runtime & Execution Environment](#5). For details about the agent system implementation, see [Agent System](#3).

## Development Setup

OpenHands uses a multi-language development environment with Python backend components and a Node.js frontend. The primary entry point for all development tasks is the `Makefile`, which orchestrates dependency management, building, and testing across both ecosystems.

### Build System Architecture

```mermaid
graph TD
    DEV["Developer"]
    MAKE["Makefile"]
    
    subgraph "Dependency Management"
        CHECK["check-dependencies"]
        POETRY["install-python-dependencies"]
        NPM["install-frontend-dependencies"]
        PRECOMMIT["install-pre-commit-hooks"]
    end
    
    subgraph "Build Process"
        FRONTEND["build-frontend"]
        BACKEND["Backend (Poetry)"]
        ASSETS["Static Assets"]
    end
    
    subgraph "Quality Control"
        LINT_PY["lint-backend"]
        LINT_FE["lint-frontend"]
        TEST["test-frontend"]
        HOOKS["pre-commit hooks"]
    end
    
    DEV --> MAKE
    MAKE --> CHECK
    CHECK --> POETRY
    CHECK --> NPM
    CHECK --> PRECOMMIT
    
    POETRY --> BACKEND
    NPM --> FRONTEND
    FRONTEND --> ASSETS
    
    MAKE --> LINT_PY
    MAKE --> LINT_FE
    MAKE --> TEST
    PRECOMMIT --> HOOKS

    POETRY --> HOOKS
    NPM --> HOOKS
```

The build system coordinates several key components:

- **`make build`** - Main build target that orchestrates all setup steps
- **`check-dependencies`** - Validates system requirements (Python 3.12, Node.js 22, Docker, Poetry, tmux)
- **`install-python-dependencies`** - Uses Poetry to install Python packages with optional Playwright support
- **`install-frontend-dependencies`** - Uses npm to install Node.js dependencies
- **`build-frontend`** - Compiles React application with Vite

Sources: [Makefile:25-32](), [Makefile:34-45](), [Makefile:139-175](), [Makefile:177-183](), [Makefile:244-246]()

### Development Dependencies

The project requires specific versions of core tools:

| Tool | Required Version | Purpose |
|------|-----------------|---------|
| Python | 3.12 | Backend runtime and package management |
| Node.js | 22.x+ | Frontend build and runtime |
| Poetry | 1.8+ | Python dependency management |
| Docker | Latest | Container runtime for sandboxed execution |
| tmux | Optional | Advanced terminal features |

The dependency checking system validates these requirements and provides installation guidance when tools are missing.

Sources: [Makefile:14](), [Makefile:64-96](), [Makefile:119-137]()

## Code Quality & Linting

### Linting Architecture

```mermaid
graph TD
    subgraph "Frontend Linting"
        ESLINT["ESLint Config"]
        TS["TypeScript"]
        PRETTIER["Prettier"]
        I18N["i18next checks"]
    end
    
    subgraph "Backend Linting"
        PRECOMMIT["pre-commit-config.yaml"]
        BLACK["Black formatter"]
        ISORT["isort import sorting"]
        FLAKE8["Flake8 linting"]
        MYPY["MyPy type checking"]
    end
    
    subgraph "Git Integration"
        HUSKY["Husky pre-commit"]
        STAGED["lint-staged"]
        HOOKS["Git hooks"]
    end
    
    MAKE_LINT["make lint"] --> ESLINT
    MAKE_LINT --> PRECOMMIT
    
    ESLINT --> TS
    ESLINT --> PRETTIER
    ESLINT --> I18N
    
    PRECOMMIT --> BLACK
    PRECOMMIT --> ISORT
    PRECOMMIT --> FLAKE8
    PRECOMMIT --> MYPY
    
    HUSKY --> STAGED
    STAGED --> ESLINT
    HUSKY --> PRECOMMIT
    HOOKS --> HUSKY
```

The linting system uses different tools for frontend and backend code:

**Frontend linting** (`npm run lint`):
- ESLint with Airbnb config and TypeScript support
- Prettier for code formatting
- i18next plugin for internationalization string checking
- TypeScript compilation verification

**Backend linting** (`pre-commit`):
- Black for Python code formatting
- isort for import statement organization
- Flake8 for style guide enforcement
- MyPy for static type checking

Sources: [frontend/.eslintrc:1-76](), [frontend/.husky/pre-commit:1-10](), [Makefile:191-201]()

### Pre-commit Hook Integration

The project uses Husky and lint-staged for Git integration:

1. **Husky** manages Git hooks and triggers checks on commit
2. **lint-staged** runs linters only on staged files
3. **Pre-commit framework** handles Python-side linting with configuration in `dev_config/python/.pre-commit-config.yaml`

This ensures code quality standards are enforced before commits reach the repository.

Sources: [frontend/.husky/pre-commit:1-10](), [Makefile:185-189]()

## CI/CD Pipeline

### GitHub Actions Workflow Architecture

```mermaid
graph TD
    subgraph "Trigger Events"
        PR["Pull Request"]
        PUSH_MAIN["Push to main"]
        TAG["Tag creation"]
        MANUAL["Manual dispatch"]
    end
    
    subgraph "Core Workflows"
        LINT_WF["lint.yml"]
        BUILD_WF["ghcr-build.yml"]
        FE_TEST["fe-unit-tests.yml"]
    end
    
    subgraph "Build Jobs"
        DEFINE["define-matrix"]
        BUILD_APP["ghcr_build_app"]
        BUILD_RT["ghcr_build_runtime"]
        BUILD_ENT["ghcr_build_enterprise"]
    end
    
    subgraph "Test Jobs"
        TEST_RT_ROOT["test_runtime_root"]
        TEST_RT_OH["test_runtime_oh"]
        FE_TESTS["Frontend tests"]
    end
    
    subgraph "Registry"
        GHCR["GitHub Container Registry"]
        IMAGES["Docker images"]
    end
    
    PR --> LINT_WF
    PR --> BUILD_WF
    PR --> FE_TEST
    PUSH_MAIN --> BUILD_WF
    TAG --> BUILD_WF
    MANUAL --> BUILD_WF
    
    BUILD_WF --> DEFINE
    DEFINE --> BUILD_APP
    DEFINE --> BUILD_RT
    BUILD_RT --> BUILD_ENT
    
    BUILD_RT --> TEST_RT_ROOT
    BUILD_RT --> TEST_RT_OH
    
    BUILD_APP --> GHCR
    BUILD_RT --> GHCR
    BUILD_ENT --> GHCR
    GHCR --> IMAGES
    
    FE_TEST --> FE_TESTS
    LINT_WF --> FE_TESTS
```

The CI/CD system is built around GitHub Actions with several key workflows:

**Primary Build Workflow** (`ghcr-build.yml`):
- Builds application, runtime, and enterprise Docker images
- Supports multi-platform builds (linux/amd64, linux/arm64)
- Pushes to GitHub Container Registry (GHCR)
- Runs comprehensive runtime testing

**Quality Assurance** (`lint.yml`):
- Frontend linting with ESLint and TypeScript compilation
- Backend linting with pre-commit hooks
- Translation completeness checking
- Version consistency validation

**Testing** (`fe-unit-tests.yml`):
- Frontend unit tests with coverage reporting
- TypeScript compilation verification

Sources: [.github/workflows/ghcr-build.yml:1-421](), [.github/workflows/lint.yml:1-88](), [.github/workflows/fe-unit-tests.yml:1-45]()

### Build Matrix Strategy

The CI system uses a dynamic build matrix to optimize build times:

```mermaid
graph LR
    subgraph "Base Images"
        NIKOLAIK["nikolaik/python-nodejs:python3.12-nodejs22"]
        UBUNTU["ubuntu:24.04"]
    end
    
    subgraph "Build Variants"
        PR_BUILD["PR builds (nikolaik only)"]
        FULL_BUILD["Full builds (both images)"]
    end
    
    subgraph "Outputs"
        RUNTIME_NIKOLAIK["runtime:*-nikolaik"]
        RUNTIME_UBUNTU["runtime:*-ubuntu"]
        APP["openhands:*"]
        ENTERPRISE["enterprise-server:*"]
    end
    
    NIKOLAIK --> PR_BUILD
    NIKOLAIK --> FULL_BUILD
    UBUNTU --> FULL_BUILD
    
    PR_BUILD --> RUNTIME_NIKOLAIK
    FULL_BUILD --> RUNTIME_NIKOLAIK
    FULL_BUILD --> RUNTIME_UBUNTU
    
    RUNTIME_NIKOLAIK --> APP
    RUNTIME_UBUNTU --> ENTERPRISE
```

- **Pull Requests**: Build only nikolaik variant to save CI resources
- **Main/Tag builds**: Build both nikolaik and ubuntu variants for full platform support
- **Conditional execution**: Fork repositories cannot push to GHCR but still build for validation

Sources: [.github/workflows/ghcr-build.yml:31-52](), [.github/workflows/ghcr-build.yml:96-99]()

## Docker Build System

### Runtime Image Build Process

```mermaid
graph TD
    subgraph "Build Orchestration"
        RUNTIME_BUILD["runtime_build.py"]
        BUILDER_FACTORY["RuntimeBuilder Factory"]
        BUILD_FOLDER["Build Context Preparation"]
    end
    
    subgraph "Docker Builders"
        DOCKER_BUILDER["DockerRuntimeBuilder"]
        REMOTE_BUILDER["RemoteRuntimeBuilder"]
        BUILDX["Docker Buildx"]
    end
    
    subgraph "Image Optimization"
        HASH_CALC["Hash Calculation"]
        CACHE_LOOKUP["Cache Layer Lookup"]
        TAG_STRATEGY["Multi-tier Tagging"]
    end
    
    subgraph "Build Artifacts"
        SOURCE_FILES["Source Code"]
        DOCKERFILE["Generated Dockerfile.j2"]
        POETRY_LOCK["poetry.lock"]
        PYPROJECT["pyproject.toml"]
    end
    
    RUNTIME_BUILD --> BUILDER_FACTORY
    BUILDER_FACTORY --> DOCKER_BUILDER
    BUILDER_FACTORY --> REMOTE_BUILDER
    
    RUNTIME_BUILD --> BUILD_FOLDER
    BUILD_FOLDER --> SOURCE_FILES
    BUILD_FOLDER --> DOCKERFILE
    BUILD_FOLDER --> POETRY_LOCK
    BUILD_FOLDER --> PYPROJECT
    
    RUNTIME_BUILD --> HASH_CALC
    HASH_CALC --> CACHE_LOOKUP
    CACHE_LOOKUP --> TAG_STRATEGY
    
    DOCKER_BUILDER --> BUILDX
    TAG_STRATEGY --> BUILDX
```

The Docker build system implements sophisticated caching and optimization:

**Build Strategy Hierarchy**:
1. **SCRATCH**: Build from base image with no reused layers
2. **VERSIONED**: Reuse image with same base + OpenHands version  
3. **LOCK**: Reuse image with identical dependency locks (fastest)

**Hash-based Tagging**:
- `get_hash_for_lock_files()`: Creates hash from `pyproject.toml` and `poetry.lock`
- `get_hash_for_source_files()`: Creates hash from source code changes
- `get_tag_for_versioned_image()`: Creates tag from base image identifier

**Multi-tier Image Tags**:
- Source tag: `oh_v{version}_{lock_hash}_{source_hash}`
- Lock tag: `oh_v{version}_{lock_hash}`
- Versioned tag: `oh_v{version}_{base_image_tag}`

Sources: [openhands/runtime/utils/runtime_build.py:108-255](), [openhands/runtime/utils/runtime_build.py:320-358](), [openhands/runtime/builder/docker.py:51-249]()

### Container Build Script Architecture

```mermaid
graph TD
    subgraph "Build Script (build.sh)"
        ARGS["Argument Parsing"]
        CONFIG["config.sh Loading"]
        TAG_GEN["Tag Generation"]
        BUILDX_CMD["Buildx Command Assembly"]
    end
    
    subgraph "Configuration Sources"
        ENV_VARS["Environment Variables"]
        GIT_INFO["Git Information"]
        VERSION_INFO["Version Information"]
    end
    
    subgraph "Build Targets"
        APP_BUILD["openhands app"]
        RUNTIME_BUILD["runtime images"]
        CUSTOM_BUILD["custom containers"]
    end
    
    subgraph "Registry Operations"
        CACHE_PULL["Cache Pull"]
        IMAGE_PUSH["Image Push"]
        TAG_APPLY["Tag Application"]
    end
    
    ARGS --> CONFIG
    CONFIG --> TAG_GEN
    
    ENV_VARS --> TAG_GEN
    GIT_INFO --> TAG_GEN
    VERSION_INFO --> TAG_GEN
    
    TAG_GEN --> BUILDX_CMD
    BUILDX_CMD --> APP_BUILD
    BUILDX_CMD --> RUNTIME_BUILD
    BUILDX_CMD --> CUSTOM_BUILD
    
    BUILDX_CMD --> CACHE_PULL
    BUILDX_CMD --> IMAGE_PUSH
    BUILDX_CMD --> TAG_APPLY
```

The `containers/build.sh` script serves as a universal Docker build orchestrator:

**Key Parameters**:
- `-i <image_name>`: Target image (openhands, runtime, etc.)
- `-o <org_name>`: Docker organization/registry prefix
- `--push`: Push to registry after build
- `--load`: Load image locally after build
- `-t <tag_suffix>`: Additional tag suffix
- `--dry`: Generate build configuration without building

**Tag Generation Logic**:
- Git commit SHA for tracking builds
- Branch/tag names for version identification
- Semantic version parsing for release builds
- Cache optimization tags for build acceleration

Sources: [containers/build.sh:1-183](), [containers/build.sh:45-78](), [containers/build.sh:118-176]()

## Development Workflows

### Local Development Setup

```mermaid
graph TD
    subgraph "Initial Setup"
        CLONE["git clone"]
        DEPS["make build"]
        CONFIG["make setup-config"]
    end
    
    subgraph "Development Mode"
        RUN["make run"]
        BACKEND["Backend (FastAPI)"]
        FRONTEND["Frontend (Vite)"]
        WORKSPACE["Workspace Mount"]
    end
    
    subgraph "Code Quality"
        LINT_LOCAL["make lint"]
        PRE_COMMIT["pre-commit hooks"]
        TESTS["make test"]
    end
    
    subgraph "Container Development"
        DOCKER_RUN["make docker-run"]
        DOCKER_DEV["make docker-dev"]
        CONTAINERS["Docker Compose"]
    end
    
    CLONE --> DEPS
    DEPS --> CONFIG
    CONFIG --> RUN
    
    RUN --> BACKEND
    RUN --> FRONTEND
    RUN --> WORKSPACE
    
    LINT_LOCAL --> PRE_COMMIT
    PRE_COMMIT --> TESTS
    
    DOCKER_RUN --> CONTAINERS
    DOCKER_DEV --> CONTAINERS
```

**Standard Development Flow**:

1. **Environment Setup**: `make build` handles all dependency installation and pre-commit hook setup
2. **Configuration**: `make setup-config` creates initial `config.toml` with LLM settings and workspace path
3. **Local Development**: `make run` starts both backend (port 3000) and frontend (port 3001) servers
4. **Docker Development**: `make docker-run` or `make docker-dev` for containerized development

**Development Server Architecture**:
- **Backend**: FastAPI server with hot reload via `uvicorn --reload`
- **Frontend**: Vite development server with HMR (Hot Module Replacement)
- **Workspace**: Configurable workspace directory for agent file operations

Sources: [Makefile:279-283](), [Makefile:249-263](), [Makefile:286-297](), [Makefile:301-333]()

### Contributing Process

The contribution workflow enforces code quality through automated checks:

**Pre-commit Validation**:
1. Frontend linting (ESLint, Prettier, TypeScript)
2. Backend linting (Black, isort, flake8, MyPy) 
3. Translation completeness verification
4. Import organization and unused import removal

**CI Pipeline Integration**:
1. All PRs trigger lint and build workflows
2. Runtime tests execute against built Docker images
3. Fork repositories build locally but cannot push to registry
4. Auto-fix workflows available via `lint-fix` label

**Quality Gates**:
- Pre-commit hooks prevent commits with linting issues
- CI workflows must pass before merge
- Docker builds verify runtime compatibility
- Translation coverage ensures internationalization completeness

Sources: [.github/workflows/lint-fix.yml:1-98](), [frontend/.husky/pre-commit:1-10](), [frontend/scripts/check-translation-completeness.cjs:1-89]()