# Temporary Vertex Structured Output Fallback

Date: 2026-05-06

## Why this exists

PM/SA analysis needs to run while Gemini Developer API quota is exhausted. The temporary workaround is to run PM/SA through Vertex AI.

During Vertex AI testing, `sa_merge_project` failed in the shared LLM wrapper:

```text
RuntimeError: Structured output parsed result is None
```

The model call completed, but LangChain returned `parsed = None` for `with_structured_output(..., include_raw=True)`. In some Vertex responses, the structured JSON is still present in the raw AI message content or tool-call arguments.

## What changed

File:

```text
backend/pipeline/core/utils.py
```

Temporary helpers were added:

```text
_json_from_text
_raw_structured_candidates
_parse_raw_structured_fallback
_call_raw_structured_fallback
```

And this block was added inside `call_structured()`:

```python
if parsed is None:
    parsed = _parse_raw_structured_fallback(schema, raw)
    if parsed is None:
        fallback_result = _call_raw_structured_fallback(...)
        if fallback_result is not None:
            return fallback_result
        raise RuntimeError("Structured output parsed result is None")
```

This only changes the failure path where LangChain does not populate `parsed`.

## How to revert later

When Gemini Developer API quota is available again, or when provider-specific LLM routing is implemented, remove:

1. `_json_from_text`
2. `_raw_structured_candidates`
3. `_parse_raw_structured_fallback`
4. `_call_raw_structured_fallback`
5. The fallback assignment/raw retry inside `if parsed is None`

Then restore the original behavior:

```python
if parsed is None:
    raise RuntimeError("Structured output parsed result is None")
```

## Verification

Run:

```powershell
cd C:\Users\ning\Desktop\navigator\KNU-PROJECT\backend
.\.venv\Scripts\python.exe -m py_compile pipeline\core\utils.py
```

Then restart the backend server before testing PM/SA with Vertex AI.
