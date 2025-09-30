3.1-Agent Controller & Orchestration

# Page: Agent Controller & Orchestration

# Agent Controller & Orchestration

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [openhands/controller/agent_controller.py](openhands/controller/agent_controller.py)
- [openhands/core/main.py](openhands/core/main.py)
- [openhands/core/setup.py](openhands/core/setup.py)
- [openhands/memory/view.py](openhands/memory/view.py)
- [openhands/server/routes/manage_conversations.py](openhands/server/routes/manage_conversations.py)
- [openhands/server/session/agent_session.py](openhands/server/session/agent_session.py)
- [openhands/server/session/session.py](openhands/server/session/session.py)
- [openhands/utils/http_session.py](openhands/utils/http_session.py)

</details>



This document covers the core orchestration system that manages agent execution, lifecycle, and coordination within OpenHands. The Agent Controller serves as the central decision engine that processes events, manages agent state transitions, coordinates between multiple agents through delegation, and integrates with runtime environments and LLM services.

For information about the runtime execution environment, see [Runtime & Execution Environment](#5). For details about LLM integration and configuration, see [LLM Integration](#4). For memory and prompt management, see [Memory & Prompt Management](#3.2).

## Core Architecture

The orchestration system is built around several key components that work together to manage agent execution:

```mermaid
graph TB
    subgraph "Session Layer"
        WS["WebSession<br/>Client Connection"]
        AS["AgentSession<br/>Agent Runtime Coordination"]
    end
    
    subgraph "Controller Layer"
        AC["AgentController<br/>Central Orchestration Engine"]
        ST["StateTracker<br/>State Management"]
        SD["StuckDetector<br/>Loop Detection"]
    end
    
    subgraph "Agent Layer" 
        AGENT["Agent<br/>LLM-powered Decision Maker"]
        DELEGATE["Delegate Agent<br/>Subtask Handler"]
    end
    
    subgraph "Event & Communication"
        ES["EventStream<br/>Message Bus"]
        EM["ReplayManager<br/>Trajectory Replay"]
    end
    
    subgraph "External Systems"
        RT["Runtime<br/>Execution Environment"]
        LLM["LLMRegistry<br/>Model Access"]
        MEM["Memory<br/>Context Management"]
    end
    
    WS --> AS
    AS --> AC
    AC --> ST
    AC --> SD
    AC --> AGENT
    AC --> DELEGATE
    AC --> ES
    AC --> EM
    
    AGENT --> LLM
    AC --> RT
    AC --> MEM
    
    ES --> RT
    ES --> WS
```

**Agent Controller Orchestration Flow**

Sources: [openhands/controller/agent_controller.py:100-200](), [openhands/server/session/agent_session.py:42-90](), [openhands/server/session/session.py:40-112]()

The `AgentController` class serves as the central orchestration engine, managing the complete lifecycle of agent execution. It coordinates between the agent's decision-making process, the runtime environment, and the user interface through an event-driven architecture.

## Agent Controller Lifecycle

The agent controller follows a well-defined lifecycle with clear state transitions and event processing:

```mermaid
stateDiagram-v2
    [*] --> LOADING
    LOADING --> RUNNING: initialize_agent()
    LOADING --> ERROR: initialization_failed
    
    RUNNING --> AWAITING_USER_INPUT: wait_for_response
    RUNNING --> AWAITING_USER_CONFIRMATION: security_risk_detected
    RUNNING --> STOPPED: user_stop
    RUNNING --> ERROR: exception_occurred
    RUNNING --> FINISHED: AgentFinishAction
    RUNNING --> REJECTED: AgentRejectAction
    RUNNING --> RATE_LIMITED: rate_limit_hit
    
    AWAITING_USER_INPUT --> RUNNING: user_message
    AWAITING_USER_CONFIRMATION --> USER_CONFIRMED: user_confirms
    AWAITING_USER_CONFIRMATION --> USER_REJECTED: user_rejects
    USER_CONFIRMED --> RUNNING: action_executed
    USER_REJECTED --> AWAITING_USER_INPUT: action_cancelled
    
    RATE_LIMITED --> RUNNING: retry_successful
    RATE_LIMITED --> ERROR: max_retries_exceeded
    
    ERROR --> RUNNING: user_restart
    STOPPED --> RUNNING: user_restart
    FINISHED --> [*]
    REJECTED --> [*]
    ERROR --> [*]
```

**Agent State Transition Diagram**

Sources: [openhands/controller/agent_controller.py:631-683](), [openhands/core/schema.py]()

### State Management Implementation

The `StateTracker` and controller work together to manage agent state transitions:

| State | Description | Triggers | Next States |
|-------|-------------|----------|-------------|
| `LOADING` | Agent initializing | Session start | `RUNNING`, `ERROR` |
| `RUNNING` | Agent actively processing | User message, observation | `AWAITING_USER_INPUT`, `STOPPED`, `ERROR`, `FINISHED` |
| `AWAITING_USER_INPUT` | Waiting for user response | Agent requests input | `RUNNING` |
| `AWAITING_USER_CONFIRMATION` | Security confirmation needed | High-risk action detected | `USER_CONFIRMED`, `USER_REJECTED` |
| `STOPPED` | Agent halted by user | Stop button pressed | `RUNNING` |
| `ERROR` | Error state | Exception occurred | `RUNNING` |
| `FINISHED` | Task completed successfully | `AgentFinishAction` | Terminal |
| `REJECTED` | Task rejected by agent | `AgentRejectAction` | Terminal |

Sources: [openhands/controller/agent_controller.py:631-683](), [openhands/controller/state/state_tracker.py]()

## Event Orchestration

The event orchestration system processes all communication between components through a centralized event stream:

```mermaid
graph LR
    subgraph "Event Sources"
        USER["EventSource.USER<br/>User Input"]
        AGENT_SRC["EventSource.AGENT<br/>Agent Actions"]
        ENV["EventSource.ENVIRONMENT<br/>Runtime Observations"]
    end
    
    subgraph "Event Stream Processing"
        ES["EventStream<br/>sid, file_store"]
        AC["AgentController<br/>on_event()"]
        WS_HANDLER["WebSession<br/>on_event()"]
    end
    
    subgraph "Event Types"
        ACTIONS["Actions<br/>MessageAction<br/>CmdRunAction<br/>FileEditAction<br/>AgentDelegateAction"]
        OBSERVATIONS["Observations<br/>CmdOutputObservation<br/>ErrorObservation<br/>AgentStateChangedObservation"]
    end
    
    subgraph "Event Processing Flow"
        SHOULD_STEP{"should_step()"}
        STEP["_step()"]
        HANDLE_ACTION["_handle_action()"]
        HANDLE_OBS["_handle_observation()"]
    end
    
    USER --> ES
    AGENT_SRC --> ES
    ENV --> ES
    
    ES --> AC
    ES --> WS_HANDLER
    
    AC --> SHOULD_STEP
    SHOULD_STEP -->|true| STEP
    AC --> HANDLE_ACTION
    AC --> HANDLE_OBS
    
    STEP --> ACTIONS
    HANDLE_ACTION --> OBSERVATIONS
```

**Event Processing Architecture**

Sources: [openhands/controller/agent_controller.py:433-493](), [openhands/events/](), [openhands/server/session/session.py:311-352]()

### Event Processing Logic

The controller implements sophisticated event processing logic in the `should_step()` method:

```python
# Key decision logic for when agent should take a step
def should_step(self, event: Event) -> bool:
    if self.delegate is not None:
        return False  # Delegate is active
    
    if isinstance(event, MessageAction) and event.source == EventSource.USER:
        return True  # User message triggers step
    
    if isinstance(event, Observation) and not isinstance(event, NullObservation):
        return True  # Environment feedback triggers step
```

Sources: [openhands/controller/agent_controller.py:392-431]()

## Agent Delegation System

OpenHands supports a multi-agent architecture where agents can delegate subtasks to specialized agents:

```mermaid
graph TD
    subgraph "Parent Agent Context"
        PARENT_AC["Parent AgentController<br/>Main Task Coordination"]
        PARENT_AGENT["Parent Agent<br/>Primary Decision Maker"]
    end
    
    subgraph "Delegation Process"
        DELEGATE_ACTION["AgentDelegateAction<br/>subtask specification"]
        CREATE_DELEGATE["start_delegate()<br/>spawn new controller"]
    end
    
    subgraph "Delegate Agent Context"
        DELEGATE_AC["Delegate AgentController<br/>is_delegate=True"]
        DELEGATE_AGENT_INST["Delegate Agent<br/>Specialized for Subtask"]
        DELEGATE_STATE["Delegate State<br/>separate metrics/iteration"]
    end
    
    subgraph "Delegation Lifecycle"
        ACTIVE{"Delegate Active?"}
        FORWARD_EVENTS["Forward Events to Delegate"]
        DELEGATE_RESULT["AgentDelegateObservation<br/>subtask results"]
        END_DELEGATE["end_delegate()<br/>cleanup and merge metrics"]
    end
    
    PARENT_AC --> PARENT_AGENT
    PARENT_AGENT --> DELEGATE_ACTION
    DELEGATE_ACTION --> CREATE_DELEGATE
    CREATE_DELEGATE --> DELEGATE_AC
    DELEGATE_AC --> DELEGATE_AGENT_INST
    DELEGATE_AC --> DELEGATE_STATE
    
    PARENT_AC --> ACTIVE
    ACTIVE -->|Yes| FORWARD_EVENTS
    FORWARD_EVENTS --> DELEGATE_AC
    ACTIVE -->|No| END_DELEGATE
    DELEGATE_AC --> DELEGATE_RESULT
    DELEGATE_RESULT --> END_DELEGATE
```

**Agent Delegation Architecture**

Sources: [openhands/controller/agent_controller.py:693-819](), [openhands/controller/agent_controller.py:439-462]()

### Delegation Implementation Details

The delegation system maintains separate execution contexts while sharing global resources:

| Component | Parent | Delegate | Notes |
|-----------|---------|----------|-------|
| `event_stream` | Subscriber | Non-subscriber | Delegate doesn't directly subscribe |
| `metrics` | Shared reference | Shared reference | Global accumulation |
| `iteration_flag` | Parent counter | Delegate counter | Merged on completion |
| `state` | Parent state | Isolated state | Separate delegate_level |
| `sid` | Original | `{parent_sid}-delegate` | Unique identifier |

Sources: [openhands/controller/agent_controller.py:717-752]()

## Session Management Integration

The orchestration system integrates with session management layers to provide scalable multi-user support:

```mermaid
graph TB
    subgraph "Client Layer"
        CLIENT["Web Client<br/>React Frontend"]
        WS_CONN["WebSocket Connection<br/>Real-time Communication"]
    end
    
    subgraph "Session Management"
        WS["WebSession<br/>sid, sio, conversation_stats"]
        AS["AgentSession<br/>runtime, controller, memory"]
        CM["ConversationManager<br/>Multi-session Coordination"]
    end
    
    subgraph "Agent Orchestration"
        AC["AgentController<br/>Agent Execution Engine"]
        ES["EventStream<br/>Event Processing Hub"]
        ST["StateTracker<br/>Persistent State Management"]
    end
    
    subgraph "Resource Management"
        RT["Runtime<br/>Sandboxed Execution"]
        LLM["LLMRegistry<br/>Model Access"]
        FS["FileStore<br/>Persistent Storage"]
    end
    
    CLIENT --> WS_CONN
    WS_CONN --> WS
    WS --> AS
    AS --> AC
    AC --> ES
    AC --> ST
    
    AS --> RT
    AS --> LLM
    ES --> FS
    ST --> FS
    
    CM --> WS
    CM --> AS
```

**Session Management Integration**

Sources: [openhands/server/session/session.py:40-130](), [openhands/server/session/agent_session.py:42-106](), [openhands/server/shared.py]()

### Session Lifecycle Coordination

The session management system coordinates the complete lifecycle from client connection to resource cleanup:

1. **Session Creation**: `WebSession` created on client connection with unique `sid`
2. **Agent Initialization**: `AgentSession.start()` creates controller, runtime, memory
3. **Event Processing**: Events flow through `EventStream` to `AgentController`
4. **Resource Management**: Runtime containers, LLM connections managed per session
5. **Session Cleanup**: `close()` methods ensure proper resource deallocation

Sources: [openhands/server/session/agent_session.py:90-223](), [openhands/server/session/session.py:119-130]()

## Integration Points

The Agent Controller integrates with multiple system components through well-defined interfaces:

### Runtime Integration
- **Security Analysis**: Integration with `SecurityAnalyzer` for action risk assessment
- **Action Execution**: Direct communication with runtime for command execution
- **Status Callbacks**: Runtime status updates propagated through controller

Sources: [openhands/controller/agent_controller.py:204-243](), [openhands/controller/agent_controller.py:443]()

### LLM Integration
- **Registry Access**: Controller accesses LLM services through `LLMRegistry`
- **Error Handling**: Comprehensive LLM error handling with state transitions
- **Budget Management**: LLM usage tracking and budget enforcement

Sources: [openhands/controller/agent_controller.py:302-390](), [openhands/controller/state/state_tracker.py]()

### Memory Integration
- **Context Management**: Memory system provides conversation context to agents
- **Microagent Loading**: Integration with workspace-specific microagents
- **Repository Information**: Git repository context and branch management

Sources: [openhands/server/session/agent_session.py:448-481](), [openhands/memory/memory.py]()

### Error Handling and Recovery

The controller implements comprehensive error handling with automatic recovery mechanisms:

```mermaid
graph TD
    subgraph "Error Detection"
        EXCEPTION["Exception Caught"]
        ERROR_TYPE{"Error Type Analysis"}
    end
    
    subgraph "Error Classification"
        AUTH_ERR["AuthenticationError<br/>ERROR_LLM_AUTHENTICATION"]
        RATE_ERR["RateLimitError<br/>RATE_LIMITED State"]
        BUDGET_ERR["ExceededBudget<br/>ERROR_LLM_OUT_OF_CREDITS"]
        CONTENT_ERR["ContentPolicyViolationError<br/>ERROR_LLM_CONTENT_POLICY"]
        STUCK_ERR["AgentStuckInLoopError<br/>Loop Detection"]
    end
    
    subgraph "Error Response"
        STATE_UPDATE["set_agent_state_to(AgentState.ERROR)"]
        STATUS_CALLBACK["status_callback('error', ...)"]
        ERROR_STORAGE["state.last_error = error_message"]
        USER_NOTIFICATION["Error message to user"]
    end
    
    EXCEPTION --> ERROR_TYPE
    ERROR_TYPE --> AUTH_ERR
    ERROR_TYPE --> RATE_ERR
    ERROR_TYPE --> BUDGET_ERR
    ERROR_TYPE --> CONTENT_ERR
    ERROR_TYPE --> STUCK_ERR
    
    AUTH_ERR --> STATE_UPDATE
    RATE_ERR --> STATE_UPDATE
    BUDGET_ERR --> STATE_UPDATE
    CONTENT_ERR --> STATE_UPDATE
    STUCK_ERR --> STATE_UPDATE
    
    STATE_UPDATE --> STATUS_CALLBACK
    STATE_UPDATE --> ERROR_STORAGE
    STATE_UPDATE --> USER_NOTIFICATION
```

**Error Handling and Recovery System**

Sources: [openhands/controller/agent_controller.py:302-390](), [openhands/controller/agent_controller.py:849-860](), [openhands/controller/stuck.py]()