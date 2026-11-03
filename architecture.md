 # TransitWise Boston: Architecture

## System architecture

```mermaid
flowchart TD
    API[MBTA V3 API<br/>Alerts, routes, stops, facilities]
    DOCS[MBTA policy PDFs<br/>Accessibility, shuttles, The RIDE]
    PIPE[Alert pipeline<br/>pipeline/load_alerts.py on GitHub Actions]
    RAGSETUP[RAG setup<br/>rag_setup.ipynb: chunk + embed]
    SF[(Snowflake<br/>RAW, CLEAN, RAG schemas)]
    PLAN[Planner<br/>agents/planner.py]
    CHECK[Checker<br/>agents/checker.py]
    RET[Retriever<br/>agents/retriever.py]
    REPLAN[Replanner<br/>agents/replanner.py]
    LLM[Claude API<br/>agents/llm.py]
    MON[Monitor<br/>agents/monitor.py]
    MCP[MCP server<br/>mcp_server.py]

    API --> PIPE --> SF
    DOCS --> RAGSETUP --> SF
    SF --> PLAN --> CHECK
    API -. live alerts .-> CHECK
    CHECK -- blocked --> REPLAN
    SF --> RET --> REPLAN
    REPLAN --> LLM
    MON --> CHECK
    MON --> REPLAN
    PLAN --> MCP
    CHECK --> MCP
    RET --> MCP
```

## Data architecture

| Layer | Components |
|---|---|
| Sources | MBTA V3 API; MBTA policy PDFs in `policy_docs/` |
| Ingestion | `pipeline/load_alerts.py` (scheduled on GitHub Actions); one-time loads for reference tables; `rag_setup.ipynb` for policy chunks |
| Storage | Snowflake `TRANSITWISE_DB`: `RAW` (as loaded), `CLEAN` (SQL views), `RAG` (policy chunks with embeddings) |
| Consumption | Planner, Checker, Retriever, Replanner, Monitor; MCP tools |