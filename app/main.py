from fastapi import FastAPI, Query
from app.scraper import get_serp_results

app = FastAPI(title="Custom SERP API", version="0.2")

@app.get("/search")
def search(
    q: str = Query(..., description="Search query"),
    limit: int = 5,
    engine: str = Query("duckduckgo", description="Search engine")
):
    """
    Perform a search on the specified search engine and return results.
    Example: /search?q=ai+tools&engine=brave&limit=5
    """
    results = get_serp_results(q, engine=engine, max_results=limit)
    return {"engine": engine, "query": q, "results": results}
