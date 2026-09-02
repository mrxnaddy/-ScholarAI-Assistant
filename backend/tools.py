from backend.database import get_all_opportunities
from backend.web_scraper import fetch_page_content
from backend.web_search import is_official_source


def search_opportunities(degree: str = None, location: str = None) -> list:
    opportunities = get_all_opportunities()
    if not degree and not location:
        return opportunities

    filtered = []
    for opp in opportunities:
        match_deg = True
        match_loc = True

        # Correct keys corresponding to opportunities.json
        allowed_degrees = opp.get("degrees") or opp.get("eligible_degrees") or []
        allowed_locations = opp.get("locations") or opp.get("eligible_countries") or []

        if degree:
            degree_str = str(degree).upper()
            # BSCS, BS CS, IT etc. mapped to BS category
            is_bs_input = any(tag in degree_str for tag in ["BS", "BACHELOR", "COMPUTER SCIENCE", "CS", "IT", "SE"])

            match_deg = any(
                degree_str in str(d).upper() or
                str(d).upper() in degree_str or
                (is_bs_input and str(d).upper() in ["BS", "BACHELORS", "UNDERGRADUATE"])
                for d in allowed_degrees
            )

        if location:
            location_str = str(location).lower()
            match_loc = any(
                location_str in str(loc).lower() or
                str(loc).lower() in location_str or
                str(loc).lower() == "all"
                for loc in allowed_locations
            )

        if match_deg and match_loc:
            filtered.append(opp)

    return filtered if filtered else opportunities


def check_eligibility(student: dict, opportunity: dict) -> dict:
    result = {}

    # 1. CGPA Check
    student_cgpa = student.get("cgpa")
    minimum_cgpa = opportunity.get("min_cgpa")

    if student_cgpa is None or minimum_cgpa is None:
        result["cgpa"] = "UNKNOWN"
    elif float(student_cgpa) >= float(minimum_cgpa):
        result["cgpa"] = "PASS"
    else:
        result["cgpa"] = "FAIL"

    # 2. Degree Check with key fallback and generic BS matching
    student_degree = str(student.get("degree") or "").upper()
    allowed_degrees = opportunity.get("degrees") or opportunity.get("eligible_degrees") or []

    if not student_degree:
        result["degree"] = "UNKNOWN"
    else:
        is_bs_student = any(tag in student_degree for tag in ["BS", "BACHELOR", "COMPUTER SCIENCE", "CS", "IT", "SE"])
        degree_matched = any(
            str(d).upper() in student_degree or
            student_degree in str(d).upper() or
            (is_bs_student and str(d).upper() in ["BS", "BACHELORS", "UNDERGRADUATE"])
            for d in allowed_degrees
        )
        result["degree"] = "PASS" if degree_matched else "FAIL"

   # Location Check Fix
    student_location = str(student.get("location") or "").lower().strip()
    allowed_locations = [str(loc).lower().strip() for loc in (opportunity.get("locations") or opportunity.get("eligible_countries") or [])]

    if not student_location:
        result["location"] = "UNKNOWN"
    else:
        location_matched = any(
            student_location in loc or
            loc in student_location or
            loc == "all" or
            "pakistan" in loc
            for loc in allowed_locations
        ) if allowed_locations else True
        result["location"] = "PASS" if location_matched else "FAIL"

    return result


def get_required_documents(opportunity):
    """
    Fetches document list and strips any HTML <br> tags into clean bullet text.
    """
    docs = []
    if isinstance(opportunity, dict):
        docs = opportunity.get("documents") or []
    elif isinstance(opportunity, str):
        # Handle string ID input
        all_opps = get_all_opportunities()
        target = next((o for o in all_opps if o.get("id") == opportunity), None)
        if target:
            docs = target.get("documents") or []

    cleaned_docs = []
    for doc in docs:
        if isinstance(doc, str):
            # Clean raw <br> tags coming from database string values
            cleaned_item = doc.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
            cleaned_docs.append(cleaned_item.strip())
        else:
            cleaned_docs.append(doc)

    return cleaned_docs


def verify_opportunity_source(opportunity: dict) -> dict:
    url = opportunity.get("official_source", "") or opportunity.get("link", "")

    if not url:
        return {"verified": False, "reason": "No official source provided"}

    if is_official_source(url):
        return {
            "verified": True,
            "source": url,
            "reason": "Source belongs to a recognized official domain"
        }

    return {
        "verified": False,
        "source": url,
        "reason": "Source is not from a recognized official domain"
    }


def extract_scholarship_details_from_url(url: str) -> dict:
    page_text = fetch_page_content(url)
    if "Error scraping page content" in page_text or "Failed to retrieve" in page_text:
        return {"status": "error", "url": url, "message": page_text}

    return {
        "status": "success",
        "url": url,
        "scraped_content_sample": page_text[:1500]
    }