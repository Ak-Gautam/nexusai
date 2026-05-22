from __future__ import annotations

import json
import re
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nexus_backend.memory.store import append_message
from nexus_backend.memory.store import create_thread
from nexus_backend.memory.store import get_messages
from nexus_backend.memory.store import get_thread
from nexus_backend.models import LlamaCppRuntimeManager
from nexus_backend.models import discover_model_registry
from nexus_backend.tools.admin import AdminToolbox
from nexus_backend.tools.admin import ToolResult


TOOL_CALL_PATTERN = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
MAX_TOOL_RESULT_CHARS = 12000


@dataclass(frozen=True)
class AgentTurn:
    thread_id: str
    answer: str
    tool_calls: list[dict[str, Any]]
    messages: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgentEngine:
    def __init__(
        self,
        database_path: Path,
        model_root: Path,
        downloads_root: Path,
        runtime_manager: LlamaCppRuntimeManager,
    ) -> None:
        self.database_path = database_path
        self.toolbox = AdminToolbox(
            model_root=model_root,
            downloads_root=downloads_root,
            runtime_manager=runtime_manager,
        )
        self.runtime_manager = runtime_manager
        self.model_root = model_root

    def run_turn(
        self,
        user_message: str,
        thread_id: str | None = None,
        model_name: str | None = None,
        temperature: float = 0.2,
        thinking_enabled: bool = True,
        max_tokens: int = 900,
        max_tool_rounds: int = 4,
    ) -> AgentTurn:
        thread = get_thread(self.database_path, thread_id) if thread_id else None
        if thread is None:
            title = _title_from_message(user_message)
            thread = create_thread(self.database_path, title=title)

        append_message(self.database_path, thread.id, "user", user_message)
        tool_calls: list[dict[str, Any]] = []
        answer = ""
        active_model = model_name or self._default_model_name()
        for result in self._run_obvious_tools(user_message):
            tool_calls.append(
                {
                    "name": result.name,
                    "arguments": {},
                    "ok": result.ok,
                    "result": _summarize_tool_payload(result.name, result.payload),
                }
            )
            append_message(
                self.database_path,
                thread.id,
                "tool",
                _compact_json(result.to_dict(), MAX_TOOL_RESULT_CHARS),
                {"tool_name": result.name, "ok": result.ok, "trigger": "deterministic"},
            )

        for _round in range(max_tool_rounds + 1):
            messages = self._build_messages(thread.id)
            result = self.runtime_manager.chat(
                model_name=active_model,
                messages=messages,
                temperature=temperature,
                thinking_enabled=thinking_enabled,
                max_tokens=max_tokens,
            )
            content = _extract_assistant_text(result)
            calls = _parse_tool_calls(content)

            if not calls:
                answer = _strip_tool_markup(content).strip()
                if not answer:
                    answer = _fallback_answer(tool_calls)
                if not answer:
                    answer = _fallback_from_history(get_messages(self.database_path, thread.id, limit=20))
                append_message(self.database_path, thread.id, "assistant", answer, {"kind": "final"})
                break

            append_message(self.database_path, thread.id, "assistant", content, {"kind": "tool_request"})
            for call in calls:
                tool_name = str(call.get("name", "")).strip()
                arguments = call.get("arguments", {})
                if not isinstance(arguments, dict):
                    arguments = {}
                result = self.toolbox.run(tool_name, arguments)
                result_payload = _compact_json(result.to_dict(), MAX_TOOL_RESULT_CHARS)
                tool_calls.append(
                    {
                        "name": tool_name,
                        "arguments": arguments,
                        "ok": result.ok,
                        "result": _summarize_tool_payload(result.name, result.payload),
                    }
                )
                append_message(
                    self.database_path,
                    thread.id,
                    "tool",
                    result_payload,
                    {"tool_name": tool_name, "ok": result.ok},
                )
        else:
            answer = "I could not complete the request because the tool loop reached its limit."
            append_message(self.database_path, thread.id, "assistant", answer, {"kind": "tool_limit"})

        return AgentTurn(
            thread_id=thread.id,
            answer=answer,
            tool_calls=tool_calls,
            messages=[
                message.to_dict()
                for message in get_messages(self.database_path, thread.id, limit=80)
                if message.role in {"user", "assistant"}
            ],
        )

    def _build_messages(self, thread_id: str) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": self._system_prompt()}]
        for message in get_messages(self.database_path, thread_id, limit=30):
            if message.role == "tool":
                messages.append(
                    {
                        "role": "user",
                        "content": f"TOOL_RESULT {message.metadata.get('tool_name', 'unknown')}:\n{message.content}",
                    }
                )
                continue
            if message.role in {"user", "assistant"}:
                messages.append({"role": message.role, "content": message.content})
        return messages

    def _system_prompt(self) -> str:
        return (
            "You are Nexus, a local-first macOS system assistant. "
            "You help with reliable local admin tasks. Do not claim filesystem facts unless a tool provided them. "
            "Never delete, move, rename, or modify files. Recommend actions as dry-run proposals only.\n\n"
            "Available tools:\n"
            f"{json.dumps(self.toolbox.specs(), ensure_ascii=True, indent=2)}\n\n"
            "When you need a tool, output exactly one or more tool calls and no final answer:\n"
            '<tool_call>{"name":"downloads_scan","arguments":{}}</tool_call>\n'
            "After receiving TOOL_RESULT messages, provide a concise final answer with concrete findings and next actions. "
            "For follow-up questions that can be answered from the conversation, answer directly without a tool call. "
            "Keep final answers under 180 words unless the user asks for detail. "
            "Prefer a short summary followed by the top 3-6 items to review. "
            "If no tool is needed, answer normally."
        )

    def _default_model_name(self) -> str | None:
        status = self.runtime_manager.status()
        if status.loaded:
            return status.model_name
        registry = discover_model_registry(self.model_root)
        return registry.defaults.planner or registry.defaults.router

    def _run_obvious_tools(self, user_message: str) -> list[ToolResult]:
        lower = user_message.lower()
        results = []
        if "download" in lower:
            results.append(self.toolbox.run("downloads_scan", {}))
        if "model" in lower or "runtime" in lower:
            results.append(self.toolbox.run("model_registry", {}))
        if "loaded" in lower or "running" in lower or "runtime" in lower:
            results.append(self.toolbox.run("runtime_status", {}))
        return results


def _parse_tool_calls(content: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for match in TOOL_CALL_PATTERN.finditer(content):
        try:
            parsed = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            calls.append(parsed)
    return calls


def _strip_tool_markup(content: str) -> str:
    return TOOL_CALL_PATTERN.sub("", content)


def _extract_assistant_text(result: dict[str, object]) -> str:
    response = result.get("response")
    if not isinstance(response, dict):
        return ""
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""


def _compact_json(payload: dict[str, Any], max_chars: int) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, indent=2)
    if len(encoded) <= max_chars:
        return encoded
    return encoded[:max_chars] + "\n... truncated ..."


def _title_from_message(message: str) -> str:
    compact = " ".join(message.strip().split())
    return compact[:80] if compact else "Nexus thread"


def _summarize_tool_payload(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if name == "downloads_scan":
        return {
            "scanned_files": payload.get("scanned_files"),
            "total_size_bytes": payload.get("total_size_bytes"),
            "large_files": payload.get("large_files", [])[:5],
            "duplicate_group_count": len(payload.get("duplicate_groups", [])),
            "recommendations": payload.get("recommendations", [])[:8],
        }
    return payload


def _fallback_answer(tool_calls: list[dict[str, Any]]) -> str:
    for call in tool_calls:
        if call.get("name") != "downloads_scan" or not call.get("ok"):
            continue
        result = call.get("result")
        if not isinstance(result, dict):
            continue
        total_size = _format_bytes(int(result.get("total_size_bytes") or 0))
        scanned = result.get("scanned_files")
        recommendations = result.get("recommendations", [])
        large_files = result.get("large_files", [])
        lines = [f"Downloads contains {scanned} files using about {total_size}."]
        if large_files:
            first = large_files[0]
            if isinstance(first, dict):
                lines.append(f"Review the largest file first: {first.get('name')} ({_format_bytes(int(first.get('size_bytes') or 0))}).")
        if isinstance(recommendations, list) and recommendations:
            lines.append("Top dry-run recommendations:")
            for item in recommendations[:5]:
                if isinstance(item, dict):
                    lines.append(f"- {item.get('action')}: {item.get('target')} - {item.get('reason')}")
        return "\n".join(lines)
    return ""


def _fallback_from_history(messages: list[object]) -> str:
    previous_assistant = ""
    latest_user = ""
    for message in messages:
        role = getattr(message, "role", "")
        content = getattr(message, "content", "")
        if role == "assistant" and content and "model did not produce a usable final answer" not in content:
            previous_assistant = content
        if role == "user" and content:
            latest_user = content.lower()

    if previous_assistant and "single item" in latest_user:
        for line in previous_assistant.splitlines():
            if "Review the largest file first:" in line:
                item = line.split("Review the largest file first:", 1)[1].strip().rstrip(".")
                return f"Deal with {item} first. It is the highest-impact item because moving or removing one large file frees the most space with the least review effort."

    if previous_assistant:
        return f"Based on the previous scan: {previous_assistant}"

    return "I could not produce a useful answer for that turn."


def _format_bytes(size: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"
