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

# Active Groq Models prioritized for execution speed and tool-calling support
GROQ_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "llama-3.1-8b-instant"
]

if groq_key:
    client = Groq(api_key=groq_key)
    MODEL_NAME = GROQ_MODELS[0]
elif openrouter_key:
    client = OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1")
    MODEL_NAME = "meta-llama/llama-3.3-70b-instruct"
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
You are ScholarAI, an intelligent AI student opportunity advisor.

Your core duties:
- Suggest scholarships and opportunities matching student profiles.
- Check eligibility and provide clear document checklists with next steps.

Strict Rules:
1) Always issue tool calls with valid, properly formatted JSON arguments.
2) Check local database first, and use `search_web` if fewer than 5 eligible opportunities are retrieved.
3) Use CLEAN MARKDOWN ONLY. Absolutely NO HTML tags (do not write <br>, <div>, etc.).
4) NEVER write generic placeholders like 'YourName' or 'YOUR_NAME'. Dynamically extract the student's name from the provided Student Profile JSON (e.g., format sample filenames as `CNIC_NadirHussain.pdf`, `SOP_NadirHussain.pdf`). If no name is provided in the profile, default to 'NadirHussain'.
5) Inside Markdown tables, keep document lists separated by clean commas without HTML break tags to ensure proper cell wrapping.
6) Provide clean Markdown links for official portals.
7) CRITICAL FORMATTING RULE: When you receive data from any tool (whether Database records or Web Search results), NEVER dump raw JSON, dictionaries, or lists. You must always synthesize and present that data using clean Markdown bullet points or formatted tables, including the Title, description, and clickable Markdown links `[View Opportunity](URL)` where applicable.
"""

def sanitize_output(text: str) -> str:
    """Post-processing filter to strip any stray HTML tags."""
    if not text:
        return ""
    clean = re.sub(r'<br\s*/?>', ' ', text, flags=re.IGNORECASE)
    clean = re.sub(r'<[^>]+>', '', clean)
    return clean.strip()

def create_completion_with_fallback(client_instance, current_model, **kwargs):
    """Executes chat completion with dynamic fallback across available models."""
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
                    formatted_lines = ["Here are the matching local database opportunities:"]
                    for item in raw_res:
                        title = item.get("title", "Opportunity")
                        opp_id = item.get("id", "")
                        desc = item.get("description", "")
                        eligibility = item.get("eligibility", {})
                        deadline = item.get("deadline", "Open")
                        formatted_lines.append(
                            f"- **{title}** (ID: `{opp_id}`)\n"
                            f"  - **Description**: {desc}\n"
                            f"  - **Deadline**: {deadline}"
                        )
                    return "\n".join(formatted_lines)
                return "No matching local opportunities found."

            elif func_name == "check_eligibility":
                opp_id = args.get("opportunity_id")
                opp = next((i for i in all_opportunities if i["id"] == opp_id), None)
                if not opp:
                    return json.dumps({"error": "Opportunity not found in database"})
                eligibility_result = check_eligibility(student, opp)
                return json.dumps(eligibility_result) if not isinstance(eligibility_result, str) else eligibility_result

            elif func_name == "get_required_documents":
                opp_id = args.get("opportunity_id")
                opp = next((i for i in all_opportunities if i["id"] == opp_id), None)
                raw_docs = get_required_documents(opp) if opp else []
                
                cleaned_docs = []
                for doc in raw_docs:
                    s = str(doc)
                    s = re.sub(r'<br\s*/?>', ', ', s, flags=re.IGNORECASE)
                    cleaned_docs.append(s.strip(" ,"))
                return json.dumps(cleaned_docs)

            elif func_name == "search_web":
                raw_res = search_web(args.get("query", message))
                if isinstance(raw_res, list) and raw_res:
                    formatted_lines = ["Here are the live web search results:"]
                    for item in raw_res:
                        title = item.get("title", "Opportunity")
                        url = item.get("url", "#")
                        content = item.get("content", "")
                        
                        # Clean raw markdown table pipes and excess spaces from web snippets
                        content = re.sub(r'\|.*?\|', ' ', content)
                        content = re.sub(r'\s+', ' ', content).strip()
                        if len(content) > 250:
                            content = content[:250] + "..."
                            
                        if url:
                            formatted_lines.append(f"- **[{title}]({url})**\n  {content}")
                        else:
                            formatted_lines.append(f"- **{title}**: {content}")
                    return "\n".join(formatted_lines)[:3000]
                return str(raw_res)

            elif func_name == "extract_scholarship_details_from_url":
                raw_res = extract_scholarship_details_from_url(args.get("url"))
                res_str = json.dumps(raw_res) if isinstance(raw_res, (dict, list)) else str(raw_res)
                return res_str[:1000]
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
                temperature=0.1
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
            "content": "Provide final clear summary based on retrieved information using clean Markdown. Do NOT attempt any more tool calls."
        })
        
        final_response, _ = create_completion_with_fallback(
            client_instance=client,
            current_model=MODEL_NAME,
            messages=messages,
            temperature=0.1
        )
        return sanitize_output(final_response.choices[0].message.content or "Completed.")
        
    except Exception as err:
        return f"Agent Tool Loop Error: {str(err)}"