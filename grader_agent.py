from deepagents import create_deep_agent
from grader_tool import grade_exam
import config

def get_grader_agent():
    """
    Creates and returns the Grader Agent using the LangChain deepagents harness.
    
    This agent wraps the core LLM and makes the `grade_exam` tool available, which
    has access to the active exam from the LangGraph AgentState.
    """
    system_prompt = (
        "You are the EduMentor AI Grader Agent.\n"
        "Your primary role is to evaluate student exams. When the user provides their answers "
        "in chat (e.g. '1-b, 2-c, 3-a, 4-d, 5-b'), you must invoke the `grade_exam` tool "
        "to parse the input, grade it against the exam stored in the state, generate educational "
        "explanations for mistakes, and search for course recommendations using Tavily.\n\n"
        "Instructions:\n"
        "1. Pass the student's answer text directly into the `grade_exam` tool.\n"
        "2. Present the markdown report returned by `grade_exam` directly to the student.\n"
        "3. Do not add redundant summaries, greetings, or conversational fluff. Let the report speak for itself.\n"
        "4. If `grade_exam` warns you that no active exam is found in the state, guide the user to generate "
        "an exam first."
    )
    
    agent = create_deep_agent(
        model=config.LLM_MODEL,
        tools=[grade_exam],
        system_prompt=system_prompt
    )
    return agent

if __name__ == "__main__":
    # If run directly, print configuration info
    print("EduMentor AI Grader Agent Loader")
    print(f"Model configured: {config.LLM_MODEL}")
    print("Tool associated: grade_exam")
