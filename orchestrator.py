import operator
import os
import sqlite3
from typing import Annotated, Literal, TypedDict
from langchain_core.messages import AIMessage, AnyMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph


# =====================================================================
# 1. STATE & PYDANTIC CONTRACTS
# =====================================================================
class ConversationalState(TypedDict):
    session_id: str
    raw_query: str
    classified_intent: Literal["FAQ", "VENDOR_TECH", "HIGH_RISK_SECURITY"]
    vendor_context_payload: dict
    human_escalation_required: bool
    execution_trail: Annotated[list[AnyMessage], operator.add]


# Pydantic schema forced onto Gemini's output generation
class IntentClassification(BaseModel):
    intent: Literal["FAQ", "VENDOR_TECH", "HIGH_RISK_SECURITY"] = Field(
        description="The strictly classified intent category of the user query."
    )


# =====================================================================
# 2. WORKER THREADS (Graph Nodes)
# =====================================================================
def intent_router_node(state: ConversationalState):
    """Real LLM inference gateway using Gemini 3.5 Flash."""
    
    # temperature=0 ensures deterministic, non-creative categorization
    llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0)
    
    # Force Gemini to conform strictly to the Pydantic schema
    structured_llm = llm.with_structured_output(IntentClassification)

    system_prompt = """You are the inbound Intent Multiplexer for Coinbase customer support.
    Analyze the user query and map it strictly to one of these three categories:
    - HIGH_RISK_SECURITY: Hacked accounts, unauthorized logins, drained wallets, stolen funds.
    - VENDOR_TECH: API timeouts, platform bugs, WebSocket latency, 504 gateway errors.
    - FAQ: General questions, fee structures, basic password resets, standard trading rules."""

    decision = structured_llm.invoke([
        ("system", system_prompt),
        ("human", state["raw_query"])
    ])

    classified = decision.intent
    log = AIMessage(content=f"[GEMINI-3.5 INFERENCE] Query explicitly routed to: {classified}")
    
    return {"classified_intent": classified, "execution_trail": [log]}


def faq_retrieval_node(state: ConversationalState):
    res = AIMessage(content="[RAG SERVICE] Document hit: /docs/security/2fa-reset-protocol.md")
    return {"execution_trail": [res]}


def vendor_api_dispatch_node(state: ConversationalState):
    payload = {"vendor_id": "AUTH_PARTNER_09", "err_code": "SOCKET_TIMEOUT_504", "priority": "P1_CRITICAL"}
    log = AIMessage(content=f"[VENDOR DISPATCH] Context packaged for API: {payload['err_code']}")
    return {"vendor_context_payload": payload, "execution_trail": [log]}


def human_staging_node(state: ConversationalState):
    log = AIMessage(content="[COMPLIANCE OFFICER] State manually validated. Authorizing downstream lock freeze.")
    return {"human_escalation_required": True, "execution_trail": [log]}


def final_gateway_node(state: ConversationalState):
    log = AIMessage(content="[ORCHESTRATOR] Session transaction committed cleanly.")
    return {"execution_trail": [log]}


# =====================================================================
# 3. MUX ROUTING EDGE
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
    thread_config = {"configurable": {"thread_id": "tx_live_gemini_01"}}
    
    inbound_payload = {
        "session_id": "tx_live_gemini_01",
        "raw_query": "I woke up and my account balance says $0.00. I didn't authorize any transfers!",
        "human_escalation_required": False
    }

    print("\n" + "="*65)
    print(" [INBOUND STREAM] DISPATCHING RAW STRING TO GEMINI API...")
    print("="*65)

    for event in omni_graph.stream(inbound_payload, config=thread_config):
        for node_name, state_update in event.items():
            print(f"  ├── [GRAPH NODE EXECUTED] : {node_name}")
            if node_name == "intent_router_node":
                print(f"  │    └── Resulting State: {state_update['classified_intent']}")

    pending_state = omni_graph.get_state(thread_config)
    
    if pending_state.next:
        print("\n" + "!"*65)
        print(f" [SYSTEM THREAD HALTED] : interrupt_before hit on -> {pending_state.next}")
        print("!"*65)
        
        auth = input("\n [CX COMPLIANCE TERMINAL] Authorize state release? (Type 'APPROVE'): ")
        if auth.strip().upper() == "APPROVE":
            for event in omni_graph.stream(None, config=thread_config):
                for node_name, _ in event.items():
                    print(f"  ├── [GRAPH NODE EXECUTED] : {node_name}")
            print("\n *** [TRANSACTION CLOSED CLEANLY] ***\n")