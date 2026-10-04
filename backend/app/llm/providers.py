import os
from typing import Optional, Any
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from app.config import get_settings


class StubChatModel(BaseChatModel):
    """Stub LLM model used for unit tests or when no external API key is provided."""

    def _generate(self, messages: list[BaseMessage], stop: Optional[list[str]] = None, **kwargs: Any) -> ChatResult:
        # Simple heuristic response generator for testing
        prompt_text = " ".join([m.content for m in messages if isinstance(m.content, str)])
        
        # If question not in context
        if "Context:\nNo relevant documents found." in prompt_text:
            text = "not found in your documents"
        elif "Context:" in prompt_text:
            # Extract citation or answer from context
            text = "Based on the provided documents: here is the retrieved answer. [Doc: sample.txt, Page: 1, Chunk: 0]"
        else:
            text = "not found in your documents"

        generation = ChatGeneration(message=AIMessage(content=text))
        return ChatResult(generations=[generation])

    @property
    def _llm_type(self) -> str:
        return "stub-chat-model"


def get_llm():
    """Return configured Chat model (Groq with Gemini fallback, or stub if no key)."""
    settings = get_settings()

    primary_model = None
    fallback_model = None

    if settings.GROQ_API_KEY:
        try:
            from langchain_groq import ChatGroq
            primary_model = ChatGroq(
                groq_api_key=settings.GROQ_API_KEY,
                model_name=settings.GROQ_MODEL,
                temperature=0.0,
            )
        except Exception:
            pass

    if settings.GEMINI_API_KEY:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            fallback_model = ChatGoogleGenerativeAI(
                google_api_key=settings.GEMINI_API_KEY,
                model=settings.GEMINI_MODEL,
                temperature=0.0,
            )
        except Exception:
            pass

    if primary_model and fallback_model:
        return primary_model.with_fallbacks([fallback_model])
    elif primary_model:
        return primary_model
    elif fallback_model:
        return fallback_model
    else:
        return StubChatModel()
