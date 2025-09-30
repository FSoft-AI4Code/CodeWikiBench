8.2-CI/CD & Deployment

# Page: CI/CD & Deployment

# CI/CD & Deployment

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



This document covers OpenHands' continuous integration, continuous deployment (CI/CD) pipelines, and deployment processes. It explains how code changes flow from development through testing to production-ready container images, and how these images are deployed across different environments.

For information about local development build processes and dependency management, see [Build System & Dependencies](#8.1).

## CI/CD Pipeline Architecture

OpenHands uses GitHub Actions as its primary CI/CD platform, orchestrating builds, tests, and deployments through several specialized workflows. The main pipeline is triggered on pushes to `main`, tags, pull requests, and manual dispatches.

```mermaid
graph TB
    subgraph "Trigger Events"
        PUSH["Push to main"]
        TAG["Tag creation"]
        PR["Pull Request"]
        MANUAL["Manual dispatch"]
    end
    
    subgraph "GitHub Actions Workflows"
        GHCR["ghcr-build.yml<br/>Main Build Pipeline"]
        LINT["lint.yml<br/>Code Quality"]
        TESTS["fe-unit-tests.yml<br/>Frontend Tests"]
        ENTERPRISE["enterprise-preview.yml<br/>Preview Deployment"]
    end
    
    subgraph "Build Matrix"
        MATRIX["define-matrix<br/>Base Image Selection"]
        APP_BUILD["ghcr_build_app<br/>Application Image"]
        RUNTIME_BUILD["ghcr_build_runtime<br/>Runtime Images"]
        ENT_BUILD["ghcr_build_enterprise<br/>Enterprise Server"]
    end
    
    subgraph "Testing Jobs"
        RT_ROOT["test_runtime_root<br/>Runtime Tests as Root"]
        RT_OH["test_runtime_oh<br/>Runtime Tests as openhands"]
        RT_CHECK["runtime_tests_check<br/>Gate for Merge"]
    end
    
    subgraph "Container Registry"
        GHCR_REPO["ghcr.io/all-hands-ai/<br/>openhands, runtime, enterprise"]
    end
    
    PUSH --> GHCR
    TAG --> GHCR  
    PR --> GHCR
    MANUAL --> GHCR
    
    PR --> LINT
    PR --> TESTS
    PR --> ENTERPRISE
    
    GHCR --> MATRIX
    MATRIX --> APP_BUILD
    MATRIX --> RUNTIME_BUILD
    GHCR --> ENT_BUILD
    
    RUNTIME_BUILD --> RT_ROOT
    RUNTIME_BUILD --> RT_OH
    RT_ROOT --> RT_CHECK
    RT_OH --> RT_CHECK
    
    APP_BUILD --> GHCR_REPO
    RUNTIME_BUILD --> GHCR_REPO
    ENT_BUILD --> GHCR_REPO
```

The pipeline supports concurrent execution with intelligent cancellation - PR-based builds share the same concurrency group but each commit to `main` gets its own group to prevent interference.

**Sources:** [.github/workflows/ghcr-build.yml:1-421](), [.github/workflows/lint.yml:1-88](), [.github/workflows/fe-unit-tests.yml:1-45]()

## Docker Build System

OpenHands builds three primary Docker images through a sophisticated multi-stage build process. The build system uses `containers/build.sh` as the orchestration script, with specialized configuration for each image type.

```mermaid
graph LR
    subgraph "Build Script Entry Points"
        BUILD_SH["containers/build.sh<br/>Main Build Orchestrator"]
        MAKE_BUILD["Makefile<br/>make build target"]
    end
    
    subgraph "Image Configurations"
        APP_DIR["containers/app/<br/>openhands application"]
        RUNTIME_DIR["containers/runtime/<br/>execution environment"] 
        ENTERPRISE_DIR["enterprise/<br/>enterprise server"]
    end
    
    subgraph "Build Parameters"
        CONFIG_SH["config.sh<br/>Build Configuration"]
        DOCKERFILE["Dockerfile<br/>Build Instructions"]
        ARGS["Build Arguments<br/>--push, --load, -t tag"]
    end
    
    subgraph "Docker Registry"
        GHCR_TAGS["ghcr.io tags:<br/>latest, SHA, branch"]
        BUILDX["docker buildx<br/>Multi-platform builds"]
    end
    
    BUILD_SH --> APP_DIR
    BUILD_SH --> RUNTIME_DIR
    BUILD_SH --> ENTERPRISE_DIR
    
    APP_DIR --> CONFIG_SH
    RUNTIME_DIR --> CONFIG_SH
    ENTERPRISE_DIR --> CONFIG_SH
    
    CONFIG_SH --> DOCKERFILE
    DOCKERFILE --> BUILDX
    BUILDX --> GHCR_TAGS
    
    MAKE_BUILD --> BUILD_SH
```

The build system implements intelligent tagging based on Git context. For version tags (e.g., `1.2.3`), it creates multiple tags including major version (`1`), minor version (`1.2`), and `latest`. Branch builds use sanitized branch names, while commit builds use both short and full SHA hashes.

**Sources:** [containers/build.sh:1-183](), [Makefile:24-32](), [.github/workflows/ghcr-build.yml:83-86]()

## Runtime Image Building System

Runtime images are built dynamically using a sophisticated templating and caching system implemented in the `openhands/runtime/utils/runtime_build.py` module. This system supports building from different base images while maximizing build cache reuse.

```mermaid
graph TD
    subgraph "Runtime Build Process"
        RUNTIME_BUILD["runtime_build.py<br/>build_runtime_image()"]
        BASE_IMAGE["Base Image<br/>(nikolaik, ubuntu, etc)"]
        BUILD_TYPE["BuildFromImageType<br/>SCRATCH, VERSIONED, LOCK"]
    end
    
    subgraph "Template System"
        JINJA_TEMPLATE["Dockerfile.j2<br/>Dynamic Dockerfile"]
        DOCKERFILE_GEN["_generate_dockerfile()<br/>Template Renderer"]
        BUILD_FOLDER["Build Context<br/>Source + Dependencies"]
    end
    
    subgraph "Caching Strategy" 
        LOCK_TAG["Lock Tag<br/>oh_v{version}_{lock_hash}"]
        VERSIONED_TAG["Versioned Tag<br/>oh_v{version}_{base_image}"]
        SOURCE_TAG["Source Tag<br/>{lock_tag}_{source_hash}"]
    end
    
    subgraph "Docker Builder"
        DOCKER_BUILDER["DockerRuntimeBuilder<br/>Docker BuildKit Integration"]
        REMOTE_BUILDER["RemoteRuntimeBuilder<br/>Remote API Integration"]
        BUILD_EXEC["docker buildx build<br/>Multi-platform Support"]
    end
    
    RUNTIME_BUILD --> BASE_IMAGE
    RUNTIME_BUILD --> BUILD_TYPE
    BASE_IMAGE --> DOCKERFILE_GEN
    BUILD_TYPE --> DOCKERFILE_GEN
    DOCKERFILE_GEN --> JINJA_TEMPLATE
    JINJA_TEMPLATE --> BUILD_FOLDER
    
    RUNTIME_BUILD --> LOCK_TAG
    RUNTIME_BUILD --> VERSIONED_TAG  
    RUNTIME_BUILD --> SOURCE_TAG
    
    BUILD_FOLDER --> DOCKER_BUILDER
    BUILD_FOLDER --> REMOTE_BUILDER
    DOCKER_BUILDER --> BUILD_EXEC
    REMOTE_BUILDER --> BUILD_EXEC
```

The build system uses three levels of caching to optimize build times:
1. **Lock-based caching**: Reuses images with identical `pyproject.toml` and `poetry.lock` files
2. **Version-based caching**: Reuses images with the same OpenHands version and base image
3. **Source-based caching**: The final image incorporating all source code changes

**Sources:** [openhands/runtime/utils/runtime_build.py:108-255](), [openhands/runtime/utils/runtime_templates/Dockerfile.j2:1-373](), [openhands/runtime/builder/docker.py:51-249]()

## Application Container Architecture

The OpenHands application image uses a multi-stage build process optimized for both frontend and backend components, with careful user management and security considerations.

```mermaid
graph TB
    subgraph "Multi-stage Build"
        FRONTEND_BUILD["frontend-builder<br/>node:24.3.0-bookworm-slim"]
        BACKEND_BUILD["backend-builder<br/>python:3.12.10-slim"]
        FINAL_APP["openhands-app<br/>Final Application Image"]
    end
    
    subgraph "Frontend Stage"
        NPM_CI["npm ci<br/>Install Dependencies"]
        NPM_BUILD["npm run build<br/>Production Build"]
        DIST_ASSETS["frontend/build<br/>Static Assets"]
    end
    
    subgraph "Backend Stage" 
        POETRY_INSTALL["poetry install<br/>Python Dependencies"]
        VENV_CREATION[".venv<br/>Virtual Environment"]
    end
    
    subgraph "Final Assembly"
        USER_SETUP["openhands user<br/>UID: 42420"]
        WORKSPACE_MOUNT["/opt/workspace_base<br/>Workspace Volume"]
        ENTRYPOINT_SH["entrypoint.sh<br/>Runtime Setup"]
        UVICORN_CMD["uvicorn server<br/>FastAPI Application"]
    end
    
    FRONTEND_BUILD --> NPM_CI
    NPM_CI --> NPM_BUILD
    NPM_BUILD --> DIST_ASSETS
    
    BACKEND_BUILD --> POETRY_INSTALL
    POETRY_INSTALL --> VENV_CREATION
    
    DIST_ASSETS --> FINAL_APP
    VENV_CREATION --> FINAL_APP
    
    FINAL_APP --> USER_SETUP
    FINAL_APP --> WORKSPACE_MOUNT
    FINAL_APP --> ENTRYPOINT_SH
    ENTRYPOINT_SH --> UVICORN_CMD
```

The application container implements flexible user management through `entrypoint.sh`, supporting both root execution (`SANDBOX_USER_ID=0`) and dynamic user creation based on the host user ID. This ensures proper file permissions when mounting host directories.

**Sources:** [containers/app/Dockerfile:1-96](), [containers/app/entrypoint.sh:1-74]()

## Deployment and Registry Management

OpenHands uses GitHub Container Registry (GHCR) as its primary container registry, with sophisticated tagging and caching strategies. The deployment process varies based on the target environment.

```mermaid
graph LR
    subgraph "Container Images"
        APP_IMG["ghcr.io/all-hands-ai/openhands<br/>Main Application"]
        RUNTIME_IMG["ghcr.io/all-hands-ai/runtime<br/>Execution Environment"]
        ENT_IMG["ghcr.io/all-hands-ai/enterprise-server<br/>Enterprise Features"]
    end
    
    subgraph "Image Tags"
        LATEST_TAG["latest<br/>Stable Release"]
        VERSION_TAG["v1.0.0<br/>Semantic Versions"]
        BRANCH_TAG["main, feature-x<br/>Branch Builds"]
        SHA_TAG["abc123<br/>Commit Hashes"]
        PR_TAG["pr-123<br/>Pull Request Builds"]
    end
    
    subgraph "Deployment Targets"
        CLOUD_DEPLOY["OpenHands Cloud<br/>Production SaaS"]
        LOCAL_DEPLOY["Local Development<br/>docker run / docker-compose"]
        ENT_PREVIEW["Enterprise Preview<br/>Feature Branch Testing"]
    end
    
    subgraph "Registry Operations"
        PUSH_OP["docker push<br/>Image Publishing"]
        PULL_OP["docker pull<br/>Image Retrieval"]
        CACHE_OP["BuildKit Cache<br/>Layer Optimization"]
    end
    
    APP_IMG --> LATEST_TAG
    APP_IMG --> VERSION_TAG
    APP_IMG --> BRANCH_TAG
    RUNTIME_IMG --> SHA_TAG
    ENT_IMG --> PR_TAG
    
    LATEST_TAG --> CLOUD_DEPLOY
    VERSION_TAG --> CLOUD_DEPLOY
    BRANCH_TAG --> LOCAL_DEPLOY
    PR_TAG --> ENT_PREVIEW
    
    PUSH_OP --> APP_IMG
    PULL_OP --> LOCAL_DEPLOY
    CACHE_OP --> PUSH_OP
```

The registry implements layer caching through BuildKit, with cache references stored as registry cache manifests. This significantly reduces build times for subsequent builds with similar dependencies.

For enterprise previews, the system automatically triggers deployments when PRs are labeled with `deploy`, creating temporary preview environments using the PR-specific image tags.

**Sources:** [.github/workflows/ghcr-build.yml:126-143](), [.github/workflows/enterprise-preview.yml:1-30](), [containers/build.sh:126-143]()

## Testing Integration in CI/CD

The CI/CD pipeline includes comprehensive testing that validates both the built images and the deployment process. Runtime tests are particularly critical as they verify the execution environment works correctly across different configurations.

| Test Category | Job Name | Purpose | Base Images |
|---------------|----------|---------|-------------|
| Runtime Tests (Root) | `test_runtime_root` | Validate runtime as root user | nikolaik, ubuntu |
| Runtime Tests (User) | `test_runtime_oh` | Validate runtime as openhands user | nikolaik, ubuntu |
| Frontend Tests | `fe-unit-tests` | UI component and logic validation | Node.js 22 |
| Lint Checks | `lint-python`, `lint-frontend` | Code quality enforcement | Python 3.12, Node.js 22 |

The testing process includes automatic retry logic for flaky tests (`--reruns 2 --reruns-delay 5`) and runs tests in parallel using `pytest-xdist`. All runtime tests must pass before PR merge is allowed, enforced by the `runtime_tests_check` gate job.

**Sources:** [.github/workflows/ghcr-build.yml:254-397](), [tests/runtime/test_mcp_action.py:1-369](), [.github/workflows/lint.yml:40-75]()