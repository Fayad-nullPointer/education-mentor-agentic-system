import uuid

import gradio as gr

from app.agents.rag_agent import ask as rag_ask
from app.agents.edu_agent import ask as edu_ask


def _rag_chat(message: str, history: list, thread_id: str) -> str:
    return rag_ask(message, thread_id=thread_id)


def _edu_chat(message: str, history: list, thread_id: str) -> str:
    return edu_ask(message, thread_id=thread_id)


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="EduMentor AI") as demo:
        gr.Markdown("# EduMentor AI")

        with gr.Tabs():
            with gr.Tab("📚 RAG Agent"):
                gr.Markdown("Ask anything about Mathematics, AI Engineering, or Computer Science.")
                rag_thread = gr.State(value="rag-session")
                gr.ChatInterface(fn=_rag_chat, additional_inputs=[rag_thread])

            with gr.Tab("🎓 Exam + Grading"):
                gr.Markdown(
                    "Take a full exam and get graded with personalized feedback.\n\n"
                    "**Try:** `Give me 5 questions on RAG` or `Start a quiz on Transformers`\n\n"
                    "Answer each question with just **a**, **b**, **c**, or **d**. "
                    "Type **exit** at any time to cancel."
                )
                edu_thread = gr.State(value=lambda: f"edu-{uuid.uuid4().hex[:8]}")
                gr.ChatInterface(fn=_edu_chat, additional_inputs=[edu_thread])

    return demo
