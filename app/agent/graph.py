"""LangGraph tool-execution graph for Kotak Prime voice agent."""

from __future__ import annotations

import json
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.tools.kotak_tools import TOOL_BY_NAME


class ToolCallState(TypedDict, total=False):
    tool_name: str
    tool_args: dict[str, Any]
    result: str
    error: str


def _execute_tool_node(state: ToolCallState) -> ToolCallState:
    name = state.get("tool_name", "")
    args = state.get("tool_args") or {}
    tool = TOOL_BY_NAME.get(name)
    if not tool:
        return {
            **state,
            "error": f"Unknown tool: {name}",
            "result": json.dumps({"error": f"Unknown tool: {name}"}),
        }
    try:
        output = tool.invoke(args)
        if not isinstance(output, str):
            output = json.dumps(output, ensure_ascii=False)
        return {**state, "result": output, "error": ""}
    except Exception as exc:  # noqa: BLE001 - surface tool failures to the model
        payload = json.dumps({"error": str(exc)})
        return {**state, "result": payload, "error": str(exc)}


def build_tool_graph():
    graph = StateGraph(ToolCallState)
    graph.add_node("execute_tool", _execute_tool_node)
    graph.add_edge(START, "execute_tool")
    graph.add_edge("execute_tool", END)
    return graph.compile()


tool_graph = build_tool_graph()


def run_tool(tool_name: str, tool_args: dict[str, Any] | None = None) -> str:
    """Execute a single realtime function call through LangGraph."""
    result = tool_graph.invoke(
        {
            "tool_name": tool_name,
            "tool_args": tool_args or {},
        }
    )
    return result.get("result") or json.dumps({"error": "No tool result"})
