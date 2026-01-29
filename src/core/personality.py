"""
Personality loading module for the MCMP chatbot.

This module handles loading static personality content from markdown files.
The personality defines the chatbot's identity, tone, and behavioral guidelines,
while dynamic context (date, graph, retrieved docs) is injected separately
by the engine at runtime.
"""

from pathlib import Path
from src.utils.logger import log_info, log_error


def load_personality(filepath: str = "prompts/personality.md") -> str:
    """
    Load static personality from a markdown file.
    
    Args:
        filepath: Path to the personality markdown file.
                  Defaults to 'prompts/personality.md'.
    
    Returns:
        The contents of the personality file as a string.
        Returns empty string if file doesn't exist.
    """
    path = Path(filepath)
    
    if not path.exists():
        log_error(f"Personality file not found: {filepath}")
        return ""
    
    content = path.read_text(encoding="utf-8")
    log_info(f"Loaded personality from {filepath} ({len(content)} chars)")
    return content
