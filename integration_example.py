"""
integration_example.py
─────────────────────────────────────────────────────────
Shows exactly how to wire Tool 2 (Exam Generator) into
the shared LangGraph ReAct agent alongside Tool 1 & Tool 3.

Copy/adapt the relevant sections into your agent.py file.
"""

import os
from typing import Annotated, Any
from typing_extensions import TypedDict

from dotenv import load_dotenv

load_dotenv()

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent   # LangGraph V1 — still valid here
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from langgraph.graph import MessagesState
from langgraph.managed import RemainingSteps         # required by create_react_agent >= V1
from litellm import completion
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver

# ── Tool imports ─────────────────────────────────────────────────────────────
from tool_exam_generator import generate_exam_tool
from tool_exam_grader import grade_answers_tool
from exam_state import read_exam_from_state


def merge_messages(left: list, right: list) -> list:
    if not left:
        left = []
    if not right:
        right = []
    return left + right

class AgentState(TypedDict):
    messages:        Annotated[list[BaseMessage], merge_messages] # استخدام الدالة اليدوية
    active_exam:     dict[str, Any] | None   
    remaining_steps: int  # إزالة الـ Annotated والـ RemainingSteps هنا مؤقتاً لتجنب تعارض الإصدارات


SYSTEM_PROMPT = """
You are EduMentor, an educational assistant for AI-engineering topics.
You have access to three tools:

1. rag_explain_tool     — Use for concept questions, explanations, summaries,
                          and Q&A grounded in the study corpus.

2. generate_exam_tool   — Use when the learner asks for a quiz, exam, or test.
                          Default to 5 questions and mixed topics unless the
                          learner specifies otherwise.
                          Pass the CURRENT state dict as the first argument.
                          IMPORTANT: After calling this tool, you MUST output the
                          ENTIRE "message" field from the tool result word-for-word,
                          including every question and every answer option.
                          Do NOT summarize, shorten, or paraphrase it.

3. grade_answers_tool   — Use when the learner replies with answers in the
                          format "1-b, 2-c, 3-a, ...".
                          Pass the CURRENT state dict as the first argument.
                          After calling this tool, output the full "message" field
                          exactly as returned.

IMPORTANT RULE — Empty or invalid answers:
If there is an active exam and the learner's message is empty, unclear, or does
not contain answers in the format "1-a, 2-b, ..." do NOT call grade_answers_tool.
Instead, respond directly with:
  "⚠️ Please provide your answers in the correct format, for example:
   1-a, 2-c, 3-b, 4-d, 5-a
   One answer per question, separated by commas."

Never reveal the answer key. If asked, politely decline.
""".strip()





def build_agent():
    checkpointer = MemorySaver()
    
    tools = [

        generate_exam_tool,     
        grade_answers_tool,  
    ]

    raw_model_name = os.getenv("LLM_MODEL_NAME", "llama-3.3-70b-versatile")
    model_id = raw_model_name.split("/", 1)[-1] if "/" in raw_model_name else raw_model_name
    
    groq_api_key = os.getenv("GROQ_API_KEY")

    llm = ChatGroq(
        model=model_id, 
        api_key=groq_api_key or None,
        temperature=0.7
    )
    
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
        state_schema=AgentState,  
        checkpointer=checkpointer,
    )
    return agent



if __name__ == "__main__":
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

    agent = build_agent()
    config = {"configurable": {"thread_id": "interactive_student_session"}}
    
    state: AgentState = {
        "messages": [],
        "active_exam": None,
    }

    print("🤖 EduMentor AI \n" + "═"*60)

    while True:
        user_input = input("\n👤 You: ")
        if user_input.strip().lower() in ["exit", "quit"]:
            print("👋 Bye!")
            break
            
        # If there is an active exam and the user sends an empty message,
        # let the LLM handle it so it can remind the user of the answer format.
        current_state = agent.get_state(config).values
        has_active_exam = bool(current_state.get("active_exam")) if current_state else False

        if not user_input.strip():
            if has_active_exam:
                user_input = ""   # pass empty string so LLM notices and reminds
            else:
                continue

        state["messages"].append(HumanMessage(content=user_input))

        try:
            for chunk in agent.stream(state, config=config):
    
                if "agent" in chunk and "messages" in chunk["agent"]:
                    last_msg = chunk["agent"]["messages"][-1]
                    if last_msg.content: 
                        print(f"\n🤖 EduMentor:\n{last_msg.content}") # طباعة رد البوت الذكي والنظيف
                
                elif "tools" in chunk and "messages" in chunk["tools"]:
                    tool_msg = chunk["tools"]["messages"][-1]
                    print(f"\n⚙️ [Running: {tool_msg.name}...]")

            state = agent.get_state(config).values

        except Exception as e:
            print(f"\n⚠️ An error occurred while processing the request: {e}")
