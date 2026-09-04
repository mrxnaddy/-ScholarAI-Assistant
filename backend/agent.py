import os
import json
import re
import time
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
from google import genai
from google.genai import types

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
    client = genai.Client(api_key=gemini_key)
    MODEL_NAME = "gemini-2.5-flash"
else:
    raise RuntimeError("No GEMINI_API_KEY configured in .env or Streamlit secrets.")

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

    def tool_search_opportunities(degree: str = "BSCS", location: str = "Pakistan"):
        """Search local database for scholarship opportunities matching degree and location."""
        raw_res = search_opportunities(degree=degree, location=location)
        return raw_res if raw_res else "No matching local opportunities found."

    def tool_check_eligibility(opportunity_id: str):
        """Check if a student meets criteria for an opportunity ID."""
        opp = next((i for i in all_opportunities if i["id"] == opportunity_id), None)
        if not opp:
            return {"error": "Opportunity not found"}
        return check_eligibility(student, opp)

    def tool_get_required_documents(opportunity_id: str):
        """Get required documents for a specific scholarship opportunity ID."""
        opp = next((i for i in all_opportunities if i["id"] == opportunity_id), None)
        if not opp:
            return {"error": "Opportunity not found"}
        return get_required_documents(opp)

    def tool_search_web(query: str):
        """Search web for active scholarships if database has few options."""
        raw_res = search_web(query)
        return raw_res if raw_res else "No web results found."

    tools_list = [
        tool_search_opportunities,
        tool_check_eligibility,
        tool_get_required_documents,
        tool_search_web
    ]

    user_prompt = f"Student Profile: {json.dumps(student)}\nUser Query: {message}"

    max_retries = 4
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTIONS,
                    tools=tools_list,
                    temperature=0.2,
                ),
            )
            return sanitize_output(response.text)
        except Exception as err:
            err_str = str(err)
            if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                if attempt < max_retries - 1:
                    sleep_time = 3 * (attempt + 1)
                    time.sleep(sleep_time)
                    continue
            return f"- Server is experiencing high traffic or rate limits (Error 429/503). Please try again in a few moments. Details: {err_str}"