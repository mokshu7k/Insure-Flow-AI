"""
InsureFlow Customer AI Agent � 3-node LangGraph pipeline.

Architecture:
  START
    +-> supervisor_node   (reads sliding-window memory, decides route)
          +- route="data_node"    --> data_node (calls DB tools) --> synthesizer_node --> END
          +- route="synthesizer"  --------------------------------> synthesizer_node --> END

Nodes:
  1. supervisor_node
     - Receives last 5 messages (sliding window) as context.
     - Uses Gemini in JSON mode to decide:
         a) Does this query require live DB data?
         b) If yes, which tools / data might help?
     - Sets state["route"] and state["supervisor_notes"].

  2. data_node
     - Has access to 8 ownership-scoped DB tools (claims, documents,
       fraud, settlements, consent, timeline, summary).
     - Gemini picks whichever tools answer the query (can call multiple).
     - Accumulated results stored in state["data_context"].

  3. synthesizer_node
     - Has deep knowledge of the InsureFlow platform (injected via system prompt).
     - Combines conversation history + data_context into a polished customer reply.
     - Final output is a plain AIMessage added to state["messages"].
"""
from __future__ import annotations

import json
import logging
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from app.ai_agents.agent.state import AgentState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Platform context (shared across supervisor + synthesizer)
# ---------------------------------------------------------------------------
PLATFORM_CONTEXT = """
## About InsureFlow AI Platform

InsureFlow is an AI-powered insurance claims management platform built for Indian customers.

### What customers can do
- **Submit claims** for medical, vehicle, property, and life insurance.
- **Upload supporting documents** (hospital bills, FIR copies, repair estimates, death certificates, etc.)
  which are OCR-processed and verified by Gemini AI.
- **Track claim status** in real-time through the portal.
- **View fraud assessment results** � every claim is automatically scored for fraud risk.
- **Check settlement details** once a claim is approved and payment is initiated.

### Claim lifecycle
SUBMITTED -> UNDER_REVIEW -> (APPROVED | REJECTED) -> SETTLED

- **SUBMITTED**: Customer has filed the claim; documents may still be pending.
- **UNDER_REVIEW**: AI fraud analysis and document verification are running or complete;
  a human adjuster may be reviewing the case.
- **APPROVED**: Claim accepted; settlement will be initiated.
- **REJECTED**: Claim denied; explanation available via fraud/verification report.
- **SETTLED**: Payment has been processed; reference number available.

### Fraud assessment
- Every claim gets a fraud score from 0.0 (clean) to 1.0 (highly suspicious).
- Risk levels: LOW (<0.40), MEDIUM (0.40-0.69), HIGH (0.70-0.84), VERY_HIGH (>=0.85).
- Multi-layer AI: deterministic rules + statistical signals + behavioral analysis
  + document cross-check + network analysis.
- A HIGH or VERY_HIGH score does NOT automatically reject a claim � a human adjuster
  reviews flagged cases. Customers should not panic if they see a flag.

### Documents
- Accepted types: medical bills, FIR copies, vehicle repair estimates, discharge summaries,
  death certificates, policy documents, photographs of damage, and more.
- Gemini extracts structured data (dates, amounts, hospital names, etc.) and
  cross-checks against the claim details. Discrepancies may trigger manual review.

### Settlements
- After approval, a settlement is created with a unique reference number.
- Status: PROCESSING -> COMPLETED.
- Payments are made via NEFT/IMPS to the registered bank account.
- Typical settlement timeline: 3-7 business days after approval.

### Consent
- InsureFlow must have a valid data-processing consent record (version 1.0) from the
  customer before processing sensitive data. This is collected during onboarding.

### Currency
- All amounts are in Indian Rupees (INR). Always format as Rs.X,XX,XXX.XX (e.g. Rs.1,20,000.00). Never use the rupee symbol.

### Tone guidelines
- Be warm, empathetic, and professional.
- Keep responses concise but complete.
- If data is missing or the claim is not found, explain clearly and suggest next steps.
- Never speculate beyond what the data shows.
"""

# ---------------------------------------------------------------------------
# Supervisor prompt
# ---------------------------------------------------------------------------
SUPERVISOR_PROMPT = f"""You are the Supervisor of the InsureFlow AI customer assistant.

Your ONLY job is to decide how to route the customer's latest message.
You do NOT answer the customer yourself.

{PLATFORM_CONTEXT}

## Routing Decision

Respond with ONLY a JSON object (no markdown, no explanation):

{{
  "route": "data_node" | "synthesizer",
  "reason": "<one sentence>",
  "likely_tools": ["tool1", "tool2"]   // empty if route=synthesizer
}}

## Available tools (for hints only � data_node will call them autonomously)
- list_my_claims         : List the user's recent claims
- get_claim_details      : Full info on a specific claim (needs claim_id)
- get_claim_documents    : Documents uploaded for a claim (needs claim_id)
- get_fraud_assessment   : Fraud score + explanation for a claim (needs claim_id)
- get_settlement_info    : Settlement amount + status (needs claim_id)
- get_claims_summary     : Aggregate stats (totals, by status/type)
- check_consent          : Check if user has given consent
- get_claim_timeline     : Chronological event timeline for a claim (needs claim_id)

## When to route to "data_node"
- User asks about any specific claim (status, amount, documents, fraud, settlement)
- User wants a list or overview of all their claims
- User asks about payment or settlement
- User asks about why a claim is flagged or rejected
- User wants a timeline or history of a claim
- Anything that requires looking up live database information

## When to route to "synthesizer" (skip data_node)
- Pure greetings or pleasantries ("hi", "thank you", "bye")
- General questions about how insurance works (not specific to their account)
- Questions about the platform itself (how to submit, what documents to upload)
- Follow-up messages clarifying something already answered in the conversation
- The conversation already has enough data_context to answer without new DB calls
"""

# ---------------------------------------------------------------------------
# Synthesizer prompt
# ---------------------------------------------------------------------------
SYNTHESIZER_PROMPT = f"""You are InsureFlow AI, a helpful and empathetic insurance claims assistant.

{PLATFORM_CONTEXT}

YOUR ROLE
You synthesize conversation history and real-time database data into a clear, helpful
plain-text response for the customer.

════════════════════════════════════════
CRITICAL FORMATTING RULES
════════════════════════════════════════

The chat UI renders your reply as PLAIN TEXT with whitespace preserved (pre-wrap).
There is NO markdown renderer. Follow these rules exactly:

  1. NO markdown ever.
     Bad:  **Status:** APPROVED   ## Your Claims   - item   | col |
     Good: Status: APPROVED       YOUR CLAIMS      • item   (use column spacing)

  2. Use ALL CAPS for section headings, followed by a blank line.
     Example:
       YOUR RECENT CLAIMS

       • Claim #abc123 ...

  3. Use these unicode bullets for lists:
     •  general items
     →  steps / actions the user should take
     ✓  positive / approved / complete
     ✗  negative / rejected / flagged

  4. Separate sections with a blank line (one empty line between sections).
     Do NOT use --- or === or *** as dividers.

  5. For claim lists, use aligned plain-text columns:
     #  Type       Status        Amount
     1. Health     APPROVED      Rs.45,000
     2. Vehicle    UNDER_REVIEW  Rs.1,20,000

  6. For single claim details, use label: value on separate lines:
     Claim ID:    abc-123-def
     Type:        Health
     Status:      UNDER_REVIEW
     Amount:      Rs.45,000.00
     Submitted:   2026-01-15
     Last update: 2026-02-10

  7. Currency: always write as Rs.X,XX,XXX.XX (e.g. Rs.1,20,000.00)

  8. Keep responses SHORT. 3-8 lines for simple answers.
     For data-heavy answers (claim list, timeline), use the column format above.

  9. If a claim is REJECTED or HIGH fraud risk, stay calm and empathetic.
     End with a clear next step.
     Example:
       Your claim was not approved due to [reason].

       → Contact our support team to appeal or provide additional documents.
       → Email: support@insureflow.in
       → Call:  1800-100-0110 (Mon-Sat, 9am-6pm)

  10. Never make up data. Only state facts from the conversation or fetched data.
      If a claim ID is needed but not provided, ask for it politely.

════════════════════════════════════════
FORMAT EXAMPLES
════════════════════════════════════════

Example — greeting:
  Hello! I'm your InsureFlow assistant.
  I can help you check claim status, view documents, understand fraud flags, or
  track settlements. What would you like to know?

Example — claims list:
  YOUR RECENT CLAIMS

  #  Type     Status        Amount
  1. Health   APPROVED      Rs.45,000.00
  2. Vehicle  UNDER_REVIEW  Rs.1,20,000.00
  3. Health   SUBMITTED     Rs.8,500.00

  To see details on any claim, share the claim number and I'll pull it up.

Example — claim status:
  CLAIM DETAILS

  Claim ID:    a1b2c3d4-...
  Type:        Health Insurance
  Status:      ✓ APPROVED
  Amount:      Rs.45,000.00
  Policy:      POL-2024-001
  Submitted:   15 Jan 2026
  Last update: 18 Feb 2026

  Your claim has been approved. Settlement will be initiated within 3-7 business days.

Example — fraud flag (calm tone):
  FRAUD ASSESSMENT

  Risk level:  MEDIUM (score 0.52)
  Status:      Under review by adjuster

  A medium risk flag means our system found some signals that need manual verification.
  This does not mean your claim is rejected — an adjuster is reviewing it.

  → If you have additional supporting documents, you can upload them via the portal.
  → For questions, contact support@insureflow.in

"""

# ---------------------------------------------------------------------------
# Helper: extract plain string from LangChain message content
# ---------------------------------------------------------------------------
def _content_str(content: Any) -> str:
    """Normalise Gemini content (may be str or list-of-blocks) to plain string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            else:
                parts.append(str(block))
        return " ".join(p for p in parts if p)
    return str(content) if content is not None else ""


# ---------------------------------------------------------------------------
# Helper: get the Gemini LLM (optionally with tools bound)
# ---------------------------------------------------------------------------
def _get_llm(tools: list | None = None, temperature: float = 0.3):
    from langchain_google_genai import ChatGoogleGenerativeAI
    from app.config import settings

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GCP_API_KEY,
        temperature=temperature,
    )
    if tools:
        return llm.bind_tools(tools)
    return llm


# ---------------------------------------------------------------------------
# Helper: build LangChain @tool wrappers bound to this request's db/user_id
# ---------------------------------------------------------------------------
def _build_data_tools(db, user_id: str) -> list:
    from langchain_core.tools import tool

    @tool
    async def list_my_claims() -> str:
        """List the user's most recent insurance claims with status, type, and amount."""
        from app.ai_agents.agent.tools import list_user_claims as _fn
        return json.dumps(await _fn(db=db, user_id=user_id))

    @tool
    async def get_claim_details(claim_id: str) -> str:
        """Get full details for a specific insurance claim by its UUID claim_id."""
        from app.ai_agents.agent.tools import get_claim_status as _fn
        return json.dumps(await _fn(claim_id, db=db, user_id=user_id))

    @tool
    async def get_claim_documents(claim_id: str) -> str:
        """Get all uploaded documents and their OCR-extracted data for a specific claim."""
        from app.ai_agents.agent.tools import get_claim_documents as _fn
        return json.dumps(await _fn(claim_id, db=db, user_id=user_id))

    @tool
    async def get_fraud_assessment(claim_id: str) -> str:
        """Get the fraud risk score, risk level, and AI explanation for a specific claim."""
        from app.ai_agents.agent.tools import get_fraud_explanation as _fn
        return json.dumps(await _fn(claim_id, db=db, user_id=user_id))

    @tool
    async def get_settlement_info(claim_id: str) -> str:
        """Get settlement amount, status, and reference number for a specific claim."""
        from app.ai_agents.agent.tools import get_settlement_info as _fn
        return json.dumps(await _fn(claim_id, db=db, user_id=user_id))

    @tool
    async def get_claims_summary() -> str:
        """Get aggregate statistics across all the user's claims: totals, by status, by type."""
        from app.ai_agents.agent.tools import get_claims_summary as _fn
        return json.dumps(await _fn(db=db, user_id=user_id))

    @tool
    async def check_consent() -> str:
        """Check whether the user has given valid data-processing consent."""
        from app.ai_agents.agent.tools import check_consent_status as _fn
        return json.dumps(await _fn(db=db, user_id=user_id))

    @tool
    async def get_claim_timeline(claim_id: str) -> str:
        """Get a chronological event timeline for a specific claim: submission, documents, fraud, settlement."""
        from app.ai_agents.agent.tools import get_claim_timeline as _fn
        return json.dumps(await _fn(claim_id, db=db, user_id=user_id))

    return [
        list_my_claims,
        get_claim_details,
        get_claim_documents,
        get_fraud_assessment,
        get_settlement_info,
        get_claims_summary,
        check_consent,
        get_claim_timeline,
    ]


# ---------------------------------------------------------------------------
# Node 1: supervisor_node
# ---------------------------------------------------------------------------
async def supervisor_node(state: AgentState) -> dict:
    """
    Reads the last 5 messages (sliding window), then asks Gemini to decide:
    - Should we fetch live DB data first? (route = "data_node")
    - Or can the synthesizer answer directly? (route = "synthesizer")
    Sets state["route"] and state["supervisor_notes"].
    """
    # Sliding window: last 10 messages = ~5 exchanges
    recent_messages = list(state["messages"])[-10:]

    # Format recent history as plain text for the supervisor
    history_text = ""
    for m in recent_messages:
        role = getattr(m, "type", "human")
        content = _content_str(getattr(m, "content", ""))
        if role in ("human",):
            history_text += f"Customer: {content}\n"
        elif role in ("ai", "assistant"):
            history_text += f"Assistant: {content}\n"

    supervision_input = f"""## Recent conversation (last 5 exchanges)

{history_text.strip() or "(no prior conversation)"}

## Latest customer message
{_content_str(recent_messages[-1].content) if recent_messages else "(none)"}

Now output your routing JSON.
"""

    try:
        llm = _get_llm(temperature=0.1)
        messages = [
            SystemMessage(content=SUPERVISOR_PROMPT),
            HumanMessage(content=supervision_input),
        ]
        response: AIMessage = await llm.ainvoke(messages)
        raw = _content_str(response.content).strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        decision = json.loads(raw)
        route = decision.get("route", "data_node")
        notes = decision.get("reason", "")
        if route not in ("data_node", "synthesizer"):
            route = "data_node"

        logger.info("Supervisor routed to '%s': %s", route, notes)
        return {
            "route": route,
            "supervisor_notes": notes,
            "intent": f"supervisor:{route}",
        }
    except Exception as exc:
        logger.warning("Supervisor parse error (%s) � defaulting to data_node", exc)
        return {
            "route": "data_node",
            "supervisor_notes": "Routing defaulted due to parse error.",
            "intent": "supervisor:default",
        }


# ---------------------------------------------------------------------------
# Node 2: data_node
# ---------------------------------------------------------------------------
async def data_node(state: AgentState) -> dict:
    """
    Calls the appropriate DB tools to answer the customer's query.
    Gemini decides autonomously which tools to invoke (can call multiple).
    Accumulated results are stored in state["data_context"].
    """
    db_factory = state["context"].get("db_factory")
    user_id = state["user_id"]

    if db_factory is None:
        logger.error("data_node: no db_factory in state context — cannot call tools")
        return {"data_context": {}, "intent": "data_error"}

    # Last 10 messages for context
    recent_messages = list(state["messages"])[-10:]
    supervisor_hint = state.get("supervisor_notes", "")

    data_system = f"""You are the Data Retrieval layer of InsureFlow AI.

Your ONLY job is to call the correct tools to fetch data the customer needs.
Do NOT compose a reply — just call the tools and let the synthesizer do that.

{PLATFORM_CONTEXT}

Supervisor hint: {supervisor_hint}

Call as many tools as needed. If a claim_id is needed but not in the conversation,
call list_my_claims first so the synthesizer knows which claims exist.
"""

    # Open a dedicated session scoped to this entire node so the db connection
    # stays alive for all tool calls. This is isolated from the request session.
    try:
        async with db_factory() as db:
            tools = _build_data_tools(db, user_id)
            tool_map = {t.name: t for t in tools}

            llm_with_tools = _get_llm(tools, temperature=0.1)
            messages = [SystemMessage(content=data_system)] + recent_messages

            response: AIMessage = await llm_with_tools.ainvoke(messages)

            accumulated: dict[str, Any] = state.get("data_context") or {}

            if response.tool_calls:
                tool_results = []
                for tc in response.tool_calls:
                    tool_fn = tool_map.get(tc["name"])
                    if tool_fn:
                        try:
                            tool_output = await tool_fn.ainvoke(tc["args"])
                        except Exception as e:
                            logger.error("data_node tool '%s' raised exception: %s", tc["name"], e, exc_info=True)
                            tool_output = json.dumps({"error": str(e)})
                    else:
                        logger.error("data_node: unknown tool requested: %s", tc["name"])
                        tool_output = json.dumps({"error": f"Unknown tool: {tc['name']}"})

                    try:
                        parsed = json.loads(tool_output)
                        accumulated[tc["name"]] = parsed
                        if "error" in parsed:
                            logger.error("data_node tool '%s' returned error: %s", tc["name"], parsed["error"])
                        else:
                            logger.info("data_node tool '%s' result: %s", tc["name"], json.dumps(parsed, default=str)[:500])
                    except Exception:
                        accumulated[tc["name"]] = tool_output
                        logger.warning("data_node tool '%s' returned non-JSON: %s", tc["name"], str(tool_output)[:200])

                    tool_results.append(ToolMessage(
                        content=tool_output,
                        tool_call_id=tc["id"],
                    ))

                # One optional chained round if Gemini wants more tool calls
                if tool_results:
                    messages2 = [SystemMessage(content=data_system)] + recent_messages + [response] + tool_results
                    response2: AIMessage = await llm_with_tools.ainvoke(messages2)

                    if response2.tool_calls:
                        for tc in response2.tool_calls:
                            tool_fn = tool_map.get(tc["name"])
                            if tool_fn:
                                try:
                                    tool_output = await tool_fn.ainvoke(tc["args"])
                                except Exception as e:
                                    logger.error("data_node round2 tool '%s' raised: %s", tc["name"], e, exc_info=True)
                                    tool_output = json.dumps({"error": str(e)})
                            else:
                                tool_output = json.dumps({"error": f"Unknown tool: {tc['name']}"})

                            try:
                                parsed2 = json.loads(tool_output)
                                accumulated[tc["name"]] = parsed2
                                if "error" in parsed2:
                                    logger.error("data_node round2 '%s' error: %s", tc["name"], parsed2["error"])
                                else:
                                    logger.info("data_node round2 '%s' result: %s", tc["name"], json.dumps(parsed2, default=str)[:500])
                            except Exception:
                                accumulated[tc["name"]] = tool_output

                if accumulated:
                    logger.info("data_node fetched tools: %s", list(accumulated.keys()))
                    for k, v in accumulated.items():
                        if isinstance(v, dict) and "error" in v:
                            logger.error("data_node FINAL context[%s] has error: %s", k, v["error"])
            else:
                logger.info("data_node: Gemini made no tool calls")

            return {
                "data_context": accumulated,
                "intent": "data_fetched",
            }

    except Exception as exc:
        logger.error("data_node unhandled error: %s", exc, exc_info=True)
        return {
            "data_context": state.get("data_context") or {},
            "intent": "data_error",
        }

# ---------------------------------------------------------------------------
async def synthesizer_node(state: AgentState) -> dict:
    """
    Composes the final customer-facing response using:
    - Full conversation history (all messages in state)
    - data_context accumulated by data_node (if any)
    - Deep InsureFlow platform knowledge via system prompt
    """
    data_ctx = state.get("data_context") or {}
    supervisor_notes = state.get("supervisor_notes", "")

    logger.info("synthesizer_node: data_context keys=%s", list(data_ctx.keys()))
    for k, v in data_ctx.items():
        if isinstance(v, dict) and "error" in v:
            logger.error("synthesizer_node: data_context[%s] has error — %s", k, v["error"])
        else:
            logger.info("synthesizer_node: data_context[%s] = %s", k, json.dumps(v, default=str)[:300])

    # Build data context section for the prompt
    if data_ctx:
        data_section = "\n## Live data fetched from the database\n"
        for tool_name, result in data_ctx.items():
            data_section += f"\n### {tool_name}\n```json\n{json.dumps(result, indent=2, default=str)}\n```\n"
    else:
        data_section = "\n## Live data\nNo database data was retrieved for this query.\n"

    context_addon = f"""
{data_section}
## Supervisor context
{supervisor_notes or "N/A"}
"""

    synth_system = SYNTHESIZER_PROMPT + context_addon

    # Use last 10 messages as conversation context
    recent_messages = list(state["messages"])[-10:]

    try:
        llm = _get_llm(temperature=0.4)
        messages = [SystemMessage(content=synth_system)] + recent_messages
        response: AIMessage = await llm.ainvoke(messages)
        reply_preview = _content_str(response.content)[:200]
        logger.info("synthesizer_node: Gemini reply preview: %s", reply_preview)

        return {
            "messages": [response],
            "intent": "synthesized",
        }

    except Exception as exc:
        logger.error("synthesizer_node unhandled error: %s", exc, exc_info=True)
        fallback = AIMessage(
            content="I'm having trouble connecting right now. Please try again shortly."
        )
        return {"messages": [fallback], "intent": "error"}


# ---------------------------------------------------------------------------
# Conditional routing function
# ---------------------------------------------------------------------------
def _route_from_supervisor(state: AgentState) -> Literal["data_node", "synthesizer_node"]:
    route = state.get("route", "data_node")
    return "data_node" if route == "data_node" else "synthesizer_node"


# ---------------------------------------------------------------------------
# Build the compiled graph
# ---------------------------------------------------------------------------
def build_graph() -> StateGraph:
    """
    Graph topology:
      START ? supervisor_node ? [conditional]
                +- route=data_node     ? data_node ? synthesizer_node ? END
                +- route=synthesizer  ? synthesizer_node ? END
    """
    graph = StateGraph(AgentState)

    graph.add_node("supervisor_node", supervisor_node)
    graph.add_node("data_node", data_node)
    graph.add_node("synthesizer_node", synthesizer_node)

    graph.add_edge(START, "supervisor_node")
    graph.add_conditional_edges(
        "supervisor_node",
        _route_from_supervisor,
        {
            "data_node": "data_node",
            "synthesizer_node": "synthesizer_node",
        },
    )
    graph.add_edge("data_node", "synthesizer_node")
    graph.add_edge("synthesizer_node", END)

    return graph.compile()


# Singleton (loaded at import time)
agent_graph = build_graph()
