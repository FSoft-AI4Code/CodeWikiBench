9-Advanced Features

# Page: Advanced Features

# Advanced Features

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [.github/workflows/openhands-resolver.yml](.github/workflows/openhands-resolver.yml)
- [.github/workflows/run-eval.yml](.github/workflows/run-eval.yml)
- [openhands/resolver/examples/openhands-resolver.yml](openhands/resolver/examples/openhands-resolver.yml)
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
- [openhands/server/static.py](openhands/server/static.py)
- [tests/unit/runtime/impl/test_local_runtime.py](tests/unit/runtime/impl/test_local_runtime.py)
- [tests/unit/test_conversation_summary.py](tests/unit/test_conversation_summary.py)

</details>



This document covers OpenHands' specialized features that extend beyond basic agent operations and user interactions. These features include automated issue resolution, advanced conversation management patterns, runtime optimization techniques, file security measures, and evaluation integrations.

For core agent functionality, see [Agent System](#3). For basic user interfaces, see [Frontend & User Interfaces](#6). For development workflows, see [Development & Contributing](#8).

## Automated Issue Resolution

OpenHands provides a sophisticated GitHub Actions workflow that automatically resolves issues and pull requests using AI agents. This system can be triggered by labels, comments, or pull request reviews.

```mermaid
graph TB
    subgraph "GitHub Events"
        LABEL["Label: fix-me"]
        COMMENT["Comment: @openhands-agent"]
        REVIEW["PR Review: @openhands-agent"]
    end
    
    subgraph "Workflow Triggers"
        TRIGGER[".github/workflows/openhands-resolver.yml"]
        PARAMS["Parameters<br/>max_iterations<br/>macro<br/>target_branch<br/>LLM_MODEL"]
    end
    
    subgraph "Resolution Process"
        INSTALL["Install OpenHands<br/>experimental or stable"]
        RESOLVE["openhands.resolver.resolve_issue<br/>--issue-number<br/>--issue-type<br/>--max-iterations"]
        OUTPUT["output.jsonl<br/>resolution results"]
    end
    
    subgraph "PR Creation"
        SUCCESS{"Resolution<br/>Success?"}
        DRAFT_PR["openhands.resolver.send_pull_request<br/>--pr-type draft"]
        BRANCH["Create branch<br/>--pr-type branch"]
        COMMENT_PR["GitHub comment<br/>with results"]
    end
    
    LABEL --> TRIGGER
    COMMENT --> TRIGGER  
    REVIEW --> TRIGGER
    TRIGGER --> PARAMS
    PARAMS --> INSTALL
    INSTALL --> RESOLVE
    RESOLVE --> OUTPUT
    OUTPUT --> SUCCESS
    SUCCESS -->|Yes| DRAFT_PR
    SUCCESS -->|No| BRANCH
    DRAFT_PR --> COMMENT_PR
    BRANCH --> COMMENT_PR
```

**Workflow Configuration**

The resolver accepts multiple configuration parameters through workflow inputs and secrets:

- `max_iterations`: Maximum number of agent iterations (default: 50)
- `macro`: Trigger phrase in comments (default: "@openhands-agent")
- `LLM_MODEL`: Model to use (default: "anthropic/claude-sonnet-4-20250514")
- `base_container_image`: Custom sandbox environment
- `target_branch`: Branch to create PR against (default: "main")

**Trigger Mechanisms**

The system responds to three types of GitHub events:
1. **Label-based**: Issues/PRs labeled with `fix-me` or `fix-me-experimental`
2. **Comment-based**: Comments containing the configured macro from collaborators
3. **Review-based**: PR reviews containing the macro from authorized users

Sources: [.github/workflows/openhands-resolver.yml:1-434]()

## Advanced Conversation Management

OpenHands implements two distinct conversation management strategies depending on deployment requirements.

```mermaid
graph TB
    subgraph "ConversationManager Interface"
        IFACE["ConversationManager<br/>Abstract Base Class"]
        METHODS["attach_to_conversation()<br/>join_conversation()<br/>send_to_event_stream()<br/>close_session()"]
    end
    
    subgraph "Standalone Implementation"
        STANDALONE["StandaloneConversationManager"]
        LOCAL_LOOPS["_local_agent_loops_by_sid<br/>dict[str, Session]"]
        LOCAL_CONN["_local_connection_id_to_session_id<br/>dict[str, str]"]
        ACTIVE_CONV["_active_conversations<br/>dict[str, tuple[ServerConversation, int]]"]
        DETACHED_CONV["_detached_conversations<br/>dict[str, tuple[ServerConversation, float]]"]
    end
    
    subgraph "Docker Nested Implementation"
        DOCKER["DockerNestedConversationManager"]
        CONTAINERS["docker_client.containers.list()<br/>openhands-runtime-{sid}"]
        NESTED_API["Nested Runtime API<br/>httpx requests"]
        SESSION_KEY["_get_session_api_key_for_conversation()"]
    end
    
    IFACE --> STANDALONE
    IFACE --> DOCKER
    STANDALONE --> LOCAL_LOOPS
    STANDALONE --> LOCAL_CONN
    STANDALONE --> ACTIVE_CONV
    STANDALONE --> DETACHED_CONV
    DOCKER --> CONTAINERS
    DOCKER --> NESTED_API
    DOCKER --> SESSION_KEY
```

**Standalone Conversation Manager**

The `StandaloneConversationManager` handles conversations within a single server process. It maintains several key data structures:

- `_local_agent_loops_by_sid`: Maps session IDs to `Session` objects
- `_active_conversations`: Tracks active conversations with reference counts
- `_detached_conversations`: Manages recently disconnected conversations for reuse

Key features include automatic cleanup of stale conversations and branch tracking for Git operations.

**Docker Nested Conversation Manager**  

The `DockerNestedConversationManager` runs each conversation in its own Docker container. This approach provides better isolation but requires container orchestration:

- Each conversation runs in a container named `openhands-runtime-{sid}`
- Communication occurs through HTTP API calls to nested runtimes
- Session API keys provide authentication between parent and nested containers

Sources: [openhands/server/conversation_manager/standalone_conversation_manager.py:53-753](), [openhands/server/conversation_manager/docker_nested_conversation_manager.py:50-618]()

## Runtime System Advanced Features

The local runtime implementation includes sophisticated optimization features for improved performance and resource management.

### Warm Server Pool Management

```mermaid
graph LR
    subgraph "Server Lifecycle"
        CREATE["_create_server()<br/>ActionExecutionServerInfo"]
        WARM_POOL["_WARM_SERVERS<br/>list[ActionExecutionServerInfo]"]
        RUNNING["_RUNNING_SERVERS<br/>dict[str, ActionExecutionServerInfo]"]
    end
    
    subgraph "Server Creation Process"
        PORTS["find_available_tcp_port()<br/>execution_server_port<br/>vscode_port<br/>app_ports"]
        SUBPROCESS["subprocess.Popen<br/>action_execution_server"]
        LOG_THREAD["threading.Thread<br/>log_output()"]
    end
    
    subgraph "Environment Configuration"
        ENV_VARS["Environment Variables<br/>INITIAL_NUM_WARM_SERVERS<br/>DESIRED_NUM_WARM_SERVERS<br/>LOCAL_RUNTIME_MODE"]
        WORKSPACE["Workspace Setup<br/>tempfile.mkdtemp<br/>workspace_mount_path"]
    end
    
    CREATE --> WARM_POOL
    WARM_POOL --> RUNNING
    CREATE --> PORTS
    PORTS --> SUBPROCESS
    SUBPROCESS --> LOG_THREAD
    ENV_VARS --> CREATE
    WORKSPACE --> CREATE
```

The `LocalRuntime` maintains pools of pre-initialized servers to reduce connection latency:

**Warm Server Creation**: Background processes create ready-to-use server instances
- `INITIAL_NUM_WARM_SERVERS`: Servers created during setup
- `DESIRED_NUM_WARM_SERVERS`: Target pool size maintained during operation

**Server Reuse Logic**: When connecting to a conversation:
1. Check `_RUNNING_SERVERS` for existing server
2. Pop from `_WARM_SERVERS` if available  
3. Create new server if needed
4. Update workspace paths appropriately

**Resource Management**: Each `ActionExecutionServerInfo` tracks:
- Process handle and port assignments
- Log thread and exit event for cleanup
- Temporary workspace path
- Workspace mount configuration

Sources: [openhands/runtime/impl/local/local_runtime.py:123-568]()

## Plugin System Architecture

OpenHands supports a flexible plugin system for extending runtime capabilities with development tools.

```mermaid
graph TB
    subgraph "Plugin Interface"
        REQ["PluginRequirement<br/>@dataclass"]
        PLUGIN["Plugin<br/>initialize()<br/>run()"]
    end
    
    subgraph "VSCode Plugin"
        VSCODE_REQ["VSCodeRequirement<br/>name: 'vscode'"]
        VSCODE_PLUGIN["VSCodePlugin<br/>vscode_port<br/>vscode_connection_token<br/>gateway_process"]
        OPENVSCODE["OpenVSCode Server<br/>--host 0.0.0.0<br/>--connection-token<br/>--disable-workspace-trust"]
    end
    
    subgraph "Jupyter Plugin" 
        JUPYTER_REQ["JupyterRequirement<br/>name: 'jupyter'"]
        JUPYTER_PLUGIN["JupyterPlugin<br/>kernel_gateway_port<br/>kernel_id<br/>JupyterKernel"]
        JUPYTER_GATEWAY["Jupyter Kernel Gateway<br/>KernelGatewayApp.ip=0.0.0.0<br/>KernelGatewayApp.port"]
    end
    
    REQ --> VSCODE_REQ
    REQ --> JUPYTER_REQ
    PLUGIN --> VSCODE_PLUGIN
    PLUGIN --> JUPYTER_PLUGIN
    VSCODE_PLUGIN --> OPENVSCODE
    JUPYTER_PLUGIN --> JUPYTER_GATEWAY
```

**VSCode Plugin Implementation**

The `VSCodePlugin` provides a web-based development environment:

- Initializes OpenVSCode Server with authentication tokens
- Configures workspace settings through `.vscode/settings.json`
- Supports path-based routing with `--server-base-path` flag
- Handles platform-specific limitations (disabled on Windows)

**Jupyter Plugin Implementation**

The `JupyterPlugin` enables interactive Python execution:

- Launches Jupyter Kernel Gateway on available ports
- Manages `JupyterKernel` instances with WebSocket communication
- Supports structured output with text and image content
- Handles execution timeouts and kernel interruption

**Plugin Lifecycle**: Plugins follow a standard initialization pattern:
1. `initialize()` called with username and runtime context
2. Platform compatibility checks and port allocation
3. Subprocess management for external services
4. Connection verification and service readiness

Sources: [openhands/runtime/plugins/vscode/__init__.py:24-142](), [openhands/runtime/plugins/jupyter/__init__.py:22-173]()

## File Operations & Security

OpenHands implements comprehensive file security measures to prevent malicious uploads and path traversal attacks.

### File Upload Configuration System

```mermaid
graph TB
    subgraph "Configuration Loading"
        CONFIG["load_file_upload_config()<br/>OpenHandsConfig"]
        PARAMS["max_file_size_mb<br/>restrict_file_types<br/>allowed_extensions"]
        VALIDATION["Sanity Checks<br/>Extension normalization<br/>Default fallbacks"]
    end
    
    subgraph "Security Functions"
        SANITIZE["sanitize_filename()<br/>os.path.basename()<br/>re.sub(r'[^\\w\\-_\\.]', '')"]
        EXTENSION_CHECK["is_extension_allowed()<br/>os.path.splitext()<br/>case-insensitive"]
        UNIQUE_NAME["get_unique_filename()<br/>copy counter logic"]
    end
    
    subgraph "File Filtering"
        IGNORE_LIST["FILES_TO_IGNORE<br/>.git/, .DS_Store<br/>node_modules/<br/>__pycache__/<br/>.vscode/"]
    end
    
    CONFIG --> PARAMS
    PARAMS --> VALIDATION
    VALIDATION --> SANITIZE
    VALIDATION --> EXTENSION_CHECK
    VALIDATION --> UNIQUE_NAME
    IGNORE_LIST --> EXTENSION_CHECK
```

**Security Implementations**:

1. **Filename Sanitization**: `sanitize_filename()` removes directory traversal attempts and limits filename length
2. **Extension Validation**: `is_extension_allowed()` enforces whitelist-based file type restrictions  
3. **Unique Naming**: `get_unique_filename()` prevents overwrites with copy counter suffixes
4. **Path Safety**: Automatic filtering of sensitive directories and system files

**Configuration Options**:
- `max_file_size_mb`: Size limit enforcement (0 = unlimited)
- `restrict_file_types`: Enable/disable extension filtering
- `allowed_extensions`: Whitelist of permitted file extensions

Sources: [openhands/server/file_config.py:18-140]()

## Evaluation Integration

OpenHands integrates with external evaluation systems for automated performance testing and benchmarking.

```mermaid
graph TB
    subgraph "Trigger Events"
        PR_LABEL["PR Labels<br/>run-eval-1/2/50/100"]
        RELEASE["Release Events<br/>published"]
        MANUAL["Manual Dispatch<br/>workflow_dispatch"]
    end
    
    subgraph "Evaluation Parameters"
        BRANCH_DETECT["Branch Detection<br/>github.head_ref<br/>github.ref_name"]
        INSTANCE_COUNT["Instance Count<br/>1, 2, 50, 100"]
        REMOTE_TRIGGER["Remote API Call<br/>All-Hands-AI/evaluation"]
    end
    
    subgraph "Result Management"
        MASTER_ISSUE["MASTER_EVAL_ISSUE_NUMBER<br/>centralized results"]
        SLACK_NOTIFY["Slack Integration<br/>evaluation progress"]
        GITHUB_COMMENTS["GitHub Comments<br/>status updates"]
    end
    
    PR_LABEL --> BRANCH_DETECT
    RELEASE --> BRANCH_DETECT
    MANUAL --> BRANCH_DETECT
    BRANCH_DETECT --> INSTANCE_COUNT
    INSTANCE_COUNT --> REMOTE_TRIGGER
    REMOTE_TRIGGER --> MASTER_ISSUE
    REMOTE_TRIGGER --> SLACK_NOTIFY
    REMOTE_TRIGGER --> GITHUB_COMMENTS
```

**Evaluation Workflow Features**:

1. **Multi-trigger Support**: PR labels, releases, or manual dispatch
2. **Scalable Testing**: Configurable instance counts (1-100)
3. **Branch Flexibility**: Automatic branch detection based on trigger type
4. **Centralized Results**: Master issue for non-PR evaluations
5. **External Integration**: Remote repository dispatch for evaluation execution

**Trigger Configuration**:
- Label-based: `run-eval-{1,2,50,100}` labels on PRs
- Release-based: Automatic evaluation on published releases
- Manual: Workflow dispatch with custom parameters

Sources: [.github/workflows/run-eval.yml:1-136]()