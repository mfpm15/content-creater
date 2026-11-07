"""Shared research entry point (Tavily). Credentials stay in the inherited environment."""
import tavily_research
from security import redact


def research(topic: str, context: str, model: str = "") -> dict:
    try:
        return tavily_research.search(topic, context)
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("Riset Tavily gagal: " + redact(str(exc))) from None
