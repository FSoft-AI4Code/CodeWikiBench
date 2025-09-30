1-Overview

# Page: Overview

# Overview

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [Development.md](Development.md)
- [README.md](README.md)
- [README_CN.md](README_CN.md)
- [README_JA.md](README_JA.md)
- [containers/dev/compose.yml](containers/dev/compose.yml)
- [docker-compose.yml](docker-compose.yml)
- [frontend/package-lock.json](frontend/package-lock.json)
- [frontend/package.json](frontend/package.json)
- [openhands/controller/agent_controller.py](openhands/controller/agent_controller.py)
- [openhands/core/main.py](openhands/core/main.py)
- [openhands/core/setup.py](openhands/core/setup.py)
- [openhands/memory/view.py](openhands/memory/view.py)
- [openhands/server/routes/manage_conversations.py](openhands/server/routes/manage_conversations.py)
- [openhands/server/session/agent_session.py](openhands/server/session/agent_session.py)
- [openhands/server/session/session.py](openhands/server/session/session.py)
- [openhands/utils/http_session.py](openhands/utils/http_session.py)
- [poetry.lock](poetry.lock)
- [pyproject.toml](pyproject.toml)

</details>



This document provides a technical overview of OpenHands, an AI-powered software development agent platform that enables autonomous code modification, command execution, web browsing, and API interaction. OpenHands orchestrates LLM-powered agents within sandboxed runtime environments to perform complex development tasks.

For information about getting started with OpenHands, see [Getting Started](#2). For details about the agent system architecture, see [Agent System](#3). For LLM configuration and integration, see [LLM Integration](#4).

## System Architecture

OpenHands follows a multi-layered architecture with distinct separation between user interfaces, core orchestration, execution environments, and external integrations.

### High-Level Component Architecture

```mermaid
graph TB
    subgraph "User Interfaces"
        WebUI["WebSession<br/>(session.py)"]
        CLI["CLI Interface<br/>(cli/entry.py)"]
        API["REST/WebSocket API<br/>(FastAPI)"]
    end
    
    subgraph "Core Orchestration"
        AgentController["AgentController<br/>(agent_controller.py)"]
        AgentSession["AgentSession<br/>(agent_session.py)"]
        EventStream["EventStream<br/>(events/stream.py)"]
        StateTracker["StateTracker<br/>(state/state_tracker.py)"]
    end
    
    subgraph "Agent System"
        Agent["Agent<br/>(controller/agent.py)"]
        Memory["Memory<br/>(memory/memory.py)"]
        LLMRegistry["LLMRegistry<br/>(llm/llm_registry.py)"]
    end
    
    subgraph "Execution Environment"
        Runtime["Runtime<br/>(runtime/base.py)"]
        DockerRuntime["DockerRuntime<br/>(runtime/impl/docker)"]
        Sandbox["ActionExecutionServer<br/>(runtime/server)"]
    end
    
    subgraph "Storage & Persistence"
        FileStore["FileStore<br/>(storage/files.py)"]
        ConversationStore["ConversationStore<br/>(storage/conversation)"]
        EventStore["EventStore<br/>(events/event_store.py)"]
    end
    
    WebUI --> AgentSession
    CLI --> AgentController
    API --> AgentSession
    
    AgentSession --> AgentController
    AgentController --> Agent
    AgentController --> EventStream
    AgentController --> StateTracker
    
    Agent --> Memory
    Agent --> LLMRegistry
    AgentController --> Runtime
    
    Runtime --> DockerRuntime
    Runtime --> Sandbox
    
    AgentSession --> FileStore
    EventStream --> EventStore
    StateTracker --> ConversationStore
```

Sources: [openhands/server/session/session.py:40-112](), [openhands/controller/agent_controller.py:100-203](), [openhands/server/session/agent_session.py:42-89](), [openhands/core/main.py:51-96]()

### Event-Driven Communication Flow

```mermaid
graph TD
    subgraph "Event Sources"
        User["USER<br/>(MessageAction)"]
        Agent["AGENT<br/>(Actions)"]
        Environment["ENVIRONMENT<br/>(Observations)"]
    end
    
    subgraph "Event Processing"
        EventStream["EventStream<br/>(sid, file_store, user_id)"]
        EventStreamSubscriber["EventStreamSubscriber<br/>(AGENT_CONTROLLER, SERVER)"]
    end
    
    subgraph "Event Handlers"
        AgentControllerHandler["AgentController.on_event<br/>(agent_controller.py:392)"]
        WebSessionHandler["WebSession._on_event<br/>(session.py:314)"]
    end
    
    subgraph "Event Storage"
        EventStore["EventStore<br/>(event_store.py)"]
        FileStore["FileStore<br/>(files.py)"]
    end
    
    User --> EventStream
    Agent --> EventStream
    Environment --> EventStream
    
    EventStream --> EventStreamSubscriber
    EventStreamSubscriber --> AgentControllerHandler
    EventStreamSubscriber --> WebSessionHandler
    
    EventStream --> EventStore
    EventStore --> FileStore
```

Sources: [openhands/events/stream.py](), [openhands/server/session/session.py:311-330](), [openhands/controller/agent_controller.py:392-408]()

## Core Components

### Agent Controller System

The `AgentController` class serves as the primary orchestration component, managing agent lifecycle, state transitions, and action execution.

| Component | File Path | Primary Responsibility |
|-----------|-----------|----------------------|
| `AgentController` | [openhands/controller/agent_controller.py:100-203]() | Agent orchestration and lifecycle management |
| `State` | [openhands/controller/state/state.py]() | Agent state persistence and tracking |
| `StateTracker` | [openhands/controller/state/state_tracker.py]() | State change monitoring and persistence |
| `StuckDetector` | [openhands/controller/stuck.py]() | Agent loop detection and prevention |

The controller handles security analysis, confirmation mode, and error recovery through dedicated subsystems:

```mermaid
graph LR
    subgraph "AgentController Core"
        Controller["AgentController"]
        SecurityAnalyzer["SecurityAnalyzer<br/>(security/analyzer.py)"]
        ConfirmationMode["confirmation_mode<br/>(boolean flag)"]
    end
    
    subgraph "State Management"
        State["State<br/>(agent_state, iterations, budget)"]
        StateTracker["StateTracker<br/>(sid, file_store, user_id)"]
        StuckDetector["StuckDetector<br/>(state)"]
    end
    
    Controller --> SecurityAnalyzer
    Controller --> ConfirmationMode
    Controller --> State
    Controller --> StateTracker
    Controller --> StuckDetector
```

Sources: [openhands/controller/agent_controller.py:100-203](), [openhands/controller/state/state_tracker.py]()

### Session Management Architecture

OpenHands uses a dual-session architecture separating web connectivity from agent execution:

```mermaid
graph TD
    subgraph "Session Layer"
        WebSession["WebSession<br/>(sid, sio, config, llm_registry)"]
        AgentSession["AgentSession<br/>(sid, file_store, llm_registry)"]
    end
    
    subgraph "Communication"
        SocketIO["socketio.AsyncServer"]
        EventStreamSubscriber["EventStreamSubscriber.SERVER"]
    end
    
    subgraph "Agent Execution"
        AgentController["AgentController"]
        Runtime["Runtime"]
        Agent["Agent"]
    end
    
    WebSession --> AgentSession
    WebSession --> SocketIO
    WebSession --> EventStreamSubscriber
    
    AgentSession --> AgentController
    AgentSession --> Runtime
    AgentSession --> Agent
```

Sources: [openhands/server/session/session.py:74-112](), [openhands/server/session/agent_session.py:64-89]()

### Runtime Environment System

The runtime system provides sandboxed execution environments with multiple implementation options:

| Runtime Type | Implementation | Use Case |
|--------------|----------------|----------|
| `DockerRuntime` | [openhands/runtime/impl/docker]() | Local Docker-based sandbox |
| `RemoteRuntime` | [openhands/runtime/impl/remote]() | Remote execution environment |
| `LocalRuntime` | [openhands/runtime/impl/local]() | Direct local execution |
| `E2BRuntime` | [openhands/runtime/impl/e2b]() | E2B cloud sandbox |

The runtime architecture supports pluggable sandbox backends:

```mermaid
graph TB
    subgraph "Runtime Interface"
        BaseRuntime["Runtime<br/>(base.py)"]
        RuntimeConfig["RuntimeConfig<br/>(config)"]
    end
    
    subgraph "Runtime Implementations"
        DockerRuntime["DockerRuntime<br/>(impl/docker/docker_runtime.py)"]
        RemoteRuntime["RemoteRuntime<br/>(impl/remote/remote_runtime.py)"]
        LocalRuntime["LocalRuntime<br/>(impl/local/local_runtime.py)"]
        E2BRuntime["E2BRuntime<br/>(impl/e2b/e2b_runtime.py)"]
    end
    
    subgraph "Execution Server"
        ActionExecutionServer["ActionExecutionServer<br/>(server/action_execution.py)"]
        SandboxPlugins["SandboxPlugins<br/>(plugins/)"]
    end
    
    BaseRuntime --> DockerRuntime
    BaseRuntime --> RemoteRuntime
    BaseRuntime --> LocalRuntime
    BaseRuntime --> E2BRuntime
    
    DockerRuntime --> ActionExecutionServer
    ActionExecutionServer --> SandboxPlugins
```

Sources: [openhands/runtime/base.py](), [openhands/runtime/impl/docker](), [openhands/core/setup.py:35-89]()

### LLM Integration Framework

OpenHands supports multiple LLM providers through a unified registry system built on `litellm`:

```mermaid
graph LR
    subgraph "LLM Registry"
        LLMRegistry["LLMRegistry<br/>(llm_registry.py)"]
        LLMConfig["LLMConfig<br/>(config/llm_config.py)"]
        LiteLLM["LiteLLM Backend"]
    end
    
    subgraph "LLM Providers"
        OpenAI["OpenAI<br/>(openai)"]
        Anthropic["Anthropic<br/>(anthropic)"]
        Google["Google<br/>(google-genai)"]
        Local["Local Models<br/>(ollama/vllm)"]
    end
    
    subgraph "Configuration"
        AgentToLLMConfig["agent_to_llm_config<br/>(dict[str, LLMConfig])"]
        OpenHandsConfig["OpenHandsConfig<br/>(core/config.py)"]
    end
    
    LLMRegistry --> LLMConfig
    LLMRegistry --> LiteLLM
    LiteLLM --> OpenAI
    LiteLLM --> Anthropic
    LiteLLM --> Google
    LiteLLM --> Local
    
    OpenHandsConfig --> AgentToLLMConfig
    AgentToLLMConfig --> LLMConfig
```

Sources: [openhands/llm/llm_registry.py](), [pyproject.toml:29-30](), [openhands/core/config/llm_config.py]()

## Key Execution Workflows

### Agent Task Execution Flow

The primary execution workflow orchestrates user input through agent processing to action execution:

```mermaid
graph TD
    UserMessage["MessageAction<br/>(EventSource.USER)"] --> EventStream
    EventStream --> AgentControllerOnEvent["AgentController.on_event<br/>(agent_controller.py:392)"]
    AgentControllerOnEvent --> ShouldStep["should_step()<br/>(agent_controller.py:392)"]
    ShouldStep --> Step["_step()<br/>(agent_controller.py:440)"]
    
    Step --> AgentStep["agent.step()<br/>(controller/agent.py)"]
    AgentStep --> LLMCall["LLM.completion()<br/>(llm/)"]
    LLMCall --> ActionParsing["parse_response()<br/>(agent/)"]
    ActionParsing --> SecurityAnalysis["_handle_security_analyzer()<br/>(agent_controller.py:204)"]
    
    SecurityAnalysis --> RuntimeExecution["runtime.run_action()<br/>(runtime/)"]
    RuntimeExecution --> ObservationGeneration["Observation<br/>(events/observation/)"]
    ObservationGeneration --> EventStream
```

Sources: [openhands/controller/agent_controller.py:392-408](), [openhands/controller/agent_controller.py:440-500](), [openhands/controller/agent_controller.py:204-243]()

### Configuration and Initialization

OpenHands uses a layered configuration system combining TOML files, environment variables, and runtime settings:

| Configuration Source | File Path | Priority |
|---------------------|-----------|----------|
| Environment Variables | System environment | Highest |
| `config.toml` | [config.toml]() | Medium |
| Default Values | [openhands/core/config/]() | Lowest |

The initialization process follows this sequence:

```mermaid
graph TD
    ConfigParsing["parse_arguments()<br/>(core/config.py)"] --> SetupConfig["setup_config_from_args()<br/>(core/config.py)"]
    SetupConfig --> CreateAgent["create_agent()<br/>(core/setup.py:150)"]
    CreateAgent --> CreateRuntime["create_runtime()<br/>(core/setup.py:35)"]
    CreateRuntime --> CreateMemory["create_memory()<br/>(core/setup.py:200)"]
    CreateMemory --> CreateController["create_controller()<br/>(core/setup.py:240)"]
    CreateController --> RunAgent["run_agent_until_done()<br/>(core/loop.py)"]
```

Sources: [openhands/core/main.py:51-96](), [openhands/core/setup.py:35-89](), [openhands/core/config/]()

The system supports multiple deployment modes including local development, Docker containers, and cloud-based execution through this unified configuration and initialization framework.

Sources: [README.md:53-127](), [pyproject.toml:1-199](), [frontend/package.json:1-151]()