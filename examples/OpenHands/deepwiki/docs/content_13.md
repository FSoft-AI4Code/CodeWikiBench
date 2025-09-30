7.2-Evaluation & Benchmarking

# Page: Evaluation & Benchmarking

# Evaluation & Benchmarking

<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [evaluation/benchmarks/swe_bench/README.md](evaluation/benchmarks/swe_bench/README.md)
- [evaluation/benchmarks/swe_bench/SWE-Interact.md](evaluation/benchmarks/swe_bench/SWE-Interact.md)
- [evaluation/benchmarks/swe_bench/run_infer.py](evaluation/benchmarks/swe_bench/run_infer.py)
- [evaluation/benchmarks/swe_bench/run_infer_interact.py](evaluation/benchmarks/swe_bench/run_infer_interact.py)
- [evaluation/benchmarks/swe_bench/scripts/run_infer_interact.sh](evaluation/benchmarks/swe_bench/scripts/run_infer_interact.sh)
- [evaluation/utils/shared.py](evaluation/utils/shared.py)

</details>



This page covers OpenHands' comprehensive evaluation and benchmarking framework, which provides standardized ways to measure agent performance across various software engineering tasks. The system primarily focuses on SWE-Bench integration but includes support for multiple evaluation modes and benchmarks.

For information about Git provider integrations that support evaluation workflows, see [Git Provider Integration](#7.1). For details about the runtime environments used during evaluation, see [Runtime & Execution Environment](#5).

## Core Evaluation Framework

The evaluation system is built around a standardized framework that provides consistent interfaces for running benchmarks, collecting metrics, and processing results across different evaluation scenarios.

### Evaluation Data Models

The framework uses two primary data models to structure evaluation workflows:

```mermaid
graph TD
    subgraph "Evaluation Data Models"
        EM["EvalMetadata<br/>Configuration & Setup"]
        EO["EvalOutput<br/>Results & Metrics"]
    end
    
    subgraph "EvalMetadata Components"
        AC["agent_class: str"]
        LC["llm_config: LLMConfig"]
        MI["max_iterations: int"]
        EOD["eval_output_dir: str"]
        DS["dataset: str"]
        CC["condenser_config: CondenserConfig"]
    end
    
    subgraph "EvalOutput Components"
        IID["instance_id: str"]
        TR["test_result: dict"]
        HIS["history: list[dict]"]
        MET["metrics: dict"]
        ERR["error: str | None"]
    end
    
    EM --> AC
    EM --> LC
    EM --> MI
    EM --> EOD
    EM --> DS
    EM --> CC
    
    EO --> IID
    EO --> TR
    EO --> HIS
    EO --> MET
    EO --> ERR
```

**Sources:** [evaluation/utils/shared.py:44-79]()

### Evaluation Orchestration

The core evaluation process is managed by the `run_evaluation` function, which handles parallelization, error recovery, and progress tracking:

```mermaid
graph LR
    subgraph "Dataset Preparation"
        DD["Dataset DataFrame"]
        PD["prepare_dataset()"]
        FD["Filtered Dataset"]
    end
    
    subgraph "Evaluation Execution" 
        RE["run_evaluation()"]
        PIW["_process_instance_wrapper()"]
        PIF["process_instance_func()"]
    end
    
    subgraph "Output Processing"
        UP["update_progress()"]
        OF["output.jsonl"]
        MR["Metrics & Reports"]
    end
    
    DD --> PD
    PD --> FD
    FD --> RE
    RE --> PIW
    PIW --> PIF
    PIF --> UP
    UP --> OF
    UP --> MR
    
    PIW --> PIW
```

**Sources:** [evaluation/utils/shared.py:486-550](), [evaluation/utils/shared.py:219-289]()

## SWE-Bench Integration

OpenHands provides comprehensive support for SWE-Bench evaluation, including multiple variants and modes. The system handles Docker image management, environment setup, and results processing automatically.

### Benchmark Variants Support

The evaluation system supports multiple SWE-Bench dataset variants through dynamic configuration:

```mermaid
graph TD
    subgraph "Dataset Type Detection"
        SDT["set_dataset_type()"]
        DN["Dataset Name Analysis"]
    end
    
    subgraph "Supported Variants"
        SB["SWE-bench<br/>Standard"]
        SBL["SWE-bench-Live<br/>Real Issues"]
        SBR["SWE-rebench<br/>Extended"]
        SG["SWE-Gym<br/>Interactive"]
        MM["Multimodal<br/>Visual Tasks"]
    end
    
    subgraph "Image Selection"
        GID["get_instance_docker_image()"]
        OFF["Official Images"]
        OH["OpenHands Images"]
    end
    
    SDT --> DN
    DN --> SB
    DN --> SBL 
    DN --> SBR
    DN --> SG
    DN --> MM
    
    SB --> GID
    SBL --> GID
    SBR --> GID
    SG --> GID
    MM --> GID
    
    GID --> OFF
    GID --> OH
```

**Sources:** [evaluation/benchmarks/swe_bench/run_infer.py:78-95](), [evaluation/benchmarks/swe_bench/run_infer.py:178-204]()

### Instance Processing Workflow

Each evaluation instance follows a standardized processing workflow that includes runtime initialization, agent execution, and results collection:

```mermaid
graph TD
    subgraph "Instance Setup"
        GC["get_config()"]
        CR["create_runtime()"]
        IR["initialize_runtime()"]
    end
    
    subgraph "Agent Execution"
        GI["get_instruction()"]
        RC["run_controller()"]
        MA["MessageAction"]
    end
    
    subgraph "Results Collection"
        CR2["complete_runtime()"]
        GP["Generate Git Patch"]
        GM["get_metrics()"]
        EO["EvalOutput Creation"]
    end
    
    GC --> CR
    CR --> IR
    IR --> GI
    GI --> MA
    MA --> RC
    RC --> CR2
    CR2 --> GP
    GP --> GM
    GM --> EO
```

**Sources:** [evaluation/benchmarks/swe_bench/run_infer.py:606-710](), [evaluation/benchmarks/swe_bench/run_infer.py:267-435]()

## Evaluation Modes and Variants

OpenHands supports multiple evaluation modes to assess different aspects of agent capabilities:

### Standard vs Interactive Evaluation

The system provides both standard autonomous evaluation and interactive evaluation where agents can communicate with simulated users:

```mermaid
graph LR
    subgraph "Standard Mode"
        SM["Standard Evaluation"]
        AP["Autonomous Processing"]  
        SP["Single-shot Problem Solving"]
    end
    
    subgraph "Interactive Mode"
        IM["Interactive Evaluation"]
        FU["FakeUser Simulation"]
        QA["Question-Answer Cycles"]
    end
    
    subgraph "Shared Components"
        PI["process_instance()"]
        CR["complete_runtime()"]
        RES["Results Collection"]
    end
    
    SM --> AP
    AP --> SP
    SP --> PI
    
    IM --> FU
    FU --> QA
    QA --> PI
    
    PI --> CR
    CR --> RES
```

**Sources:** [evaluation/benchmarks/swe_bench/run_infer_interact.py:48-91](), [evaluation/benchmarks/swe_bench/run_infer_interact.py:97-104]()

### SWT-Bench Test Generation Mode

For test generation evaluation, the system modifies prompts and setup to focus on creating unit tests rather than fixing issues:

| Mode | Purpose | Environment Setup | Prompt Template |
|------|---------|-------------------|-----------------|
| `swe` | Issue Resolution | Standard | `swe_default.j2` |
| `swt` | Test Generation | Standard | `swt.j2` |
| `swt-ci` | Test Gen + CI | Pre-install deps | `swt.j2` + test commands |

**Sources:** [evaluation/benchmarks/swe_bench/run_infer.py:109-151](), [evaluation/benchmarks/swe_bench/run_infer.py:395-418]()

## Configuration and Customization

The evaluation system provides extensive configuration options through environment variables, TOML files, and command-line arguments.

### Environment Configuration

Key environment variables control evaluation behavior:

```mermaid
graph TD
    subgraph "Core Settings"
        RT["RUNTIME<br/>docker|remote"]
        IEM["ITERATIVE_EVAL_MODE<br/>true|false"]
        WB["RUN_WITH_BROWSING<br/>true|false"]
    end
    
    subgraph "Memory Management"
        EC["EVAL_CONDENSER<br/>Config Name"]
        CC["CondenserConfig<br/>Memory Optimization"]
    end
    
    subgraph "Error Handling"  
        ESME["EVAL_SKIP_MAXIMUM_RETRIES_EXCEEDED<br/>true|false"]
        MRE["maximum_retries_exceeded.jsonl<br/>Failed Instances Log"]
    end
    
    subgraph "Remote Runtime"
        AAK["ALLHANDS_API_KEY"]
        SRA["SANDBOX_REMOTE_RUNTIME_API_URL"]
        EDP["EVAL_DOCKER_IMAGE_PREFIX"]
    end
    
    RT --> CC
    IEM --> ESME
    WB --> EC
    EC --> CC
    ESME --> MRE
    
    AAK --> SRA
    SRA --> EDP
```

**Sources:** [evaluation/benchmarks/swe_bench/run_infer.py:69-71](), [evaluation/utils/shared.py:440-453]()

### Instance Filtering and Selection

Evaluations can be customized through TOML configuration files to run on specific subsets:

```mermaid
graph TD
    subgraph "Selection Methods"
        CT["config.toml"]
        SI["selected_ids<br/>Specific Instances"]
        SR["selected_repos<br/>Repository Filter"]
        SK["SKIP_IDS<br/>Environment Variable"]
    end
    
    subgraph "Dataset Processing"
        FD["filter_dataset()"]
        PD["prepare_dataset()"]
        RD["Reduced Dataset"]
    end
    
    CT --> SI
    CT --> SR
    SK --> FD
    SI --> FD
    SR --> FD
    FD --> PD
    PD --> RD
```

**Sources:** [evaluation/benchmarks/swe_bench/run_infer.py:713-744](), [evaluation/utils/shared.py:219-289]()

## Results Processing and Metrics

The evaluation framework captures comprehensive metrics and produces structured outputs for analysis and comparison.

### Metrics Collection

Multiple metric sources are combined to provide comprehensive evaluation data:

```mermaid
graph TD
    subgraph "Metrics Sources"
        CS["ConversationStats<br/>Primary Source"]  
        SM["state.metrics<br/>Legacy Fallback"]
        CM["Condensation Metadata<br/>Memory Usage"]
    end
    
    subgraph "Metrics Processing"
        GM["get_metrics()"]
        CMB["Combined Metrics"]
        GCM["get_condensation_metadata()"]
    end
    
    subgraph "Output Formats"
        EO["EvalOutput.metrics"]
        JSON["output.jsonl"]
        REP["report.json"]
    end
    
    CS --> GM
    SM --> GM
    GM --> CMB
    CMB --> GCM
    GCM --> CM
    
    GM --> EO
    EO --> JSON
    JSON --> REP
```

**Sources:** [evaluation/utils/shared.py:670-689](), [evaluation/utils/shared.py:59-79]()

### Output Structure and Formats

Evaluation results are structured consistently across all benchmark types:

| Field | Type | Description |
|-------|------|-------------|
| `instance_id` | string | Unique identifier for the task |
| `instruction` | string | Original problem statement |
| `test_result` | object | Benchmark-specific results (e.g., git_patch) |
| `history` | array | Complete interaction history |
| `metrics` | object | Performance and usage metrics |
| `error` | string | Error message if evaluation failed |
| `metadata` | object | Configuration and environment details |

**Sources:** [evaluation/utils/shared.py:59-79]()