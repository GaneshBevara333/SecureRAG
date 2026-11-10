import os
from typing import Optional, Any
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from app.config import get_settings


class StubChatModel(BaseChatModel):
    provider_name: str = "stub"

    def _generate(self, messages: list[BaseMessage], stop: Optional[list[str]] = None, **kwargs: Any) -> ChatResult:
        prompt_text = " ".join([m.content for m in messages if isinstance(m.content, str)])

        if "Context:\nNo relevant documents found." in prompt_text:
            text = "not found in your documents"
        elif "Context:" in prompt_text and "Question:" in prompt_text:
            parts = prompt_text.split("Question:")
            context_part = parts[0].split("Context:")[1].lower() if "Context:" in parts[0] else ""
            q_part = parts[1].split("Answer:")[0].strip().lower()
            
            # Words with length > 3 from the question
            keywords = [w.strip("?.,!;:\"'") for w in q_part.split() if len(w.strip("?.,!;:\"'")) > 3]
            
            # If question has keywords and none are found in the retrieved context
            if keywords and not any(k in context_part for k in keywords):
                text = "not found in your documents"
            else:
                text = "Based on the provided documents: here is the retrieved answer."
        else:
            text = "not found in your documents"

        p_tokens = max(1, len(prompt_text) // 4)
        c_tokens = max(1, len(text) // 4)
        msg = AIMessage(
            content=text,
            usage_metadata={
                "input_tokens": p_tokens,
                "output_tokens": c_tokens,
                "total_tokens": p_tokens + c_tokens,
            },
            response_metadata={
                "provider": self.provider_name,
                "model_name": f"{self.provider_name}-model",
            },
        )
        generation = ChatGeneration(message=msg)
        return ChatResult(generations=[generation])

    @property
    def _llm_type(self) -> str:
        return self.provider_name


def determine_provider(response: Any, llm: Any = None) -> str:
    """Determine which provider generated the response (groq, gemini, or stub)."""
    if hasattr(response, "response_metadata") and response.response_metadata:
        meta = response.response_metadata
        if "provider" in meta:
            return str(meta["provider"]).lower()
        model_str = str(meta.get("model_name") or meta.get("model") or "").lower()
        if "gemini" in model_str or "google" in model_str:
            return "gemini"
        if "groq" in model_str or "llama" in model_str:
            return "groq"

    if llm is not None:
        llm_type = getattr(llm, "_llm_type", "")
        if "gemini" in llm_type.lower() or "google" in llm_type.lower():
            return "gemini"
        if "groq" in llm_type.lower():
            return "groq"
        if "stub" in llm_type.lower():
            return "stub"

    return "groq"


def get_llm(primary_override: Any = None, fallback_override: Any = None):
    """
    Return configured Chat model (Groq with Gemini fallback, or stub if no key).
    Accepts primary_override and fallback_override for dependency injection in tests.
    """
    if primary_override is not None and fallback_override is not None:
        return primary_override.with_fallbacks([fallback_override])
    elif primary_override is not None:
        return primary_override
    elif fallback_override is not None:
        return fallback_override

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
