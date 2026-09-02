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
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b"
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
            "name": "get_required_documents",
            "description": "Get required documents for a specific scholarship opportunity ID.",
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
You are ScholarAI, a scholarship advisor that outputs ONLY final structured results.

TOOL USAGE RULES:
1. If the user asks to find scholarships, ALWAYS call search_opportunities first.
2. If the user asks for eligibility or details, call check_eligibility and get_required_documents for EVERY opportunity found before giving your final answer.
3. Only call search_web if the local database search returns fewer than 3 results.

OUTPUT FORMAT RULES (strict):
1. NEVER write greetings, intros, summaries, or closing remarks.
2. NEVER explain what you are about to do or what tool you are calling. Just call the tool silently.
3. Final answer must be ONLY markdown bullet points, nothing before or after them.
4. Each bullet must be formatted EXACTLY like this, on separate lines:
    - **Title**
      - Summary: one line description
      - Deadline: date
      - Eligibility: ✅ Eligible / ❌ Not Eligible — short reason
      - Required Documents: list key documents needed
      - Link: [Official Source](url)
5. If no results found, output exactly one line: "No matching opportunities found."
6. Never output JSON, raw pipes (|), code blocks, disclaimers, or apologies.
7. Total response must not exceed 6 bullet points.
"""

def sanitize_output(text: str) -> str:
    if not text:
        return "- No matching opportunities found."

    clean = re.sub(r'<think>.*?</think>', '', text, flags=re.IGNORECASE | re.DOTALL)
    clean = re.sub(r'<tool_call>.*?</tool_call>', '', clean, flags=re.IGNORECASE | re.DOTALL)
    clean = re.sub(r'</?tool_call>|</?think>', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'<br\s*/?>', ' ', clean, flags=re.IGNORECASE)
    clean = re.sub(r'<[^>]+>', '', clean)
    clean = clean.strip()

    lines = clean.split("\n")
    bullet_lines = [l for l in lines if l.strip().startswith(("- **", "* **", "  - ", "  * "))]

    if bullet_lines:
        return "\n".join(bullet_lines)

    return clean or "- No matching opportunities found."

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
                        url = item.get("url", "#")
                        cleaned.append(f"- **{title}** (ID: `{opp_id}`)\n  - Summary: {desc}\n  - Deadline: {deadline}\n  - Link: [Official Source]({url})")
                    return "\n".join(cleaned)
                return "No matching local opportunities found."

            elif func_name == "check_eligibility":
                opp_id = args.get("opportunity_id")
                opp = next((i for i in all_opportunities if i["id"] == opp_id), None)
                if not opp:
                    return json.dumps({"error": "Opportunity not found"})
                res = check_eligibility(student, opp)
                return json.dumps(res) if not isinstance(res, str) else res

            elif func_name == "get_required_documents":
                opp_id = args.get("opportunity_id")
                opp = next((i for i in all_opportunities if i["id"] == opp_id), None)
                if not opp:
                    return json.dumps({"error": "Opportunity not found"})
                res = get_required_documents(opp)
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
                            cleaned.append(f"- **[{title}]({url})**\n  - Summary: {content}\n  - Link: [Official Source]({url})")
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
        for _ in range(12):
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

        final_response = create_completion_with_fallback(
            messages=messages,
            temperature=0.0
        )
        return sanitize_output(final_response.choices[0].message.content)

    except Exception as err:
        return f"- Error details: {str(err)}"