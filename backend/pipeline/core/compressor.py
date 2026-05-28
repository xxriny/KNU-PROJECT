"""
Prompt Compressor stub — compress_prompt is always False throughout the codebase.
LLMLingua / PyTorch dependency removed. If prompt compression is needed in the
future, re-enable by installing llmlingua and restoring the implementation.
"""
from observability.logger import get_logger

_logger = get_logger()


class PromptCompressor:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def compress_with_preservation(self, text: str, target_token_rate: float = 0.5, extra_preserve=None) -> str:
        return text


_compressor_instance = None


def get_compressor() -> PromptCompressor:
    global _compressor_instance
    if _compressor_instance is None:
        _compressor_instance = PromptCompressor()
    return _compressor_instance
