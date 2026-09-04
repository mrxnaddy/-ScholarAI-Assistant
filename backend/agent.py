import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
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

gemini_key = os.getenv("GEMINI_API_KEY")
if not gemini_key:
    try:
        gemini_key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        pass

if not gemini_key:
    gemini_key = os.getenv("OPENAI_API_KEY")

if gemini_key:
    client = OpenAI(
        api_key=gemini_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    MODEL_NAME = "gemini-1.5-flash"
    PROVIDER = "gemini"
else:
    raise RuntimeError("No GEMINI_API_KEY configured in .env or Streamlit secrets.")

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
You are ScholarAI, an expert scholarship and opportunity advisor. 
When a user asks to find scholarships or opportunities, provide rich, comprehensive, and fully detailed explanations for every matching entry.

OUTPUT FORMAT RULES:
1. Provide a clear, professional breakdown of each opportunity.
2. For each scholarship found, use structured markdown bullet points like this:
   - **[Scholarship Title]** (ID: `opp_id`)
     - **Summary**: Comprehensive description of the scholarship scope, benefits, and coverage.
     - **Deadline**: Exact application deadline date or open status.
     - **Eligibility**: ✅ Eligible / ❌ Not Eligible — clear breakdown matching student profile (CGPA, degree, location).
     - **Required Documents**: Detailed checklist of necessary documents (transcripts, statement of purpose, letters of recommendation, etc.).
     - **Link**: [Official Source Website](url)
3. Do not cut short the details. Make sure all gathered tool data is fully expanded and formatted nicely.
"""

def sanitize_output(text: str) -> str:
    if not text:
        return "- No matching opportunities found."

    clean = re.sub(r'<think>.*?</think>', '', text, flags=re.IGNORECASE | re.DOTALL)
    clean = re.sub(r'<tool_call>.*?</tool_call>', '', clean, flags=re.IGNORECASE | re.DOTALL)
    clean = re.sub(r'</?tool_call>|</?think>', '', clean, flags=re.IGNORECASE)
    clean = clean.strip()
    return clean or "- No matching opportunities found."

def create_completion_with_fallback(**kwargs):
    global client, MODEL_NAME, PROVIDER
    try:
        kwargs["model"] = MODEL_NAME
        response = client.chat.completions.create(**kwargs)
        return response
    except Exception as err:
        raise err

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
                return json.dumps(raw_res) if raw_res else "No matching local opportunities found."

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
                return json.dumps(raw_res) if raw_res else "No web results found."
        except Exception as e:
            return json.dumps({"error": str(e)})
        return json.dumps({"error": "Invalid tool"})

    user_prompt = f"Student Profile: {json.dumps(student)}\nUser Query: {message}"
    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTIONS},
        {"role": "user", "content": user_prompt}
    ]

    try:
        for _ in range(8):
            response = create_completion_with_fallback(
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.2
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
            temperature=0.2
        )
        return sanitize_output(final_response.choices[0].message.content)

    except Exception as err:
        return f"- Error details: {str(err)}"