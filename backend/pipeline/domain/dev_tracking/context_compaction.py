from __future__ import annotations

import os
from typing import Any

from .utils import _as_dict


def _changed_file_set(state: dict[str, Any]) -> set[str]:
    checkout = _as_dict(state.get("checkout"))
    candidates = state.get("changed_files") or checkout.get("changed_files") or []
    if not isinstance(candidates, list):
        return set()
    return {
        str(item).replace("\\", "/")
        for item in candidates
        if str(item or "").strip()
    }


def _prioritize_inventory_for_pr(
    inventory: dict[str, Any],
    changed_files: set[str],
    *,
    max_files: int = 240,
    max_symbols: int = 320,
) -> dict[str, Any]:
    # author: xxrin
    # LLM 컨텍스트는 PR 변경 파일을 최우선으로 보존하고 나머지 repo 정보는 제한된 요약으로 뒤에 둔다.
    files = inventory.get("files", []) if isinstance(inventory.get("files"), list) else []
    symbols_by_file = _as_dict(inventory.get("symbols_by_file"))
    if not changed_files:
        selected_files = files[:max_files]
    else:
        changed = [
            item for item in files
            if isinstance(item, dict) and str(item.get("file") or "").replace("\\", "/") in changed_files
        ]
        related_imports = {
            str(path).replace("\\", "/")
            for item in changed
            for path in (item.get("internal_imports") or [])
        }
        related = [
            item for item in files
            if isinstance(item, dict)
            and str(item.get("file") or "").replace("\\", "/") in related_imports
            and item not in changed
        ]
        rest = [item for item in files if item not in changed and item not in related]
        selected_files = [*changed, *related, *rest[: max(0, max_files - len(changed) - len(related))]]

    selected_names = {
        str(item.get("file") or "").replace("\\", "/")
        for item in selected_files
        if isinstance(item, dict)
    }
    selected_symbols: dict[str, list[dict[str, Any]]] = {}
    symbol_count = 0
    for file_name in selected_names:
        items = symbols_by_file.get(file_name) or []
        if not isinstance(items, list):
            continue
        remaining = max_symbols - symbol_count
        if remaining <= 0:
            break
        selected_symbols[file_name] = items[:remaining]
        symbol_count += len(selected_symbols[file_name])

    return {
        "files": selected_files,
        "symbols_by_file": selected_symbols,
        "summary": {
            **_as_dict(inventory.get("summary")),
            "selected_file_count": len(selected_files),
            "selected_symbol_count": symbol_count,
            "changed_file_count": len(changed_files),
        },
    }


def _compact_inventory_for_approval_task(
    inventory: dict[str, Any],
    changed_files: set[str],
) -> dict[str, Any]:
    # author: xxrin
    # PM 승인 이후 code chunk 반영에 필요한 근거만 task payload에 남겨 local.db payload 비대화를 막는다.
    compact = _prioritize_inventory_for_pr(
        inventory,
        changed_files,
        max_files=60,
        max_symbols=120,
    )
    compact["summary"] = {
        **_as_dict(compact.get("summary")),
        "approval_payload_compacted": True,
    }
    return compact


def _compress_if_available(
    text: str,
    *,
    enabled: bool,
    rate: float,
    preserve: list[str],
) -> tuple[str, dict[str, Any]]:
    if not enabled or len(text) < 6000:
        return text, {"used": False, "reason": "disabled_or_short_context"}
    try:
        max_chunk_chars = int(os.getenv("NAVIGATOR_PROMPT_COMPRESS_CHUNK_CHARS", "12000") or "12000")
        max_output_chars = int(os.getenv("NAVIGATOR_PROMPT_COMPRESS_OUTPUT_CHARS", "36000") or "36000")
        if max_chunk_chars > 0 and len(text) > max_chunk_chars:
            compressed, meta = _compress_text_in_chunks(
                text,
                rate=rate,
                preserve=preserve,
                max_chunk_chars=max_chunk_chars,
                max_output_chars=max_output_chars,
            )
            return compressed, meta

        from pipeline.core.compressor import get_compressor
        compressed = get_compressor().compress_with_preservation(
            text,
            target_token_rate=rate,
            extra_preserve=preserve,
        )
        return compressed, {
            "used": compressed != text,
            "original_chars": len(text),
            "compressed_chars": len(compressed),
        }
    except Exception as exc:
        return text, {"used": False, "error": str(exc) or type(exc).__name__}


def _split_text_chunks(text: str, max_chars: int) -> list[str]:
    # author: xxrin
    # 긴 JSON/컨텍스트를 줄 단위 chunk로 나눠 압축기가 512 토큰 제한을 넘지 않도록 한다.
    if max_chars <= 0 or len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in text.splitlines():
        line_len = len(line) + 1
        if current and current_len + line_len > max_chars:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        if line_len > max_chars:
            if current:
                chunks.append("\n".join(current))
                current = []
                current_len = 0
            for index in range(0, len(line), max_chars):
                chunks.append(line[index:index + max_chars])
            continue
        current.append(line)
        current_len += line_len
    if current:
        chunks.append("\n".join(current))
    return chunks


def _compress_text_in_chunks(
    text: str,
    *,
    rate: float,
    preserve: list[str],
    max_chunk_chars: int,
    max_output_chars: int,
) -> tuple[str, dict[str, Any]]:
    from pipeline.core.compressor import get_compressor

    compressor = get_compressor()
    chunks = _split_text_chunks(text, max_chunk_chars)
    compressed_parts: list[str] = []
    failed_chunks = 0
    for index, chunk in enumerate(chunks):
        try:
            compressed = compressor.compress_with_preservation(
                chunk,
                target_token_rate=rate,
                extra_preserve=preserve,
            )
        except Exception:
            failed_chunks += 1
            compressed = chunk[:max_chunk_chars]
        compressed_parts.append(f"[chunk {index + 1}/{len(chunks)}]\n{compressed}")

    merged = "\n\n".join(compressed_parts)
    truncated = False
    if max_output_chars > 0 and len(merged) > max_output_chars:
        truncated = True
        merged = merged[:max_output_chars] + "\n... [truncated after chunk compression]"
    return merged, {
        "used": True,
        "mode": "chunked",
        "chunk_count": len(chunks),
        "failed_chunks": failed_chunks,
        "original_chars": len(text),
        "compressed_chars": len(merged),
        "truncated": truncated,
    }
