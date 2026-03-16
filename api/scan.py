from http.server import BaseHTTPRequestHandler
import json
import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig

async def get_crawl_data(url):
    async with AsyncWebCrawler() as crawler:
        config = CrawlerRunConfig(
            screenshot=False, # Set to False for faster serverless execution
            word_count_threshold=10
        )
        result = await crawler.arun(url=url, config=config)
        return {
            "markdown": result.markdown[:5000], # Truncate for response limits
            "status": "success"
        }

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)
        url = data.get("url")

        if not url:
            self.send_response(400)
            self.end_headers()
            return

        # Run the async crawler in the synchronous handler
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(get_crawl_data(url))
        loop.close()

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())
        return