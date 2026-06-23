# Omni-Route: Hybrid CX Multi-Agent Orchestrator (PoC)

> [!IMPORTANT]  
> **STATUS: ACTIVE R&D ENGINEERING SPIKE**  
> *Specification Authored: June 23, 2026 | Scheduled Code Freeze: June 28, 2026*

---

## Executive Summary

This repository houses an explicitly time-boxed R&D engineering spike designed to evaluate stateful intent-routing across hybrid (**Internal Micro-Agents** + **3rd-Party Vendor AI**) LLM boundaries. 

The primary architectural objective is to validate `LangGraph`'s `interrupt_before` graph-freezing primitives to guarantee **zero-hallucination, secure Human-in-the-Loop (HITL) handoffs** for Tier-1 financial customer support escalations.

## Architectural Blueprint (In-Progress)

```text
[ Incoming User Token Stream ] 
             │
             v
    ┌─────────────────┐
    │  Intent Router  │ (Zero-Shot Classifier)
    └────────┬────────┘
             │
     ┌───────┼─────────────────────────┐
     │ (FAQ) │ (Tech)                  │ (High-Risk / Fraud)
     v       v                         v
  ┌─────┐ ┌────────────┐     ┌───────────────────┐
  │ RAG │ │ Vendor API │     │ interrupt_before  │ <--- [ GRAPH FREEZE ]
  └─────┘ └────────────┘     └─────────┬─────────┘
                                       │
                                       v
                             [ SQLite Checkpoint ]
                                       │
                              ( Human CX Override )
                                       │
                                       v
                            [ Synchronous Handoff ]
```

## Core State Schema (`TypedDict`)

The graph passes a strictly typed, validated dictionary across all node boundaries:

```python
from typing import TypedDict, Literal, Annotated
import operator

class ConversationalState(TypedDict):
    user_id: str
    session_id: str
    raw_query: str
    classified_intent: Literal["FAQ", "VENDOR_TECH", "HIGH_RISK_SECURITY"]
    vendor_context_payload: dict
    human_escalation_required: bool
    execution_trail: Annotated[list, operator.add]
```

## Implementation Milestones (Sprint 26.2)

- [x] **Phase 1 (June 23):** Define architectural boundaries, state schema contracts, and SQLite checkpointer interface.
- [ ] **Phase 2 (June 26):** Stand up LangGraph router node and vendor API tool-calling mocks.
- [ ] **Phase 3 (June 27):** Wire `interrupt_before` thread-locking and human CLI approval override.
- [ ] **Phase 4 (June 28):** Attach LangSmith tracing telemetry and publish live execution graph URLs.

> [!NOTE]  
> *Live LangSmith telemetry links will populate in this section upon the completion of Phase 4.*
