import os

def load_dotenv(dotenv_path=".env"):
    """
    Manually parses a .env file and sets environment variables.
    Avoids third-party dependencies like python-dotenv.
    """
    if not os.path.exists(dotenv_path):
        # Look in workspace root if not found in current execution path
        base_dir = os.path.dirname(os.path.abspath(__file__))
        dotenv_path = os.path.join(base_dir, ".env")
        if not os.path.exists(dotenv_path):
            return

    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip comments or empty lines
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    # Strip surrounding quotes if present
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    # Inject key-value pair into system environment
                    os.environ[key] = val
    except Exception as e:
        print(f"Warning: Failed to parse .env file: {e}")

# Run the dotenv loader
load_dotenv()

# Configuration variables
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini/gemini-1.5-flash")

def get_model():
    """
    Returns an initialized LangChain model wrapper based on LLM_MODEL config.
    """
    # Import inside function to avoid import errors if langchain-core is not fully installed
    # or if we are doing dry runs.
    if LLM_MODEL.startswith("gemini"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        model_name = LLM_MODEL.split("/", 1)[-1] if "/" in LLM_MODEL else LLM_MODEL
        return ChatGoogleGenerativeAI(model=model_name, google_api_key=GEMINI_API_KEY)
    elif LLM_MODEL.startswith("openai"):
        from langchain_openai import ChatOpenAI
        model_name = LLM_MODEL.split("/", 1)[-1] if "/" in LLM_MODEL else LLM_MODEL
        return ChatOpenAI(model=model_name, openai_api_key=OPENAI_API_KEY)
    else:
        # Default or fallback (using OpenAI-like interface or custom LangChain model mapping)
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=LLM_MODEL)
