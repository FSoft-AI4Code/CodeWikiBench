6-Frontend & User Interfaces

# Page: Frontend & User Interfaces

# Frontend & User Interfaces

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [frontend/src/api/open-hands.ts](frontend/src/api/open-hands.ts)
- [frontend/src/api/open-hands.types.ts](frontend/src/api/open-hands.types.ts)
- [frontend/src/hooks/mutation/use-save-settings.ts](frontend/src/hooks/mutation/use-save-settings.ts)
- [frontend/src/hooks/query/use-settings.ts](frontend/src/hooks/query/use-settings.ts)
- [frontend/src/i18n/declaration.ts](frontend/src/i18n/declaration.ts)
- [frontend/src/i18n/translation.json](frontend/src/i18n/translation.json)
- [frontend/src/mocks/handlers.ts](frontend/src/mocks/handlers.ts)
- [frontend/src/routes/app-settings.tsx](frontend/src/routes/app-settings.tsx)
- [frontend/src/routes/llm-settings.tsx](frontend/src/routes/llm-settings.tsx)
- [frontend/src/services/settings.ts](frontend/src/services/settings.ts)
- [frontend/src/types/settings.ts](frontend/src/types/settings.ts)
- [openhands/cli/commands.py](openhands/cli/commands.py)
- [openhands/cli/main.py](openhands/cli/main.py)
- [openhands/cli/pt_style.py](openhands/cli/pt_style.py)
- [openhands/cli/settings.py](openhands/cli/settings.py)
- [openhands/cli/tui.py](openhands/cli/tui.py)
- [openhands/core/schema/exit_reason.py](openhands/core/schema/exit_reason.py)
- [openhands/storage/data_models/settings.py](openhands/storage/data_models/settings.py)
- [tests/unit/cli/test_cli_tui.py](tests/unit/cli/test_cli_tui.py)

</details>



This page covers OpenHands' user interface systems, including the web-based React frontend, command-line interface (CLI), and the API communication layer that connects them to the backend services. This documentation focuses on the client-side architecture, user interaction patterns, and communication protocols.

For detailed information about the web interface implementation and API endpoints, see [Web Interface & API](#6.1). For comprehensive CLI usage and terminal interface details, see [Command Line Interface](#6.2).

## Architecture Overview

OpenHands provides multiple user interface options to accommodate different user preferences and use cases. The system supports both graphical and text-based interactions through a unified backend API.

## Frontend Architecture Components

```mermaid
graph TB
    subgraph "User Interfaces"
        WEB["React Web App<br/>frontend/"]
        CLI["CLI Interface<br/>openhands/cli/"]
    end
    
    subgraph "Communication Layer"
        API_CLIENT["OpenHands API Client<br/>open-hands.ts"]
        WS_CLIENT["WebSocket Client<br/>Real-time Events"]
        HTTP_CLIENT["HTTP Client<br/>REST Endpoints"]
    end
    
    subgraph "State Management"
        REDUX["Redux Store<br/>State Management"]
        SETTINGS_STORE["Settings Store<br/>Local Configuration"]
        REACT_QUERY["React Query<br/>Server State"]
    end
    
    subgraph "Backend Services"
        FASTAPI["FastAPI Server<br/>REST + WebSocket"]
        EVENT_STREAM["EventStream<br/>Real-time Communication"]
    end
    
    WEB --> API_CLIENT
    CLI --> HTTP_CLIENT
    
    API_CLIENT --> WS_CLIENT
    API_CLIENT --> HTTP_CLIENT
    API_CLIENT --> REACT_QUERY
    
    WEB --> REDUX
    WEB --> SETTINGS_STORE
    CLI --> SETTINGS_STORE
    
    WS_CLIENT --> EVENT_STREAM
    HTTP_CLIENT --> FASTAPI
    
    REACT_QUERY --> FASTAPI
```

**Sources:** [frontend/src/api/open-hands.ts:1-501](), [openhands/cli/main.py:1-644](), [openhands/cli/tui.py:1-1016](), [frontend/src/hooks/query/use-settings.ts:1-91]()

## Web Frontend System

The web frontend is a React-based single-page application that provides a graphical interface for interacting with OpenHands agents. It features real-time communication, internationalization support, and comprehensive settings management.

### Core Web Components

```mermaid
graph TD
    subgraph "React Application"
        APP["App Component"]
        ROUTES["Route Components<br/>app-settings.tsx<br/>llm-settings.tsx"]
        COMPONENTS["UI Components<br/>Settings Forms<br/>Chat Interface"]
    end
    
    subgraph "State Management"
        REDUX_STORE["Redux Store<br/>Application State"]
        REACT_QUERY_CLIENT["React Query Client<br/>useSettings<br/>useSaveSettings"]
        SETTINGS_HOOK["useSettings Hook<br/>use-settings.ts"]
    end
    
    subgraph "API Integration"
        OPEN_HANDS_CLIENT["OpenHands Class<br/>Static Methods"]
        SETTINGS_SERVICE["SettingsService<br/>API Endpoints"]
        WS_COMMUNICATION["WebSocket Events<br/>Real-time Updates"]
    end
    
    subgraph "Internationalization"
        I18N_SYSTEM["i18n System<br/>translation.json"]
        LANGUAGE_SUPPORT["Multi-language Support<br/>16 Languages"]
    end
    
    APP --> ROUTES
    ROUTES --> COMPONENTS
    COMPONENTS --> REDUX_STORE
    COMPONENTS --> REACT_QUERY_CLIENT
    
    REACT_QUERY_CLIENT --> SETTINGS_HOOK
    SETTINGS_HOOK --> OPEN_HANDS_CLIENT
    OPEN_HANDS_CLIENT --> SETTINGS_SERVICE
    OPEN_HANDS_CLIENT --> WS_COMMUNICATION
    
    COMPONENTS --> I18N_SYSTEM
    I18N_SYSTEM --> LANGUAGE_SUPPORT
```

**Sources:** [frontend/src/api/open-hands.ts:24-500](), [frontend/src/hooks/query/use-settings.ts:10-91](), [frontend/src/hooks/mutation/use-save-settings.ts:1-78](), [frontend/src/routes/app-settings.tsx:1-265](), [frontend/src/i18n/translation.json:1-50]()

The web frontend uses React Query for server state management, with hooks like `useSettings()` and `useSaveSettings()` providing reactive data binding. The `OpenHands` class serves as the main API client, exposing static methods for all backend communication.

## Command Line Interface System

The CLI provides a text-based interface using prompt_toolkit for rich terminal interactions. It supports real-time agent communication, command processing, and comprehensive settings management through terminal prompts.

### CLI Architecture Components

```mermaid
graph TD
    subgraph "CLI Entry Points"
        MAIN["main.py<br/>run_session()"]
        COMMANDS["commands.py<br/>handle_commands()"]
    end
    
    subgraph "Terminal UI"
        TUI["tui.py<br/>Terminal Interface"]
        DISPLAY_FUNCTIONS["Display Functions<br/>display_event()<br/>display_banner()"]
        INPUT_FUNCTIONS["Input Functions<br/>read_prompt_input()<br/>cli_confirm()"]
    end
    
    subgraph "CLI Settings"
        SETTINGS_CLI["settings.py<br/>modify_llm_settings_basic()"]
        FILE_SETTINGS_STORE["FileSettingsStore<br/>Persistent Storage"]
    end
    
    subgraph "Agent Communication"
        EVENT_STREAM["EventStream<br/>Real-time Events"]
        AGENT_CONTROLLER["AgentController<br/>Agent Management"]
    end
    
    MAIN --> COMMANDS
    MAIN --> TUI
    COMMANDS --> SETTINGS_CLI
    
    TUI --> DISPLAY_FUNCTIONS
    TUI --> INPUT_FUNCTIONS
    
    SETTINGS_CLI --> FILE_SETTINGS_STORE
    
    MAIN --> EVENT_STREAM
    EVENT_STREAM --> AGENT_CONTROLLER
    
    DISPLAY_FUNCTIONS --> EVENT_STREAM
```

**Sources:** [openhands/cli/main.py:91-644](), [openhands/cli/tui.py:79-1016](), [openhands/cli/commands.py:122-174](), [openhands/cli/settings.py:1-566]()

The CLI uses an event-driven architecture where `display_event()` handles real-time updates from the agent, while command processing through `handle_commands()` manages user interactions and system control.

## API Communication Layer

Both interfaces communicate with the backend through a unified API layer that handles HTTP requests, WebSocket connections, and session management.

### OpenHands API Client Structure

| Method Category | Key Methods | Purpose |
|---|---|---|
| **Conversation Management** | `createConversation()`, `getConversation()`, `updateConversation()` | CRUD operations for conversations |
| **Session Control** | `startConversation()`, `stopConversation()` | Agent lifecycle management |
| **File Operations** | `getFiles()`, `getFile()`, `uploadFiles()` | Workspace file management |
| **Real-time Communication** | `getConversationHeaders()`, WebSocket integration | Live agent interaction |
| **Feedback System** | `submitFeedback()`, `getBatchFeedback()` | User feedback collection |

**Sources:** [frontend/src/api/open-hands.ts:67-500](), [frontend/src/api/open-hands.types.ts:1-142]()

The `OpenHands` class provides static methods for all API operations, with automatic session management through `currentConversation` state and authentication headers via `getConversationHeaders()`.

## Settings and Configuration Management

Both interfaces share a unified settings system that persists user preferences and system configuration across sessions.

### Settings Architecture

```mermaid
graph LR
    subgraph "Frontend Settings"
        WEB_SETTINGS["Web Settings Forms<br/>app-settings.tsx<br/>llm-settings.tsx"]
        SETTINGS_HOOKS["React Hooks<br/>useSettings<br/>useSaveSettings"]
    end
    
    subgraph "CLI Settings"
        CLI_SETTINGS["CLI Settings<br/>settings.py"]
        CLI_COMMANDS["Settings Commands<br/>/settings command"]
    end
    
    subgraph "Settings Storage"
        DEFAULT_SETTINGS["DEFAULT_SETTINGS<br/>services/settings.ts"]
        API_SETTINGS["ApiSettings<br/>Backend Storage"]
        FILE_SETTINGS["FileSettingsStore<br/>Local Config Files"]
    end
    
    subgraph "Configuration Types"
        SETTINGS_TYPE["Settings Type<br/>types/settings.ts"]
        MCP_CONFIG["MCPConfig<br/>MCP Server Configuration"]
        POST_SETTINGS["PostSettings<br/>API Request Format"]
    end
    
    WEB_SETTINGS --> SETTINGS_HOOKS
    CLI_SETTINGS --> CLI_COMMANDS
    
    SETTINGS_HOOKS --> DEFAULT_SETTINGS
    CLI_COMMANDS --> FILE_SETTINGS
    
    DEFAULT_SETTINGS --> API_SETTINGS
    FILE_SETTINGS --> API_SETTINGS
    
    API_SETTINGS --> SETTINGS_TYPE
    SETTINGS_TYPE --> MCP_CONFIG
    SETTINGS_TYPE --> POST_SETTINGS
```

**Sources:** [frontend/src/services/settings.ts:1-40](), [frontend/src/types/settings.ts:1-72](), [openhands/cli/settings.py:41-566](), [openhands/storage/data_models/settings.py:21-187]()

Settings are managed through a layered system where `DEFAULT_SETTINGS` provides fallback values, while user modifications are persisted via API endpoints or local file storage depending on the interface used.

## Internationalization System

The web frontend supports 16 languages through a comprehensive i18n system with over 3000 translation keys.

### Translation System Structure

| Component | File | Purpose |
|---|---|---|
| **Translation Data** | `frontend/src/i18n/translation.json` | Complete translation database |
| **Type Declarations** | `frontend/src/i18n/declaration.ts` | TypeScript enum for translation keys |
| **Language Support** | React i18next integration | Runtime language switching |

The i18n system uses a hierarchical key structure like `SETTINGS$LLM_API_KEY` and `MICROAGENT$ADD_TO_MICROAGENT`, providing type-safe access to translations through the `I18nKey` enum.

**Sources:** [frontend/src/i18n/translation.json:1-5986](), [frontend/src/i18n/declaration.ts:1-598]()

## Authentication and Session Management

Both interfaces handle authentication and session management through a unified system that supports conversation-based sessions and API key authentication.

### Session Management Components

- **Conversation Sessions**: Each conversation gets a unique `conversation_id` and optional `session_api_key`
- **Authentication Headers**: Managed through `getConversationHeaders()` in the API client
- **Session State**: Tracked through `currentConversation` in the OpenHands class
- **Settings Integration**: User authentication status affects settings availability

The system supports both authenticated and guest modes, with settings and conversation history persistence dependent on authentication status.

**Sources:** [frontend/src/api/open-hands.ts:57-64](), [frontend/src/hooks/query/use-settings.ts:45-58](), [openhands/cli/main.py:140-444]()