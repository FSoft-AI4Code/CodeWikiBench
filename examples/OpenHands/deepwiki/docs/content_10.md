6.2-Command Line Interface

# Page: Command Line Interface

# Command Line Interface

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [openhands/cli/commands.py](openhands/cli/commands.py)
- [openhands/cli/main.py](openhands/cli/main.py)
- [openhands/cli/pt_style.py](openhands/cli/pt_style.py)
- [openhands/cli/settings.py](openhands/cli/settings.py)
- [openhands/cli/tui.py](openhands/cli/tui.py)
- [openhands/core/schema/exit_reason.py](openhands/core/schema/exit_reason.py)
- [tests/unit/cli/test_cli_tui.py](tests/unit/cli/test_cli_tui.py)

</details>



The Command Line Interface (CLI) provides a terminal-based text user interface (TUI) for interacting with OpenHands agents. It enables users to run agents locally, configure settings, manage conversations, and execute commands through an interactive prompt system. The CLI operates in headless mode with confirmation-based security controls and supports advanced features like MCP server integration and repository initialization.

For information about the web-based interface, see [Web Interface & API](#6.1). For details about agent orchestration and execution, see [Agent Controller & Orchestration](#3.1).

## CLI Architecture Overview

The CLI system consists of several interconnected components that handle user interaction, agent orchestration, and session management:

```mermaid
graph TB
    subgraph "CLI Entry Point"
        RCC["run_cli_command()"]
        MWL["main_with_loop()"]
    end
    
    subgraph "Session Management"
        RS["run_session()"]
        CS["cleanup_session()"]
        RSF["run_setup_flow()"]
    end
    
    subgraph "User Interface"
        TUI["TUI Display Functions"]
        PI["Prompt Input System"]
        CC["CommandCompleter"]
        CLI_CONFIRM["cli_confirm()"]
    end
    
    subgraph "Command Processing"
        HC["handle_commands()"]
        REPL["Command REPL Loop"]
        CMD_HANDLERS["Command Handlers"]
    end
    
    subgraph "Configuration"
        SETTINGS["Settings Management"]
        CONFIG_LOAD["Config Loading"]
        FILE_STORE["FileSettingsStore"]
    end
    
    subgraph "Agent Integration" 
        AC["AgentController"]
        ES["EventStream"]
        RT["Runtime"]
        MEM["Memory"]
    end
    
    RCC --> MWL
    MWL --> RSF
    MWL --> RS
    RS --> TUI
    RS --> PI
    RS --> HC
    HC --> CMD_HANDLERS
    HC --> REPL
    TUI --> CLI_CONFIRM
    PI --> CC
    MWL --> SETTINGS
    SETTINGS --> FILE_STORE
    RS --> AC
    RS --> ES
    RS --> RT
    RS --> MEM
    RS --> CS
```

**CLI System Architecture**

The CLI operates through a main event loop that coordinates user input, agent execution, and output rendering through a sophisticated terminal user interface.

Sources: [openhands/cli/main.py:758-781](), [openhands/cli/main.py:565-756](), [openhands/cli/tui.py:1-40]()

## Core CLI Components

### Main Entry Point and Session Management

The CLI entry point is handled by `run_cli_command` which sets up the event loop and manages the overall CLI lifecycle:

```mermaid
graph TD
    subgraph "CLI Startup Flow"
        ENTRY["run_cli_command()"] 
        LOOP["asyncio.new_event_loop()"]
        MAIN_LOOP["main_with_loop()"]
        CONFIG_SETUP["setup_config_from_args()"]
        SETTINGS_LOAD["FileSettingsStore.get_instance()"]
    end
    
    subgraph "Setup Flows"
        SETUP_FLOW["run_setup_flow()"]
        ALIAS_FLOW["run_alias_setup_flow()"]
        SECURITY_CHECK["check_folder_security_agreement()"]
    end
    
    subgraph "Session Execution"
        RUN_SESSION["run_session()"]
        SESSION_LOOP["Agent Session Loop"]
        CLEANUP["cleanup_session()"]
    end
    
    ENTRY --> LOOP
    LOOP --> MAIN_LOOP
    MAIN_LOOP --> CONFIG_SETUP
    MAIN_LOOP --> SETTINGS_LOAD
    MAIN_LOOP --> SETUP_FLOW
    MAIN_LOOP --> ALIAS_FLOW
    MAIN_LOOP --> SECURITY_CHECK
    MAIN_LOOP --> RUN_SESSION
    RUN_SESSION --> SESSION_LOOP
    SESSION_LOOP --> CLEANUP
    
    style RUN_SESSION fill:#f9f
    style SESSION_LOOP fill:#f9f
```

**CLI Startup and Session Flow**

The session management handles agent lifecycle, conversation persistence, and cleanup through coordinated async operations.

Sources: [openhands/cli/main.py:758-781](), [openhands/cli/main.py:565-756](), [openhands/cli/main.py:125-444]()

### Terminal User Interface System

The TUI system provides rich terminal output and interactive input handling through the `prompt_toolkit` library:

| Component | Function | Description |
|-----------|----------|-------------|
| **Display Functions** | `display_event()` | Routes events to appropriate display handlers |
| **Input System** | `read_prompt_input()` | Handles user input with command completion |
| **Confirmation UI** | `cli_confirm()` | Interactive choice selection with keyboard navigation |
| **Command Completion** | `CommandCompleter` | Auto-completion for CLI commands |
| **Streaming Output** | `update_streaming_output()` | Real-time command output display |
| **Styled Output** | `get_cli_style()` | Terminal styling and color management |

The event display system handles different event types through specialized display functions:

```mermaid
graph LR
    subgraph "Event Display Routing"
        DE["display_event()"]
        CRA["CmdRunAction"]
        MA["MessageAction"] 
        CO["CmdOutputObservation"]
        FE["FileEditObservation"]
        FR["FileReadObservation"]
        MCP_A["MCPAction"]
        MCP_O["MCPObservation"]
    end
    
    subgraph "Display Handlers"
        DC["display_command()"]
        DCO["display_command_output()"]
        DFE["display_file_edit()"]
        DFR["display_file_read()"]
        DM["display_message()"]
        DMCP_A["display_mcp_action()"]
        DMCP_O["display_mcp_observation()"]
    end
    
    DE --> CRA
    DE --> MA
    DE --> CO
    DE --> FE
    DE --> FR
    DE --> MCP_A
    DE --> MCP_O
    
    CRA --> DC
    CO --> DCO
    FE --> DFE
    FR --> DFR
    MA --> DM
    MCP_A --> DMCP_A
    MCP_O --> DMCP_O
```

**TUI Event Display System**

Sources: [openhands/cli/tui.py:260-305](), [openhands/cli/tui.py:384-587](), [openhands/cli/pt_style.py:13-28]()

## Interactive Command System

The CLI provides an interactive command system with a REPL (Read-Eval-Print Loop) that processes both user messages and special commands:

### Command Processing Flow

```mermaid
graph TD
    subgraph "Command Input"
        RPI["read_prompt_input()"]
        CC["CommandCompleter"]
        USER_INPUT["User Input"]
    end
    
    subgraph "Command Routing"
        HC["handle_commands()"]
        CMD_CHECK["Command Check"]
        SLASH_CMD["Slash Command"]
        USER_MSG["User Message"]
    end
    
    subgraph "Command Handlers"
        EXIT["handle_exit_command()"]
        HELP["handle_help_command()"]
        INIT["handle_init_command()"]
        STATUS["handle_status_command()"]
        NEW["handle_new_command()"]
        SETTINGS["handle_settings_command()"]
        RESUME["handle_resume_command()"]
        MCP["handle_mcp_command()"]
    end
    
    subgraph "Event Stream"
        ES["EventStream"]
        MA["MessageAction"]
        CSA["ChangeAgentStateAction"]
    end
    
    RPI --> USER_INPUT
    CC --> RPI
    USER_INPUT --> HC
    HC --> CMD_CHECK
    CMD_CHECK --> SLASH_CMD
    CMD_CHECK --> USER_MSG
    
    SLASH_CMD --> EXIT
    SLASH_CMD --> HELP
    SLASH_CMD --> INIT
    SLASH_CMD --> STATUS
    SLASH_CMD --> NEW
    SLASH_CMD --> SETTINGS
    SLASH_CMD --> RESUME
    SLASH_CMD --> MCP
    
    USER_MSG --> ES
    EXIT --> CSA
    NEW --> CSA
    USER_MSG --> MA
```

**Interactive Command Processing**

### Available Commands

The CLI supports the following interactive commands:

| Command | Handler Function | Description |
|---------|------------------|-------------|
| `/exit` | `handle_exit_command()` | Terminates the current session with confirmation |
| `/help` | `handle_help_command()` | Displays help information and available commands |
| `/init` | `handle_init_command()` | Initializes repository with microagent instructions |
| `/status` | `handle_status_command()` | Shows session status and usage metrics |
| `/new` | `handle_new_command()` | Creates a new conversation session |
| `/settings` | `handle_settings_command()` | Opens interactive settings configuration |
| `/resume` | `handle_resume_command()` | Resumes a paused agent |
| `/mcp` | `handle_mcp_command()` | Manages MCP server configuration |

Sources: [openhands/cli/commands.py:122-173](), [openhands/cli/tui.py:79-88](), [openhands/cli/tui.py:772-795]()

## Configuration and Settings Management

The CLI provides comprehensive configuration management through interactive menus and file-based persistence:

### Settings Architecture

```mermaid
graph TB
    subgraph "Configuration Sources"
        CLI_ARGS["Command Line Args"]
        CONFIG_TOML["config.toml"] 
        SETTINGS_JSON["settings.json"]
        ENV_VARS["Environment Variables"]
    end
    
    subgraph "Settings Management"
        FSS["FileSettingsStore"]
        SETTINGS_OBJ["Settings Object"]
        CONFIG_OBJ["OpenHandsConfig"]
    end
    
    subgraph "Interactive Configuration"
        DS["display_settings()"]
        MLS_BASIC["modify_llm_settings_basic()"]
        MLS_ADV["modify_llm_settings_advanced()"]
        MSA["modify_search_api_settings()"]
    end
    
    subgraph "Configuration UI"
        CLI_CONFIRM["cli_confirm()"]
        GVI["get_validated_input()"]
        FUZZY_COMPLETE["FuzzyWordCompleter"]
    end
    
    CLI_ARGS --> CONFIG_OBJ
    CONFIG_TOML --> CONFIG_OBJ
    ENV_VARS --> CONFIG_OBJ
    
    FSS --> SETTINGS_JSON
    FSS --> SETTINGS_OBJ
    SETTINGS_OBJ --> CONFIG_OBJ
    
    DS --> MLS_BASIC
    DS --> MLS_ADV
    DS --> MSA
    
    MLS_BASIC --> CLI_CONFIRM
    MLS_ADV --> GVI
    MSA --> GVI
    
    CLI_CONFIRM --> FUZZY_COMPLETE
    GVI --> FUZZY_COMPLETE
```

**Settings Management System**

### Settings Categories

The CLI settings system manages several configuration categories:

| Category | Configuration Function | Purpose |
|----------|----------------------|---------|
| **LLM Basic** | `modify_llm_settings_basic()` | Provider selection, model choice, API keys |
| **LLM Advanced** | `modify_llm_settings_advanced()` | Custom models, base URLs, advanced options |
| **Search API** | `modify_search_api_settings()` | Tavily search API configuration |
| **Agent Settings** | Agent configuration | Default agent, confirmation mode |
| **Memory Condensation** | Condenser configuration | Memory management settings |

The settings system uses a hierarchical precedence model where CLI arguments override config files, which override settings.json, which override defaults.

Sources: [openhands/cli/settings.py:233-487](), [openhands/cli/settings.py:41-121](), [openhands/cli/commands.py:269-291]()

## MCP Server Integration

The CLI provides comprehensive Model Context Protocol (MCP) server management through interactive commands:

### MCP Command System

```mermaid
graph TD
    subgraph "MCP Management Interface"
        MCP_CMD["/mcp Command"]
        MCP_MENU["MCP Menu Options"]
    end
    
    subgraph "MCP Operations" 
        LIST["List Servers"]
        ADD["Add Server"]
        REMOVE["Remove Server"]
        ERRORS["View Errors"]
    end
    
    subgraph "Server Types"
        SSE["SSE Servers"]
        STDIO["Stdio Servers"] 
        SHTTP["SHTTP Servers"]
    end
    
    subgraph "Configuration Management"
        CONFIG_FILE["config.toml"]
        LOAD_CONFIG["load_config_file()"]
        SAVE_CONFIG["save_config_file()"]
    end
    
    subgraph "Server Configuration"
        SSE_CONFIG["MCPSSEServerConfig"]
        STDIO_CONFIG["MCPStdioServerConfig"]
        SHTTP_CONFIG["MCPSHTTPServerConfig"]
    end
    
    MCP_CMD --> MCP_MENU
    MCP_MENU --> LIST
    MCP_MENU --> ADD
    MCP_MENU --> REMOVE
    MCP_MENU --> ERRORS
    
    ADD --> SSE
    ADD --> STDIO
    ADD --> SHTTP
    
    SSE --> SSE_CONFIG
    STDIO --> STDIO_CONFIG
    SHTTP --> SHTTP_CONFIG
    
    ADD --> SAVE_CONFIG
    REMOVE --> LOAD_CONFIG
    REMOVE --> SAVE_CONFIG
    
    SAVE_CONFIG --> CONFIG_FILE
    LOAD_CONFIG --> CONFIG_FILE
```

**MCP Server Management System**

The MCP integration supports three transport types:
- **SSE (Server-Sent Events)**: HTTP-based streaming connections
- **Stdio**: Standard input/output process communication  
- **SHTTP**: Streamable HTTP connections

Each server type has dedicated configuration handlers that validate input and persist settings to `config.toml`.

Sources: [openhands/cli/commands.py:431-884](), [openhands/cli/commands.py:507-563](), [openhands/cli/tui.py:199-238]()

## Agent Integration and Event Flow

The CLI integrates closely with the OpenHands agent system through event streams and session management:

### CLI-Agent Communication Flow

```mermaid
graph LR
    subgraph "CLI Components"
        USER_INPUT["User Input"]
        PROMPT_TASK["prompt_for_next_task()"]
        ON_EVENT["on_event_async()"]
    end
    
    subgraph "Event System"
        ES["EventStream"]
        EVENT_SUB["EventStreamSubscriber"]
        MSG_ACTION["MessageAction"]
        CHANGE_STATE["ChangeAgentStateAction"]
    end
    
    subgraph "Agent System"
        AC["AgentController"] 
        AGENT["Agent"]
        RT["Runtime"]
        MEM["Memory"]
    end
    
    subgraph "Agent States"
        RUNNING["RUNNING"]
        AWAITING_INPUT["AWAITING_USER_INPUT"]
        AWAITING_CONFIRM["AWAITING_USER_CONFIRMATION"]
        PAUSED["PAUSED"]
        FINISHED["FINISHED"]
    end
    
    USER_INPUT --> MSG_ACTION
    MSG_ACTION --> ES
    ES --> AC
    AC --> AGENT
    AGENT --> RT
    
    AC --> EVENT_SUB
    EVENT_SUB --> ON_EVENT
    ON_EVENT --> PROMPT_TASK
    
    ON_EVENT --> AWAITING_INPUT
    ON_EVENT --> AWAITING_CONFIRM
    ON_EVENT --> PAUSED
    ON_EVENT --> FINISHED
    
    AWAITING_CONFIRM --> CHANGE_STATE
    PAUSED --> PROMPT_TASK
```

**CLI-Agent Event Flow**

### Session Lifecycle Management

The CLI manages agent sessions through several key functions:

| Function | Purpose | Key Operations |
|----------|---------|----------------|
| `run_session()` | Main session orchestration | Agent creation, runtime setup, event handling |
| `cleanup_session()` | Session termination | Task cancellation, state persistence, resource cleanup |
| `on_event_async()` | Event processing | State change handling, user interaction prompts |
| `prompt_for_next_task()` | User input collection | Command processing, message creation |

The session system handles agent state transitions and coordinates between user input and agent execution through an event-driven architecture.

Sources: [openhands/cli/main.py:125-444](), [openhands/cli/main.py:91-123](), [openhands/cli/main.py:214-310]()

## Security and Confirmation System

The CLI implements a multi-layered security system with user confirmation for potentially risky operations:

### Security Architecture

```mermaid
graph TD
    subgraph "Security Checks"
        FSA["check_folder_security_agreement()"]
        TRUSTED_DIRS["Trusted Directories"]
        CONFIRM_MODE["Confirmation Mode"]
    end
    
    subgraph "Action Security Assessment"
        ACTION["Action"]
        SEC_RISK["ActionSecurityRisk"]
        HIGH["HIGH"]
        MEDIUM["MEDIUM"] 
        LOW["LOW"]
    end
    
    subgraph "Confirmation Flow"
        RCI["read_confirmation_input()"]
        CLI_CONFIRM["cli_confirm()"]
        SECURITY_PROMPT["Security Prompt"]
    end
    
    subgraph "Confirmation Modes"
        ALWAYS["Always Confirm"]
        AUTO_HIGH["Auto High-Risk"]
        MANUAL["Manual Confirm"]
    end
    
    FSA --> TRUSTED_DIRS
    ACTION --> SEC_RISK
    SEC_RISK --> HIGH
    SEC_RISK --> MEDIUM
    SEC_RISK --> LOW
    
    HIGH --> RCI
    MEDIUM --> RCI
    LOW --> RCI
    
    RCI --> CLI_CONFIRM
    CLI_CONFIRM --> SECURITY_PROMPT
    
    CLI_CONFIRM --> ALWAYS
    CLI_CONFIRM --> AUTO_HIGH
    CLI_CONFIRM --> MANUAL
```

**Security and Confirmation System**

The security system includes:
- **Folder Security**: Verification of workspace directory trust
- **Action Risk Assessment**: Classification of actions by security risk level
- **User Confirmation**: Interactive approval for risky operations
- **Confirmation Modes**: Flexible security policies

Sources: [openhands/cli/commands.py:384-428](), [openhands/cli/tui.py:839-869](), [openhands/cli/main.py:245-300]()

## Error Handling and User Experience

The CLI provides comprehensive error handling and user experience enhancements:

### Error Display System

The CLI includes specialized error handling for different components:

| Error Type | Handler | Description |
|------------|---------|-------------|
| **MCP Errors** | `display_mcp_errors()` | Shows MCP server connection issues |
| **Validation Errors** | `ValidationError` handling | Input validation with retry prompts |
| **Agent Errors** | `ErrorObservation` display | Agent execution error formatting |
| **Session Errors** | Session error recovery | Handles interrupted sessions and authentication errors |

The error system provides detailed error messages with actionable guidance and retry mechanisms for recoverable errors.

Sources: [openhands/cli/tui.py:199-238](), [openhands/cli/commands.py:636-727](), [openhands/cli/main.py:395-413]()