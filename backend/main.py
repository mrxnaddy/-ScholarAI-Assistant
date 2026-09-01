from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional

from backend.database import get_all_opportunities
from backend.tools import check_eligibility, get_required_documents, extract_scholarship_details_from_url
from backend.agent import ask_ai
from backend.web_search import search_web

app = FastAPI(title="ScholarAI API", version="1.0")

class StudentProfile(BaseModel):
    degree: Optional[str] = Field(default=None, description="Degree name e.g. BSCS")
    cgpa: Optional[float] = Field(default=None, description="Current CGPA e.g. 3.5")
    location: Optional[str] = Field(default=None, description="Country or location e.g. Pakistan")

class CheckEligibilityRequest(BaseModel):
    student: StudentProfile
    opportunity_id: str

class AskAIRequest(BaseModel):
    message: str
    student: Optional[StudentProfile] = None

class ExtractURLRequest(BaseModel):
    url: str

@app.get("/")
def home():
    return {"status": "online", "message": "ScholarAI Backend API active"}

@app.get("/opportunities")
def opportunities():
    return get_all_opportunities()

@app.post("/check-eligibility")
def eligibility(payload: CheckEligibilityRequest):
    opportunities_list = get_all_opportunities()
    opportunity = next(
        (item for item in opportunities_list if item["id"] == payload.opportunity_id),
        None
    )
    if opportunity is None:
        return {"error": "Opportunity not found"}

    student_data = payload.student.model_dump() if hasattr(payload.student, "model_dump") else payload.student.dict()
    result = check_eligibility(student_data, opportunity)

    return {
        "opportunity": opportunity.get("name", "Unknown"),
        "eligibility": result,
        "required_documents": get_required_documents(opportunity)
    }

@app.post("/ask-ai")
def ask_ai_endpoint(payload: AskAIRequest):
    student_dict = (
        payload.student.model_dump() if payload.student and hasattr(payload.student, "model_dump")
        else (payload.student.dict() if payload.student else {})
    )
    answer = ask_ai(payload.message, student_dict)
    return {"answer": answer}

@app.get("/search-scholarships")
def search_scholarships(q: str):
    return search_web(q)

@app.post("/extract-scholarship-details")
def extract_scholarship_details(payload: ExtractURLRequest):
    return extract_scholarship_details_from_url(payload.url)