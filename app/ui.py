import gradio as gr

from app.agents.rag_agent import ask


def _chat(message: str, history: list, thread_id: str) -> str:
    return ask(message, thread_id=thread_id)


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="RAG Agent") as demo:
        gr.Markdown("## RAG Agent\nAsk anything about Mathematics, AI Engineering, or Computer Science.")

        thread_id = gr.State(value="default-session")

        gr.ChatInterface(
            fn=_chat,
            additional_inputs=[thread_id],
        )

    return demo
