import re
import requests
from typing import Annotated, Dict, Any, List
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

import config
from state import Question

def parse_student_answers(raw_text: str) -> Dict[str, str]:
    """
    Parses a string containing student answers (e.g., '1-b, 2-c, 3-a')
    into a structured dictionary mapping question number strings to answer letters.
    
    Supports various delimiters like hyphen, colon, period, or spaces.
    e.g., "1-b", "2: c", "3. a", "4) d", "5 b"
    """
    # Pattern matches digits followed by optional separator followed by a-f characters
    pattern = r'(\d+)\s*[\-\:\.\)\s]?\s*([a-fA-F])'
    matches = re.findall(pattern, raw_text)
    return {q_num: ans.lower() for q_num, ans in matches}

def search_courses_tavily(topic: str) -> List[Dict[str, Any]]:
    """
    Queries Tavily Search API for course recommendations on approved platforms.
    Restricts results to coursera.org, udemy.com, and deeplearning.ai.
    """
    if not config.TAVILY_API_KEY or config.TAVILY_API_KEY == "your_tavily_api_key_here":
        # Fallback Mock Courses if API Key is not set or placeholder
        mock_database = {
            "rag": [
                {"title": "Retrieval-Augmented Generation (RAG) Specialization", "url": "https://www.coursera.org/specializations/rag-systems", "source": "Coursera (Mock)"},
                {"title": "Vector Databases & Embeddings for RAG", "url": "https://www.deeplearning.ai/short-courses/vector-databases-embeddings", "source": "DeepLearning.AI (Mock)"},
                {"title": "Mastering RAG with LangChain and LlamaIndex", "url": "https://www.udemy.com/course/mastering-rag", "source": "Udemy (Mock)"}
            ],
            "langgraph": [
                {"title": "AI Agents in LangGraph", "url": "https://www.deeplearning.ai/short-courses/ai-agents-langgraph", "source": "DeepLearning.AI (Mock)"},
                {"title": "Building Multi-Agent Systems", "url": "https://www.coursera.org/learn/multi-agent-systems", "source": "Coursera (Mock)"}
            ],
            "agent": [
                {"title": "AI Agents in LangGraph", "url": "https://www.deeplearning.ai/short-courses/ai-agents-langgraph", "source": "DeepLearning.AI (Mock)"},
                {"title": "Building AI Agents with Python", "url": "https://www.udemy.com/course/building-ai-agents", "source": "Udemy (Mock)"}
            ]
        }
        
        # Match topic keywords to mock database
        topic_lower = topic.lower()
        for key, courses in mock_database.items():
            if key in topic_lower:
                return courses
        return [
            {"title": f"Introduction to {topic}", "url": "https://www.coursera.org", "source": "Coursera (Mock)"},
            {"title": f"Advanced {topic} Guide", "url": "https://www.deeplearning.ai", "source": "DeepLearning.AI (Mock)"}
        ]

    # Target domains as per project brief
    domains = ["coursera.org", "udemy.com", "deeplearning.ai"]
    query = f"{topic} course"
    
    payload = {
        "api_key": config.TAVILY_API_KEY,
        "query": query,
        "include_domains": domains,
        "max_results": 3
    }
    
    try:
        response = requests.post("https://api.tavily.com/search", json=payload, timeout=10)
        response.raise_for_status()
        results = response.json().get("results", [])
        
        parsed_courses = []
        for item in results:
            parsed_courses.append({
                "title": item.get("title", "Course link"),
                "url": item.get("url", ""),
                "source": item.get("url", "").split("/")[2] if "/" in item.get("url", "") else "Course Platform"
            })
        return parsed_courses
    except Exception as e:
        print(f"Warning: Tavily search failed ({e}). Falling back to general domains.")
        # Simple fallback URL list
        return [{"title": f"{topic} Course", "url": f"https://www.coursera.org/search?query={topic.replace(' ', '+')}", "source": "Coursera"}]

def generate_mistake_explanation(question: Question, user_ans: str) -> str:
    """
    Invokes LLM to generate a brief, educational explanation for a mistake.
    """
    options_str = "\n".join([f"  {k}) {v}" for k, v in question['options'].items()])
    correct_text = question['options'].get(question['correct_option'], "")
    user_text = question['options'].get(user_ans, "Unknown Option")
    
    # Try calling LLM if keys are configured
    has_api_key = (config.GEMINI_API_KEY and config.GEMINI_API_KEY != "your_gemini_api_key_here") or \
                  (config.OPENAI_API_KEY and config.OPENAI_API_KEY != "your_openai_api_key_here")

    if not has_api_key:
        # Static educational fallback explanation
        return (f"The correct option is '{question['correct_option']}' ({correct_text}). "
                f"You selected '{user_ans}' ({user_text}). "
                f"Please review the core concepts of '{question['topic']}' to understand why '{question['correct_option']}' is correct.")

    try:
        model = config.get_model()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert AI engineering tutor. The student answered a question incorrectly. Explain why the correct answer is correct and why the student's chosen answer is incorrect. Keep it brief (1-2 sentences), direct, clear, and encouraging."),
            ("user", "Question: {question}\nOptions:\n{options}\nCorrect Option: {correct_option} - {correct_text}\nStudent Selected Option: {user_option} - {user_text}")
        ])
        
        chain = prompt | model | StrOutputParser()
        explanation = chain.invoke({
            "question": question['question'],
            "options": options_str,
            "correct_option": question['correct_option'],
            "correct_text": correct_text,
            "user_option": user_ans,
            "user_text": user_text
        })
        return explanation.strip()
    except Exception as e:
        print(f"Warning: LLM explanation generation failed: {e}")
        return f"Correct option is '{question['correct_option']}' ({correct_text}). Your option was '{user_ans}' ({user_text})."

@tool
def grade_exam(student_answers: str, state: Annotated[dict, InjectedState]) -> str:
    """
    Parses student answers, grades them against the active exam stored in the AgentState,
    generates brief mistake explanations using an LLM, and recommends courses for weak topics via Tavily.
    
    Args:
        student_answers: The student's answers written in chat (e.g. '1-b, 2-c, 3-a, 4-d, 5-b').
    """
    # 1. Retrieve the exam from State
    active_exam: List[Question] = state.get("active_exam")
    if not active_exam:
        return ("Error: No active exam found in the agent state. Please request an exam first "
                "before submitting answers.")

    # 2. Parse the student's answers
    parsed_answers = parse_student_answers(student_answers)
    if not parsed_answers:
        return ("Could not parse any answers from your input. Please provide your answers "
                "in a format like: '1-b, 2-c, 3-a, 4-d, 5-b'.")

    # 3. Grade the responses
    correct_count = 0
    total_questions = len(active_exam)
    mistakes = []
    weak_topics = set()

    for question in active_exam:
        q_id_str = str(question['id'])
        correct_opt = question['correct_option'].lower()
        
        student_opt = parsed_answers.get(q_id_str)
        if student_opt is not None:
            student_opt = student_opt.lower()
            
        if student_opt == correct_opt:
            correct_count += 1
        else:
            # Mistake recorded (either wrong option or unanswered)
            user_ans = student_opt if student_opt else "unanswered"
            mistakes.append({
                "question": question,
                "user_answer": user_ans
            })
            weak_topics.add(question['topic'])

    # 4. Generate feedback for mistakes
    mistakes_feedback = []
    for mistake in mistakes:
        question = mistake["question"]
        user_ans = mistake["user_answer"]
        explanation = generate_mistake_explanation(question, user_ans)
        
        mistakes_feedback.append(
            f"**Question {question['id']}:** {question['question']}\n"
            f"- *Your Answer:* {user_ans.upper()}\n"
            f"- *Correct Answer:* {question['correct_option'].upper()}\n"
            f"- *Explanation:* {explanation}\n"
        )

    # 5. Fetch Course Recommendations for weak topics
    course_recommendations = []
    if weak_topics:
        # Search courses for weak topics (cap total recommendations at 3 as per PDF)
        all_recommended_courses = []
        for topic in list(weak_topics)[:3]:  # query up to 3 weak topics
            courses = search_courses_tavily(topic)
            if courses:
                # Add the top course for this topic
                all_recommended_courses.append((topic, courses[0]))
                
        # Fill up to 3 total courses if we have more results
        if len(all_recommended_courses) < 3 and len(weak_topics) > 0:
            for topic in list(weak_topics):
                courses = search_courses_tavily(topic)
                for course in courses[1:]:
                    if len(all_recommended_courses) >= 3:
                        break
                    all_recommended_courses.append((topic, course))
                if len(all_recommended_courses) >= 3:
                    break

        for topic, course in all_recommended_courses[:3]:
            course_recommendations.append(
                f"- **{course['title']}** ({course['source']})\n  Link: {course['url']} *(Topic: {topic})*"
            )

    # 6. Format the complete report
    score_percentage = (correct_count / total_questions) * 100
    report = []
    report.append("## 📝 Exam Grading Report\n")
    report.append(f"**Score:** {correct_count}/{total_questions} ({score_percentage:.1f}%)\n")
    
    if correct_count == total_questions:
        report.append("🎉 Perfect score! Excellent understanding of the material.\n")
    else:
        report.append("### 🔍 Incorrect Answers & Explanations\n")
        report.append("\n".join(mistakes_feedback))
        
        if course_recommendations:
            report.append("### 📚 Recommended Courses\n")
            report.append("Based on the topics you missed, here are some recommended courses to strengthen your knowledge:\n")
            report.append("\n".join(course_recommendations))
            
    return "\n".join(report)
