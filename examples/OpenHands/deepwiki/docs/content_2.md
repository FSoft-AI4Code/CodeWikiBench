3-Agent System

# Page: Agent System

# Agent System

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [openhands/controller/agent_controller.py](openhands/controller/agent_controller.py)
- [openhands/core/main.py](openhands/core/main.py)
- [openhands/core/setup.py](openhands/core/setup.py)
- [openhands/memory/view.py](openhands/memory/view.py)
- [openhands/runtime/impl/local/local_runtime.py](openhands/runtime/impl/local/local_runtime.py)
- [openhands/runtime/plugins/jupyter/__init__.py](openhands/runtime/plugins/jupyter/__init__.py)
- [openhands/runtime/plugins/jupyter/execute_server.py](openhands/runtime/plugins/jupyter/execute_server.py)
- [openhands/runtime/plugins/vscode/__init__.py](openhands/runtime/plugins/vscode/__init__.py)
- [openhands/runtime/plugins/vscode/settings.json](openhands/runtime/plugins/vscode/settings.json)
- [openhands/server/conversation_manager/conversation_manager.py](openhands/server/conversation_manager/conversation_manager.py)
- [openhands/server/conversation_manager/docker_nested_conversation_manager.py](openhands/server/conversation_manager/docker_nested_conversation_manager.py)
- [openhands/server/conversation_manager/standalone_conversation_manager.py](openhands/server/conversation_manager/standalone_conversation_manager.py)
- [openhands/server/data_models/feedback.py](openhands/server/data_models/feedback.py)
- [openhands/server/file_config.py](openhands/server/file_config.py)
- [openhands/server/mock/listen.py](openhands/server/mock/listen.py)
- [openhands/server/routes/manage_conversations.py](openhands/server/routes/manage_conversations.py)
- [openhands/server/session/agent_session.py](openhands/server/session/agent_session.py)
- [openhands/server/session/session.py](openhands/server/session/session.py)
- [openhands/server/static.py](openhands/server/static.py)
- [openhands/utils/http_session.py](openhands/utils/http_session.py)
- [tests/unit/runtime/impl/test_local_runtime.py](tests/unit/runtime/impl/test_local_runtime.py)
- [tests/unit/test_conversation_summary.py](tests/unit/test_conversation_summary.py)

</details>



The Agent System is the core orchestration layer of OpenHands that manages AI agent execution, state, and lifecycle. It provides the foundational infrastructure for running LLM-powered agents in sandboxed environments while maintaining conversation context and handling multi-agent coordination.

This document covers the agent orchestration engine, session management, and event-driven communication patterns. For runtime execution environments, see [Runtime & Execution Environment](#5). For LLM integration details, see [LLM Integration](#4). For user interface components, see [Frontend & User Interfaces](#6).

## Architecture Overview

The Agent System follows an event-driven architecture where agents react to user inputs and environmental observations through a centralized event stream. The system supports both single-agent workflows and multi-agent delegation patterns.

### Core Components Architecture

```mermaid
graph TB
    subgraph "Session Management Layer"
        WebSession["WebSession<br/>(session.py)"]
        AgentSession["AgentSession<br/>(agent_session.py)"]
        ConversationManager["ConversationManager<br/>(conversation_manager.py)"]
    end
    
    subgraph "Agent Orchestration Layer"
        AgentController["AgentController<br/>(agent_controller.py)"]
        StateTracker["StateTracker<br/>(state_tracker.py)"]
        Agent["Agent<br/>(agent.py)"]
        Memory["Memory<br/>(memory.py)"]
    end
    
    subgraph "Communication Layer"
        EventStream["EventStream<br/>(stream.py)"]
        EventSubscriber["EventStreamSubscriber<br/>(stream.py)"]
    end
    
    subgraph "State & Persistence"
        State["State<br/>(state.py)"]
        FileStore["FileStore<br/>(files.py)"]
        ConversationStats["ConversationStats<br/>(conversation_stats.py)"]
    end
    
    WebSession --> AgentSession
    AgentSession --> AgentController
    ConversationManager --> WebSession
    
    AgentController --> StateTracker
    AgentController --> Agent
    AgentController --> Memory
    AgentController --> EventStream
    
    StateTracker --> State
    EventStream --> EventSubscriber
    State --> FileStore
    AgentController --> ConversationStats
    
    style AgentController fill:#ffeeee
    style EventStream fill:#eeffee
    style State fill:#eeeeff
```

Sources: [openhands/controller/agent_controller.py:100-200](), [openhands/server/session/session.py:40-75](), [openhands/server/session/agent_session.py:42-88](), [openhands/server/conversation_manager/conversation_manager.py:20-50]()

## Agent Controller & State Management

The `AgentController` class serves as the central orchestrator for agent execution. It manages the agent lifecycle, handles event processing, and maintains conversation state across sessions.

### AgentController Core Components

```mermaid
graph TD
    subgraph "AgentController Class"
        controller_init["__init__()<br/>Initialize controller"]
        step_method["step()<br/>Execute agent step"]
        on_event["on_event()<br/>Handle incoming events"]
        set_agent_state["set_agent_state_to()<br/>Update agent state"]
        handle_action["_handle_action()<br/>Process agent actions"]
        handle_observation["_handle_observation()<br/>Process observations"]
    end
    
    subgraph "State Management"
        State_restore["State.restore_from_session()"]
        state_save["state.save_to_session()"]
        StateTracker_class["StateTracker<br/>run_control_flags()"]
        StuckDetector["StuckDetector<br/>_is_stuck()"]
    end
    
    subgraph "Event Processing"
        should_step["should_step()<br/>Determine if agent should act"]
        react_to_exception["_react_to_exception()<br/>Handle errors"]
        reset_method["_reset()<br/>Reset agent state"]
    end
    
    controller_init --> State_restore
    step_method --> should_step
    on_event --> handle_action
    on_event --> handle_observation
    step_method --> StateTracker_class
    step_method --> StuckDetector
    set_agent_state --> state_save
    step_method --> react_to_exception
    set_agent_state --> reset_method
    
    style step_method fill:#ffeeee
    style on_event fill:#eeffee
    style State_restore fill:#eeeeff
```

Sources: [openhands/controller/agent_controller.py:100-200](), [openhands/controller/agent_controller.py:358-390](), [openhands/controller/agent_controller.py:433-493](), [openhands/controller/state/state_tracker.py]()

### Agent State Lifecycle

The system manages agent states through the `AgentState` enum, transitioning between states based on events and conditions:

| State | Description | Triggers |
|-------|-------------|----------|
| `LOADING` | Agent initialization | Session startup |
| `AWAITING_USER_INPUT` | Waiting for user message | Agent requests input |
| `RUNNING` | Actively processing | User message received |
| `USER_CONFIRMED` | Action confirmed | User approval in confirmation mode |
| `USER_REJECTED` | Action rejected | User rejection in confirmation mode |
| `FINISHED` | Task completed | `AgentFinishAction` |
| `STOPPED` | Manual stop | User interruption |
| `ERROR` | Error occurred | Exception handling |

Sources: [openhands/controller/agent_controller.py:631-683](), [openhands/core/schema/agent.py]()

## Session Management

Session management handles the coordination between web clients, agent execution, and conversation persistence through a three-tier architecture.

### Session Architecture Flow

```mermaid
graph LR
    subgraph "Client Layer"
        WebClient["Web Client<br/>(React Frontend)"]
        SocketIO["Socket.IO<br/>Connection"]
    end
    
    subgraph "Session Layer"
        WebSession_manage["WebSession<br/>sio: socketio.AsyncServer<br/>agent_session: AgentSession"]
        ConversationManager_concrete["ConversationManager<br/>_local_agent_loops_by_sid<br/>_local_connection_id_to_session_id"]
    end
    
    subgraph "Agent Layer" 
        AgentSession_manage["AgentSession<br/>controller: AgentController<br/>runtime: Runtime<br/>memory: Memory"]
        AgentController_manage["AgentController<br/>agent: Agent<br/>event_stream: EventStream<br/>state: State"]
    end
    
    WebClient --> SocketIO
    SocketIO --> WebSession_manage
    ConversationManager_concrete --> WebSession_manage
    WebSession_manage --> AgentSession_manage
    AgentSession_manage --> AgentController_manage
    
    style WebSession_manage fill:#ffeeee
    style AgentSession_manage fill:#eeffee
    style ConversationManager_concrete fill:#eeeeff
```

Sources: [openhands/server/session/session.py:74-112](), [openhands/server/session/agent_session.py:64-88](), [openhands/server/conversation_manager/standalone_conversation_manager.py:53-77]()

### Session Initialization Process

The session initialization follows a specific sequence to set up the complete agent environment:

1. **WebSession Creation**: Socket.IO connection established
2. **Agent Configuration**: LLM config and agent type selection  
3. **Runtime Initialization**: Sandbox environment setup
4. **Memory Creation**: Context and microagent loading
5. **Controller Setup**: Agent controller with state restoration
6. **Event Stream Activation**: Begin event processing

Sources: [openhands/server/session/session.py:132-305](), [openhands/server/session/agent_session.py:90-223]()

## Event-Driven Communication

The system uses an event-driven architecture where all communication flows through the `EventStream` class, enabling loose coupling between components.

### Event Flow Architecture

```mermaid
graph TB
    subgraph "Event Sources"
        User["USER<br/>(MessageAction)"]
        Agent_src["AGENT<br/>(Actions/Responses)"]
        Environment["ENVIRONMENT<br/>(Observations)"]
    end
    
    subgraph "EventStream Core"
        EventStream_class["EventStream<br/>add_event()<br/>subscribe()<br/>get_events()"]
        EventStreamSubscriber_enum["EventStreamSubscriber<br/>AGENT_CONTROLLER<br/>SERVER<br/>MAIN"]
    end
    
    subgraph "Event Processors"
        AgentController_proc["AgentController<br/>on_event()<br/>should_step()"]
        WebSession_proc["WebSession<br/>on_event()<br/>dispatch()"]
        MainLoop["Main Loop<br/>run_controller()"]
    end
    
    subgraph "Event Types"
        Actions["Actions<br/>MessageAction<br/>CmdRunAction<br/>FileEditAction"]
        Observations["Observations<br/>CmdOutputObservation<br/>AgentStateChangedObservation"]
    end
    
    User --> EventStream_class
    Agent_src --> EventStream_class
    Environment --> EventStream_class
    
    EventStream_class --> EventStreamSubscriber_enum
    EventStreamSubscriber_enum --> AgentController_proc
    EventStreamSubscriber_enum --> WebSession_proc
    EventStreamSubscriber_enum --> MainLoop
    
    EventStream_class --> Actions
    EventStream_class --> Observations
    
    style EventStream_class fill:#ffeeee
    style EventStreamSubscriber_enum fill:#eeffee
```

Sources: [openhands/events/stream.py](), [openhands/controller/agent_controller.py:433-493](), [openhands/server/session/session.py:311-352](), [openhands/events/action/__init__.py](), [openhands/events/observation/__init__.py]()

### Event Processing Pipeline

Each event follows a consistent processing pipeline:

1. **Event Addition**: Added to `EventStream` with source attribution
2. **Subscriber Notification**: All registered subscribers receive event
3. **Filtering**: Each subscriber applies `should_step()` logic
4. **Processing**: Relevant subscribers process the event
5. **State Updates**: Agent state and conversation state updated
6. **Response Generation**: New events may be generated as responses

Sources: [openhands/controller/agent_controller.py:392-431](), [openhands/controller/agent_controller.py:467-493]()

## Agent Lifecycle Management

The agent lifecycle encompasses initialization, execution, error handling, and cleanup phases, with support for session restoration and state persistence.

### Agent Execution Loop

```mermaid
graph TD
    subgraph "Initialization Phase"
        create_agent["create_agent()<br/>(setup.py)"]
        create_runtime["create_runtime()<br/>(setup.py)"]
        create_memory["create_memory()<br/>(setup.py)"]
        create_controller["create_controller()<br/>(setup.py)"]
    end
    
    subgraph "Execution Loop"
        wait_event["Wait for Event<br/>(EventStream)"]
        should_step_check["should_step()<br/>(agent_controller.py)"]
        agent_step["agent.step()<br/>(Agent.step())"]
        execute_action["Execute Action<br/>(Runtime)"]
        observe_result["Generate Observation<br/>(Runtime/Environment)"]
    end
    
    subgraph "State Management"
        check_limits["run_control_flags()<br/>(StateTracker)"]
        stuck_detection["_is_stuck()<br/>(StuckDetector)"]
        save_state["save_state()<br/>(State)"]
    end
    
    subgraph "Error Handling"
        catch_exception["_react_to_exception()<br/>(agent_controller.py)"]
        set_error_state["set_agent_state_to(ERROR)<br/>(agent_controller.py)"]
        reset_agent["_reset()<br/>(agent_controller.py)"]
    end
    
    create_agent --> create_runtime
    create_runtime --> create_memory
    create_memory --> create_controller
    create_controller --> wait_event
    
    wait_event --> should_step_check
    should_step_check -->|Yes| check_limits
    check_limits -->|Pass| stuck_detection
    stuck_detection -->|Not stuck| agent_step
    agent_step --> execute_action
    execute_action --> observe_result
    observe_result --> save_state
    save_state --> wait_event
    
    check_limits -->|Fail| catch_exception
    stuck_detection -->|Stuck| catch_exception
    agent_step -->|Exception| catch_exception
    catch_exception --> set_error_state
    set_error_state --> reset_agent
    
    should_step_check -->|No| wait_event
    
    style agent_step fill:#ffeeee
    style check_limits fill:#eeffee
    style catch_exception fill:#ffcccc
```

Sources: [openhands/core/setup.py:202-243](), [openhands/controller/agent_controller.py:821-887](), [openhands/controller/agent_controller.py:302-391](), [openhands/controller/stuck.py]()

## Memory & Context Management

The `Memory` class provides context management for agents, including conversation history, repository information, runtime details, and microagent integration.

### Memory Architecture

```mermaid
graph TB
    subgraph "Memory Class Components"
        Memory_init["Memory<br/>__init__()<br/>event_stream: EventStream<br/>sid: str"]
        runtime_info["set_runtime_info()<br/>Available hosts<br/>Working directory"]
        repo_info["set_repository_info()<br/>Repository details<br/>Branch information"]
        microagents["load_user_workspace_microagents()<br/>Custom agent tools"]
        conversation_instructions["set_conversation_instructions()<br/>User-provided context"]
    end
    
    subgraph "Context Sources"
        EventStream_memory["EventStream<br/>Conversation history"]
        Runtime_memory["Runtime<br/>System information<br/>Available tools"]
        Repository["Repository<br/>Project context<br/>File structure"]
        Microagents["Microagents<br/>Custom tools<br/>Specialized capabilities"]
        UserSecrets["UserSecrets<br/>API keys<br/>Configuration"]
    end
    
    subgraph "Memory Integration"
        AgentSession_memory["AgentSession._create_memory()"]
        setup_memory["create_memory()<br/>(setup.py)"]
    end
    
    Memory_init --> runtime_info
    Memory_init --> repo_info
    Memory_init --> microagents
    Memory_init --> conversation_instructions
    
    runtime_info --> Runtime_memory
    repo_info --> Repository
    microagents --> Microagents
    Memory_init --> EventStream_memory
    runtime_info --> UserSecrets
    
    AgentSession_memory --> Memory_init
    setup_memory --> Memory_init
    
    style Memory_init fill:#ffeeee
    style runtime_info fill:#eeffee
    style microagents fill:#eeeeff
```

Sources: [openhands/memory/memory.py](), [openhands/server/session/agent_session.py:448-481](), [openhands/core/setup.py:157-199]()

## Multi-Agent Coordination

OpenHands supports multi-agent workflows through a delegation system where parent agents can spawn child agents for specialized tasks.

### Delegation Architecture

```mermaid
graph TD
    subgraph "Parent Agent"
        ParentController["AgentController<br/>parent: None<br/>delegate: AgentController"]
        ParentAgent["Agent<br/>(Primary task agent)"]
    end
    
    subgraph "Delegation Process"
        AgentDelegateAction["AgentDelegateAction<br/>agent: str<br/>inputs: dict"]
        start_delegate["start_delegate()<br/>(agent_controller.py)"]
        create_delegate_controller["Create Delegate Controller<br/>is_delegate=True"]
        delegate_state["State<br/>delegate_level++<br/>shared metrics"]
    end
    
    subgraph "Delegate Agent"
        DelegateController["AgentController<br/>parent: AgentController<br/>delegate: None"]
        DelegateAgent["Agent<br/>(Specialized agent)"]
    end
    
    subgraph "Completion Process"
        delegate_finish["AgentFinishAction<br/>AgentRejectAction<br/>ERROR state"]
        end_delegate["end_delegate()<br/>(agent_controller.py)"]
        AgentDelegateObservation["AgentDelegateObservation<br/>outputs: dict<br/>content: str"]
    end
    
    ParentController --> ParentAgent
    ParentAgent --> AgentDelegateAction
    AgentDelegateAction --> start_delegate
    start_delegate --> create_delegate_controller
    create_delegate_controller --> delegate_state
    
    delegate_state --> DelegateController
    DelegateController --> DelegateAgent
    
    DelegateController --> delegate_finish
    delegate_finish --> end_delegate
    end_delegate --> AgentDelegateObservation
    AgentDelegateObservation --> ParentController
    
    style start_delegate fill:#ffeeee
    style end_delegate fill:#eeffee
    style delegate_state fill:#eeeeff
```

Sources: [openhands/controller/agent_controller.py:693-753](), [openhands/controller/agent_controller.py:754-820](), [openhands/events/action/agent.py](), [openhands/events/observation/agent.py]()

### Delegation State Management

The delegation system maintains shared state across parent and child agents:

- **Iteration Counter**: Shared across all agents to enforce global limits
- **Budget Tracking**: Global budget accumulation across delegation chain  
- **Metrics Collection**: Consolidated metrics from all agents
- **Event Stream**: Single event stream shared between parent and delegates
- **State Isolation**: Each agent maintains independent conversation state

Sources: [openhands/controller/agent_controller.py:717-752](), [openhands/controller/state/state.py]()