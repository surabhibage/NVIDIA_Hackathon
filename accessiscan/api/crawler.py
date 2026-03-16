import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig


async def crawl(url):

    async with AsyncWebCrawler() as crawler:

        config = CrawlerRunConfig(
            screenshot=True,
            word_count_threshold=10
        )

        result = await crawler.arun(url=url, config=config)

        return {
            "markdown": result.markdown,
            "screenshot": result.screenshot
        }


def crawl_sync(url):
    return asyncio.run(crawl(url))