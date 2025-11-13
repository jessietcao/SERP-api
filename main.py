# main.py
from fastapi import FastAPI, Query
from scraper import get_serp_results

app = FastAPI(title="Custom SERP API", version="0.1")

@app.get("/search")
def search(q: str = Query(..., description="Search query"), limit: int = 5):
    """
    Run a DuckDuckGo search and return top results.
    Example: /search?q=ai+tools&limit=5
    """
    results = get_serp_results(q, max_results=limit)
    return {"query": q, "results": results}

