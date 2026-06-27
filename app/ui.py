import uuid

import gradio as gr

from app.agents.deep_agent import ask as deep_ask


def _deep_chat(message: str, history: list, thread_id: str) -> str:
    return deep_ask(message, thread_id=thread_id)


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="EduMentor AI") as demo:
        gr.Markdown(
            "# EduMentor AI\n"
            "Your AI mentor for **Mathematics, AI Engineering, and Computer Science**. "
            "Ask a concept, request an explanation, or take an exam — one chat handles it all.\n\n"
            "**Try:** `Explain RAG` · `Give me 5 questions on Transformers` · "
            "then answer with `1-a, 2-c, 3-b, …`"
        )
        deep_thread = gr.State(value=lambda: f"deep-{uuid.uuid4().hex[:8]}")
        gr.ChatInterface(fn=_deep_chat, additional_inputs=[deep_thread])

    return demo
