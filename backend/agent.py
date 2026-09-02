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

GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant"
]

if groq_key:
    client = Groq(api_key=groq_key)
    MODEL_NAME = GROQ_MODELS[0]
elif openrouter_key:
    client = OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1")
    MODEL_NAME = "openai/gpt-oss-120b"
elif openai_key:
    client = OpenAI(api_key=openai_key)
    MODEL_NAME = "gpt-4o-mini"
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
            "description": "Get required documents checklist for an opportunity ID.",
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
    },
    {
        "type": "function",
        "function": {
            "name": "extract_scholarship_details_from_url",
            "description": "Scrape details directly from a web page URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to extract content from"}
                },
                "required": ["url"]
            }
        }
    }
]

SYSTEM_INSTRUCTIONS = """
You are ScholarAI, a scholarship advisor that outputs ONLY final structured results.

STRICT RULES (do not break these):
1. NEVER write greetings, intros, summaries, or closing remarks (no "Here are...", "I hope this helps", "Let me know if...", "Based on your profile...").
2. NEVER explain what you are about to do or what tool you are calling. Just call the tool silently.
3. Final answer must be ONLY markdown bullet points, nothing before or after them.
4. Each bullet must contain EXACTLY: **Title**, one-line Summary (max 15 words), Deadline, and a markdown link. Nothing else.
5. If no results found, output exactly one line: "No matching opportunities found." — nothing else.
6. Never output JSON, code blocks, disclaimers, or apologies.
7. Total response must not exceed 6 bullet points.
"""

def sanitize_output(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r'<br\s*/?>', ' ', text, flags=re.IGNORECASE)
    clean = re.sub(r'<[^>]+>', '', clean)
    return clean.strip()

def create_completion_with_fallback(client_instance, current_model, **kwargs):
    models_to_try = [current_model] + [m for m in GROQ_MODELS if m != current_model] if groq_key else [current_model]
    last_err = None
    for model in models_to_try:
        try:
            kwargs["model"] = model
            return client_instance.chat.completions.create(**kwargs), model
        except Exception as err:
            last_err = err
            err_str = str(err).lower()
            if any(k in err_str for k in ["404", "400", "decommissioned", "model_not_found"]):
                continue
            raise err
    raise last_err

def ask_ai(message: str, student: dict = None) -> str:
    global MODEL_NAME
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

            elif func_name == "get_required_documents":
                opp_id = args.get("opportunity_id")
                opp = next((i for i in all_opportunities if i["id"] == opp_id), None)
                raw_docs = get_required_documents(opp) if opp else []
                cleaned_docs = [re.sub(r'<br\s*/?>', ', ', str(doc), flags=re.IGNORECASE).strip(" ,") for doc in raw_docs]
                return json.dumps(cleaned_docs)

            elif func_name == "search_web":
                raw_res = search_web(args.get("query", message))
                if isinstance(raw_res, list) and raw_res:
                    cleaned = []
                    for item in raw_res:
                        title = item.get("title", "").strip()
                        url = item.get("url", "#")
                        content = item.get("content", "")
                        
                        content = re.sub(r'\|.*?\|', ' ', content)
                        content = re.sub(r'\s+', ' ', content).strip()
                        if len(content) > 180:
                            content = content[:180] + "..."
                            
                        if title and url:
                            cleaned.append(f"- **[{title}]({url})**\n  - {content}")
                    return "\n".join(cleaned[:6]) if cleaned else "No relevant web data found."
                return str(raw_res)

            elif func_name == "extract_scholarship_details_from_url":
                raw_res = extract_scholarship_details_from_url(args.get("url"))
                return json.dumps(raw_res)[:1000] if isinstance(raw_res, (dict, list)) else str(raw_res)[:1000]
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
            response, active_model = create_completion_with_fallback(
                client_instance=client,
                current_model=MODEL_NAME,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.0
            )
            MODEL_NAME = active_model
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
                return sanitize_output(response_message.content or "No response generated.")

        messages.append({
            "role": "user",
            "content": "Provide direct, concise, professional bullet points containing only title, deadline, and markdown link. No fluff."
        })
        
        final_response, _ = create_completion_with_fallback(
            client_instance=client,
            current_model=MODEL_NAME,
            messages=messages,
            temperature=0.0
        )
        return sanitize_output(final_response.choices[0].message.content or "Completed.")
        
    except Exception as err:
        return f"Agent Tool Loop Error: {str(err)}"