import asyncio
import base64
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig

app = FastAPI()

# Allow your HTML frontend to call this API from any origin (localhost dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

class CrawlRequest(BaseModel):
    url: str

@app.post("/crawl")
async def crawl(req: CrawlRequest):
    if not req.url.startswith("http"):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    try:
        async with AsyncWebCrawler() as crawler:
            config = CrawlerRunConfig(
                screenshot=True,          # captures viewport as PNG
                word_count_threshold=10,  # skip tiny text blocks
            )
            result = await crawler.arun(url=req.url, config=config)

        # Screenshot comes back as bytes — encode to base64 so JSON can carry it
        screenshot_b64 = None
        if result.screenshot:
            screenshot_b64 = base64.b64encode(result.screenshot).decode("utf-8")

        return {
            "success": True,
            "url": req.url,
            "markdown": result.markdown or "",
            "html": result.html or "",
            "screenshot_b64": screenshot_b64,      # data:image/png;base64,<this>
            "links": result.links or {},
            "metadata": {
                "title": result.metadata.get("title", "") if result.metadata else "",
                "description": result.metadata.get("description", "") if result.metadata else "",
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Run with: uvicorn main:app --reload --port 8000