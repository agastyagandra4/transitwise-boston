# TransitWise Boston: Architecture

## System architecture

```mermaid
flowchart TD
    API["MBTA V3 API"]
    DOCS["Accessibility policy PDFs"]
    LOAD["Reference loads and alert pipeline"]
    INDEX["Chunk and embed documents"]
    SF[("Snowflake: RAW and RAG")]
    USER["User input / notebook"]
    REPLAN["Replanner: coordinate trip"]
    PLAN["Planner: calculate route"]
    CHECK["Checker: check accessibility"]
    RET["Retriever: find policy guidance"]
    LLM["LLM: explain options"]
    OUT["Route and explanation"]

    API --> LOAD --> SF
    DOCS --> INDEX --> SF
    USER --> REPLAN
    REPLAN -->|"plan or retry"| PLAN
    SF -->|"routes and stations"| PLAN
    PLAN -->|"route"| REPLAN
    REPLAN -->|"check route"| CHECK
    API -->|"live alerts"| CHECK
    CHECK -->|"issues or clear route"| REPLAN
    REPLAN -->|"blocked trip"| RET
    SF -->|"policy passages"| RET
    RET -->|"relevant context"| LLM
    REPLAN -->|"route and issues"| LLM
    LLM -->|"validate answer"| OUT
    REPLAN -->|"clear route, fallback or error"| OUT