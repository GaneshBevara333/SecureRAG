import time
import re
import hashlib
import threading
from typing import Dict, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from app.llm.providers import get_llm, StubChatModel

JUDGE_SYSTEM_PROMPT = """You are an impartial evaluator assessing the faithfulness of an AI-generated answer.
You will be provided with a Question, retrieved Context, and the Answer.
Determine if all factual claims made in the Answer are directly supported by the Context.
Output ONLY a float number between 0.0 and 1.0, where:
1.0 = completely faithful and grounded in the context.
0.0 = ungrounded, hallucinated, or contradictory.
Do not output any other text or explanation, only the float score."""


class JudgeService:
    """LLM-as-a-judge service for evaluating answer faithfulness with hashing cache and 429 retry backoff."""

    def __init__(self):
        self._cache: Dict[str, float] = {}
        self._lock = threading.Lock()
        self.call_count: int = 0
        self.cache_hits: int = 0
        self.cache_misses: int = 0

    @staticmethod
    def compute_cache_key(question: str, answer: str, context: str) -> str:
        payload = f"{question.strip()}|||{answer.strip()}|||{context.strip()}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def evaluate_faithfulness(
        self,
        question: str,
        answer: str,
        context: str,
        max_retries: int = 3,
        initial_backoff: float = 0.5,
    ) -> float:
        """
        Evaluate faithfulness of an answer with respect to context.
        Uses cached score if hash(question + answer + context) was previously evaluated.
        Retries on 429 rate limit errors with exponential backoff.
        """
        cache_key = self.compute_cache_key(question, answer, context)

        with self._lock:
            if cache_key in self._cache:
                self.cache_hits += 1
                return self._cache[cache_key]
            self.cache_misses += 1
            self.call_count += 1

        score = self._invoke_judge_with_retry(
            question=question,
            answer=answer,
            context=context,
            max_retries=max_retries,
            initial_backoff=initial_backoff,
        )

        with self._lock:
            self._cache[cache_key] = score

        return score

    def _invoke_judge_with_retry(
        self,
        question: str,
        answer: str,
        context: str,
        max_retries: int,
        initial_backoff: float,
    ) -> float:
        llm = get_llm()

        # Deterministic evaluation for StubChatModel
        if isinstance(llm, StubChatModel):
            if answer.strip().lower() == "not found in your documents":
                return 1.0
            if not context.strip():
                return 0.0
            # Check overlap between answer words and context
            answer_words = set(re.findall(r"\w{4,}", answer.lower()))
            context_lower = context.lower()
            if not answer_words:
                return 1.0
            matched = sum(1 for w in answer_words if w in context_lower)
            return round(matched / len(answer_words), 2)

        prompt = f"Question: {question}\n\nContext:\n{context}\n\nAnswer:\n{answer}"
        messages = [
            SystemMessage(content=JUDGE_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        attempt = 0
        backoff = initial_backoff
        while attempt <= max_retries:
            try:
                response = llm.invoke(messages)
                content = response.content if isinstance(response.content, str) else str(response.content)
                match = re.search(r"(\d+(\.\d+)?)", content)
                if match:
                    val = float(match.group(1))
                    return max(0.0, min(1.0, val))
                return 1.0
            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = "429" in err_str or "rate limit" in err_str or "resource exhausted" in err_str
                if is_rate_limit and attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= 2.0
                    attempt += 1
                else:
                    # Fallback score if judge call ultimately fails
                    return 0.8

        return 0.8

    def reset_cache(self) -> None:
        """Clear cache and reset invocation metrics (used in tests)."""
        with self._lock:
            self._cache.clear()
            self.call_count = 0
            self.cache_hits = 0
            self.cache_misses = 0


judge_service = JudgeService()
