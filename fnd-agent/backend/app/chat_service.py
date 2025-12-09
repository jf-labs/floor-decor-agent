from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException
from pydantic import BaseModel, Field

from . import product_loader
from .embedding_store import get_embedding_index
from .models import ProductDetail, ProductSpec, UseCase
from .ollama_client import OllamaClient
from .rules_engine import build_spec_map
from .use_case_checks import USE_CASE_CHECKERS

SYSTEM_PROMPT = """You are FND Agent, a Floor & Decor assistant.
- Always ground answers in the provided context or tool outputs. If you do not have enough information, say so.
- To use a tool, respond ONLY with JSON of the form:
  {"action":"call_tool","tool_name":"search_products","arguments":{"query":"..."}}.
- When you can answer the customer, respond with:
  {"action":"final_response","content":"<answer>"}.
- Never fabricate SKUs or specs. Prefer citing SKU numbers explicitly.
- Tools available:
  * search_products(query: string, limit?: int) -> find matching SKUs.
  * get_product_detail(sku: string) -> detailed product specs.
  * check_usage(sku: string, use_case: string) -> run the rules engine for a specific scenario.
- After receiving tool results you may call another tool or return the final response.
"""

MAX_TOOL_CALLS = 3


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    active_sku: Optional[str] = Field(
        default=None,
        description="Currently selected SKU from the UI, used as a hint for retrieval.",
    )


class ChatResponse(BaseModel):
    message: ChatMessage
    referenced_products: List[ProductDetail] = []


def _detail_to_summary(detail: ProductDetail, idx: int) -> str:
    product = detail.product
    spec_map = build_spec_map(detail)
    lines = [
        f"{idx}. SKU {product.sku} — {product.name or 'Unnamed'} (Category: {product.category_slug or 'Unknown'})",
    ]
    keys = (
        "Bathroom Floor Use",
        "Shower Surface",
        "Placement Location",
        "Water Resistance",
        "Frost Resistance",
        "Radiant Heat Compatible",
        "Installation Options",
        "Installation Type",
        "Material",
    )
    for key in keys:
        value = spec_map.get(key.lower())
        if value:
            lines.append(f"   {key}: {value}")
    return "\n".join(lines)


def _dedupe_products(details: List[ProductDetail]) -> List[ProductDetail]:
    seen = set()
    unique: List[ProductDetail] = []
    for detail in details:
        sku = detail.product.sku
        if sku in seen:
            continue
        seen.add(sku)
        unique.append(detail)
    return unique


class ChatService:
    def __init__(self):
        self.llm = OllamaClient()

    def handle_chat(self, payload: ChatRequest, conn) -> ChatResponse:
        if not payload.messages:
            raise HTTPException(status_code=400, detail="At least one message is required.")

        last_user = next((m for m in reversed(payload.messages) if m.role == "user"), None)
        if last_user is None:
            raise HTTPException(status_code=400, detail="Conversation must include a user prompt.")

        try:
            embedding_index = get_embedding_index()
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=400,
                detail="Embedding index not found. Run `python -m app.build_embeddings` from fnd-agent/backend.",
            ) from exc

        retrieved_details, context_text = self._prepare_context(
            conn,
            last_user.content,
            payload.active_sku,
            embedding_index,
        )
        conversation = self._build_conversation(payload.messages, context_text)
        referenced_products = list(retrieved_details)

        for _ in range(MAX_TOOL_CALLS):
            assistant_content = self.llm.chat(conversation)
            action = self._parse_action(assistant_content)
            if action["action"] == "call_tool":
                tool_name = action.get("tool_name")
                arguments = action.get("arguments", {})
                tool_response_text, new_refs = self._execute_tool(conn, tool_name, arguments)
                referenced_products.extend(new_refs)

                conversation.append({"role": "assistant", "content": assistant_content})
                conversation.append(
                    {
                        "role": "system",
                        "content": f"Tool {tool_name} result:\n{tool_response_text}\n"
                        "Respond with another JSON directive.",
                    }
                )
                continue

            final_text = action.get("content") or assistant_content
            assistant_message = ChatMessage(role="assistant", content=final_text.strip())
            return ChatResponse(
                message=assistant_message,
                referenced_products=_dedupe_products(referenced_products),
            )

        raise HTTPException(status_code=500, detail="Too many tool calls without a final response.")

    def _build_conversation(self, messages: List[ChatMessage], context_text: str) -> List[Dict[str, str]]:
        conv: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        if context_text:
            conv.append({"role": "system", "content": context_text})
        for msg in messages:
            if msg.role not in {"user", "assistant"}:
                continue
            conv.append({"role": msg.role, "content": msg.content})
        conv.append(
            {
                "role": "system",
                "content": "Remember: respond with JSON as described earlier.",
            }
        )
        return conv

    def _prepare_context(
        self,
        conn,
        query: str,
        active_sku: Optional[str],
        embedding_index,
        top_k: int = 3,
    ) -> Tuple[List[ProductDetail], str]:
        candidate_skus: List[str] = []
        if active_sku:
            candidate_skus.append(active_sku)

        if query.strip():
            lexical_hits = product_loader.search_products(conn, query, limit=top_k)
            candidate_skus.extend([item.sku for item in lexical_hits])

            for result in embedding_index.search(query, top_k=top_k):
                candidate_skus.append(result.sku)

        seen = set()
        ordered_skus = []
        for sku in candidate_skus:
            if sku and sku not in seen:
                seen.add(sku)
                ordered_skus.append(sku)

        details: List[ProductDetail] = []
        for sku in ordered_skus[:top_k]:
            detail = product_loader.load_product_with_details(conn, sku)
            if detail:
                if not isinstance(detail, ProductDetail):
                    detail = ProductDetail(**detail)
                details.append(detail)

        if not details:
            return [], ""

        context_lines = ["Relevant Floor & Decor products:"]
        for idx, detail in enumerate(details, start=1):
            context_lines.append(_detail_to_summary(detail, idx))
        context_lines.append(
            "Use these facts when answering the next user question. Ask for tool calls if you need fresh data."
        )
        context_text = "\n".join(context_lines)
        return details, context_text

    def _parse_action(self, content: str) -> Dict:
        content = content.strip()
        try:
            data = json.loads(content)
            if isinstance(data, dict) and data.get("action") in {"call_tool", "final_response"}:
                return data
        except json.JSONDecodeError:
            pass
        # Attempt to extract JSON substring
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict) and data.get("action"):
                    return data
            except json.JSONDecodeError:
                pass
        return {"action": "final_response", "content": content}

    def _execute_tool(
        self,
        conn,
        tool_name: Optional[str],
        arguments: Dict,
    ) -> Tuple[str, List[ProductDetail]]:
        if tool_name == "search_products":
            query = arguments.get("query", "")
            limit = int(arguments.get("limit", 5))
            results = product_loader.search_products(conn, query, limit=min(limit, 25))
            payload = [item.model_dump() for item in results]
            return json.dumps({"results": payload}, ensure_ascii=False), []

        if tool_name == "get_product_detail":
            sku = arguments.get("sku")
            if not sku:
                raise HTTPException(status_code=400, detail="get_product_detail requires a sku.")
            detail = product_loader.load_product_with_details(conn, sku)
            if detail is None:
                raise HTTPException(status_code=404, detail=f"SKU {sku} not found.")
            if not isinstance(detail, ProductDetail):
                detail = ProductDetail(**detail)
            return json.dumps(detail.model_dump(), ensure_ascii=False), [detail]

        if tool_name == "check_usage":
            sku = arguments.get("sku")
            use_case_value = arguments.get("use_case")
            if not sku or not use_case_value:
                raise HTTPException(status_code=400, detail="check_usage requires sku and use_case.")
            try:
                use_case = UseCase(use_case_value)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"Unknown use case {use_case_value}.") from exc

            detail = product_loader.load_product_with_details(conn, sku)
            if detail is None:
                raise HTTPException(status_code=404, detail=f"SKU {sku} not found.")
            if not isinstance(detail, ProductDetail):
                detail = ProductDetail(**detail)

            checker = USE_CASE_CHECKERS.get(use_case)
            if checker is None:
                raise HTTPException(status_code=400, detail=f"Use case {use_case_value} not supported.")
            usage_result = checker(detail)
            return json.dumps(usage_result.model_dump(), ensure_ascii=False), [detail]

        raise HTTPException(status_code=400, detail=f"Tool {tool_name} is not supported.")

