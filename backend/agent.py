import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI

from backend.tools import (
    search_opportunities,
    check_eligibility,
    get_required_documents,
    extract_scholarship_details_from_url
)
from backend.web_search import search_web
from backend.database import get_all_opportunities

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

groq_key = os.getenv("GROQ_API_KEY")
openrouter_key = os.getenv("OPENROUTER_API_KEY")
openai_key = os.getenv("OPENAI_API_KEY")
tavily_key = os.getenv("TAVILY_API_KEY")

GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-safeguard-20b"
]

if groq_key:
    client = Groq(api_key=groq_key)
    MODEL_NAME = GROQ_MODELS[0]
    PROVIDER = "groq"
elif openrouter_key:
    client = OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1")
    MODEL_NAME = GROQ_MODELS[0]
    PROVIDER = "openrouter"
elif openai_key:
    client = OpenAI(api_key=openai_key)
    MODEL_NAME = "gpt-4o-mini"
    PROVIDER = "openai"
else:
    raise RuntimeError("No API key configured in .env file.")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_opportunities",
            "description": "Search local database for scholarship opportunities matching degree and location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "degree": {"type": "string", "description": "Academic degree, e.g., BSCS or Undergraduate"},
                    "location": {"type": "string", "description": "Location or country, e.g., Pakistan"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_eligibility",
            "description": "Check if a student meets criteria for an opportunity ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "opportunity_id": {"type": "string", "description": "ID of the scholarship opportunity"}
                },
                "required": ["opportunity_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search web for active scholarships if database has few options.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        }
    }
]

SYSTEM_INSTRUCTIONS = """
You are ScholarAI, a professional scholarship search assistant.
Your ONLY job is to return relevant scholarship opportunities for the student.

STRICT OUTPUT RULES:
1. Output ONLY scholarship results as markdown bullet points starting with "- **Title:**".
2. No greeting, introduction, explanation, conclusion, recommendation, or extra text.
3. Each scholarship MUST use exactly this format:
- **Title:** Scholarship Name | **Summary:** Short summary | **Deadline:** Exact deadline | **Link:** [Official Source](URL)
4. If no matching verified scholarship is found, output exactly:
- No matching opportunities found.
"""

def sanitize_output(text: str) -> str:
    if not text:
        return "- No matching opportunities found."
    
    # Sirf woh lines extract karna jo markdown bullet points hein (- **Title:** ...)
    lines = text.split("\n")
    bullet_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- **Title:**") or stripped.startswith("* **Title:**"):
            bullet_lines.append(stripped)
            
    if bullet_lines:
        return "\n".join(bullet_lines)
    
    # Agar model ne standard bullets nahi diye lekin kuch text hai, toh fallback return karein
    return text.strip() or "- No matching opportunities found."

def create_completion_with_fallback(**kwargs):
    global client, MODEL_NAME, PROVIDER
    attempts = []
    if groq_key:
        for m in GROQ_MODELS:
            attempts.append(("groq", Groq(api_key=groq_key), m))

    if not attempts:
        raise RuntimeError("No valid Groq API key configured.")

    last_err = None
    for prov, cli, model in attempts:
        try:
            kwargs["model"] = model
            response = cli.chat.completions.create(**kwargs)
            client = cli
            MODEL_NAME = model
            PROVIDER = prov
            return response
        except Exception as err:
            last_err = err
            err_str = str(err).lower()
            if any(k in err_str for k in ["404", "400", "429", "decommissioned", "model_not_found", "rate_limit"]):
                continue
            raise err
    raise last_err

def ask_ai(message: str, student: dict = None) -> str:
    if not student:
        student = {}

    if not student.get("name"):
        student["name"] = "Nadir Hussain"
    if not student.get("degree"):
        student["degree"] = "BSCS"
    if not student.get("location"):
        student["location"] = "Pakistan"

    all_opportunities = get_all_opportunities()

    def execute_tool(func_name: str, args: dict):
        try:
            if func_name == "search_opportunities":
                raw_res = search_opportunities(
                    degree=args.get("degree") or student.get("degree"),
                    location=args.get("location") or student.get("location")
                )
                if isinstance(raw_res, list) and raw_res:
                    cleaned = []
                    for item in raw_res:
                        title = item.get("title", "Opportunity")
                        opp_id = item.get("id", "")
                        desc = item.get("description", "")
                        deadline = item.get("deadline", "Open")
                        cleaned.append(f"- **{title}** (ID: `{opp_id}`)\n  - **Summary**: {desc}\n  - **Deadline**: {deadline}")
                    return "\n".join(cleaned)
                return "No matching local opportunities found."

            elif func_name == "check_eligibility":
                opp_id = args.get("opportunity_id")
                opp = next((i for i in all_opportunities if i["id"] == opp_id), None)
                if not opp:
                    return json.dumps({"error": "Opportunity not found"})
                res = check_eligibility(student, opp)
                return json.dumps(res) if not isinstance(res, str) else res

            elif func_name == "search_web":
                raw_res = search_web(args.get("query", message))
                if isinstance(raw_res, list) and raw_res:
                    cleaned = []
                    for item in raw_res:
                        title = item.get("title", "").strip()
                        url = item.get("url", "#")
                        content = item.get("content", "")
                        if title and url:
                            cleaned.append(f"- **[{title}]({url})**\n  - {content}")
                    return "\n".join(cleaned[:6]) if cleaned else "No relevant web data found."
                return str(raw_res)
        except Exception as e:
            return json.dumps({"error": str(e)})
        return json.dumps({"error": "Invalid tool"})

    user_prompt = f"Student Profile: {json.dumps(student)}\nUser Query: {message}"
    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTIONS},
        {"role": "user", "content": user_prompt}
    ]

    try:
        for _ in range(5):
            response = create_completion_with_fallback(
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.0
            )
            response_message = response.choices[0].message

            if response_message.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": response_message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in response_message.tool_calls
                    ]
                })

                for tool_call in response_message.tool_calls:
                    fn_name = tool_call.function.name
                    try:
                        fn_args = json.loads(tool_call.function.arguments or "{}")
                    except Exception:
                        fn_args = {}
                    
                    result = execute_tool(fn_name, fn_args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result) if not isinstance(result, str) else result
                    })
            else:
                return sanitize_output(response_message.content)

        messages.append({
            "role": "user",
            "content": "Output ONLY the final scholarship bullet points in the exact required format. No conversational text."
        })
        
        final_response = create_completion_with_fallback(
            messages=messages,
            temperature=0.0
        )
        return sanitize_output(final_response.choices[0].message.content)
        
    except Exception as err:
        return f"- No matching opportunities found due to an error."