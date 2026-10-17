import logging

from agentic_memory.setting import QUERY_SENTENCE_MIN_WORDS

logger = logging.getLogger(__name__)

_REFORMULATE_PROMPT = """\
Rewrite the following task description as a natural-language question suitable for semantic search.
Task: {task}
Question (one sentence, no markdown):"""

_SENTENCE_MIN_WORDS = QUERY_SENTENCE_MIN_WORDS


def _looks_like_sentence(text: str) -> bool:
    """Heuristic: skip reformulation if the query already looks like a full sentence."""
    words = text.split()
    return len(words) >= _SENTENCE_MIN_WORDS


class QueryReformulator:
    """Optionally rewrite a short keyword query into a natural-language question."""

    def __init__(self, llm=None) -> None:
        self._llm = llm

    def reformulate(self, query: str) -> str:
        """Return a (possibly rewritten) query string.

        If the query is already a full sentence, or no LLM is configured, returns
        the query unchanged.
        """
        if self._llm is None or _looks_like_sentence(query):
            return query

        try:
            prompt = _REFORMULATE_PROMPT.format(task=query)
            response = self._llm.invoke(prompt)
            result = response.content if hasattr(response, "content") else str(response)
            result = result.strip()
            if result:
                logger.debug("Reformulated query: %r → %r", query, result)
                return result
        except Exception as exc:
            logger.warning("Query reformulation failed: %s", exc)

        return query
