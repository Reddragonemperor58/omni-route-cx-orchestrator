import operator
import sqlite3
from typing import Annotated, Literal, TypedDict
from langchain_core.messages import AIMessage, AnyMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph


# =====================================================================
# 1. STATE CONTRACT (The C++ Struct equivalent)
# =====================================================================
class ConversationalState(TypedDict):
    session_id: str
    raw_query: str
    classified_intent: Literal["FAQ", "VENDOR_TECH", "HIGH_RISK_SECURITY"]
    vendor_context_payload: dict
    human_escalation_required: bool
    # Reducer: append-only memory buffer
    execution_trail: Annotated[list[AnyMessage], operator.add]


# =====================================================================
# 2. WORKER THREADS (Graph Nodes)
# =====================================================================
def intent_router_node(state: ConversationalState):
    """Zero-shot intent classification gateway."""
    query = state["raw_query"].lower()

    if any(w in query for w in ["stolen", "hack", "fraud", "drained", "unauthorized"]):
        intent = "HIGH_RISK_SECURITY"
    elif any(w in query for w in ["api", "bug", "vendor", "timeout", "latency"]):
        intent = "VENDOR_TECH"
    else:
        intent = "FAQ"

    log = AIMessage(content=f"[ROUTER GATEWAY] Intent explicitly bound to: {intent}")
    return {"classified_intent": intent, "execution_trail": [log]}


def faq_retrieval_node(state: ConversationalState):
    """Deterministic Help-Center RAG retrieval."""
    res = AIMessage(content="[RAG SERVICE] Document hit: /docs/security/2fa-reset-protocol.md")
    return {"execution_trail": [res]}


def vendor_api_dispatch_node(state: ConversationalState):
    """Simulates building a secure payload for a 3rd-party vendor."""
    payload = {
        "vendor_id": "AUTH_PARTNER_09",
        "err_code": "SOCKET_TIMEOUT_504",
        "priority": "P1_CRITICAL"
    }
    log = AIMessage(content=f"[VENDOR DISPATCH] Context packaged for API: {payload['err_code']}")
    return {"vendor_context_payload": payload, "execution_trail": [log]}


def human_staging_node(state: ConversationalState):
    """
    *** HARDWARE INTERRUPT TARGET ***
    Graph execution will be suspended strictly BEFORE entering this scope.
    """
    log = AIMessage(content="[COMPLIANCE OFFICER] State manually validated. Authorizing downstream lock freeze.")
    return {"human_escalation_required": True, "execution_trail": [log]}


def final_gateway_node(state: ConversationalState):
    """Synchronous collection point."""
    log = AIMessage(content="[ORCHESTRATOR] Session transaction committed cleanly.")
    return {"execution_trail": [log]}


# =====================================================================
# 3. HARDWARE MUX (Conditional Routing Edge)
# =====================================================================
def mux_routing_logic(state: ConversationalState) -> str:
    intent = state.get("classified_intent")

    if intent == "FAQ":
        return "faq_retrieval_node"
    elif intent == "VENDOR_TECH":
        return "vendor_api_dispatch_node"
    elif intent == "HIGH_RISK_SECURITY":
        return "human_staging_node"

    return "faq_retrieval_node"


# =====================================================================
# 4. COMPILER & CHECKPOINTER LINKAGE
# =====================================================================
builder = StateGraph(ConversationalState)

builder.add_node("intent_router_node", intent_router_node)
builder.add_node("faq_retrieval_node", faq_retrieval_node)
builder.add_node("vendor_api_dispatch_node", vendor_api_dispatch_node)
builder.add_node("human_staging_node", human_staging_node)
builder.add_node("final_gateway_node", final_gateway_node)

builder.add_edge(START, "intent_router_node")
builder.add_conditional_edges("intent_router_node", mux_routing_logic)

builder.add_edge("faq_retrieval_node", "final_gateway_node")
builder.add_edge("vendor_api_dispatch_node", "final_gateway_node")
builder.add_edge("human_staging_node", "final_gateway_node")
builder.add_edge("final_gateway_node", END)

# Attach local disk checkpointer
conn = sqlite3.connect("cx_telemetry.sqlite", check_same_thread=False)
memory_checkpointer = SqliteSaver(conn)

omni_graph = builder.compile(
    checkpointer=memory_checkpointer,
    interrupt_before=["human_staging_node"],
)


# =====================================================================
# 5. LOCAL RUNTIME SIMULATOR
# =====================================================================
if __name__ == "__main__":
    thread_config = {"configurable": {"thread_id": "tx_session_8821"}}
    
    inbound_payload = {
        "session_id": "tx_session_8821",
        "raw_query": "EMERGENCY: Someone logged in from Moscow and drained my Ethereum wallet!",
        "human_escalation_required": False
    }

    print("\n" + "="*65)
    print(" [INBOUND STREAM] INGESTING USER SESSION TOKEN...")
    print("="*65)

    for event in omni_graph.stream(inbound_payload, config=thread_config):
        for node_name, _ in event.items():
            print(f"  ├── [GRAPH NODE EXECUTED] : {node_name}")

    print("\n" + "!"*65)
    print(" [SYSTEM THREAD HALTED] : interrupt_before triggered")
    print(" [MEMORY FLUSHED]       : State serialized to ./cx_telemetry.sqlite")
    print("!"*65)

    pending_state = omni_graph.get_state(thread_config)
    print(f"  └── [*] Next Scheduled Instruction : {pending_state.next}")

    auth = input("\n [CX COMPLIANCE TERMINAL] Fraud detected. Type 'APPROVE' to release state lock: ")

    if auth.strip().upper() == "APPROVE":
        print("\n" + "="*65)
        print(" [LOCK RELEASED] RE-HYDRATING STATE FROM SQLITE...")
        print("="*65)
        for event in omni_graph.stream(None, config=thread_config):
            for node_name, _ in event.items():
                print(f"  ├── [GRAPH NODE EXECUTED] : {node_name}")
        print("\n *** [TRANSACTION CLOSED CLEANLY] ***\n")
    else:
        print("\n [ABORTED] State remains frozen on disk.\n")