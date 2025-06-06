import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter,BM25ContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

class CrawlerService:
    def __init__(self, min_words_threshold=17):
        self.browser_config = BrowserConfig(
            headless=True,  
            verbose=False,
            user_agent_mode="custom",
            user_agent_generator_config={"user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"}
    
        )
        self.min_word_threshold = min_words_threshold
        

    async def fetch_markdown(self, url: str, user_query, enable_cache=False):
        
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.ENABLED if enable_cache else CacheMode.DISABLED,
            markdown_generator=DefaultMarkdownGenerator(
                content_filter=BM25ContentFilter(user_query=user_query, bm25_threshold=0.97)
            ),
        )
        

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            try:
                result = await crawler.arun(url=url, config=run_config)

                if result is None:
                    print(f"[ERROR] Crawling failed: No result for {url}")
                    return None, None

                if not hasattr(result, 'markdown') or result.markdown is None:
                    print(f"[ERROR] Crawling failed: No markdown attribute for {url}")
                    return None, None
                
                if len(result.markdown.fit_markdown) < self.min_word_threshold:
                    raise Exception("Not enough words found, skipping the link")

                return result.markdown.raw_markdown, result.markdown.fit_markdown

            except Exception as e:
                print(f"[ERROR] Exception while crawling {url}: {e}")
                return None, None

    async def fetch_multiple_markdown(self, urls: list, user_query, enable_cache=False):
        
        
        run_config = CrawlerRunConfig(
            
            cache_mode=CacheMode.ENABLED if enable_cache else CacheMode.DISABLED,
            
            markdown_generator=DefaultMarkdownGenerator(
                content_filter=BM25ContentFilter(user_query=user_query, bm25_threshold=0.97)
            ),
        )
        
        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            
            results = await crawler.arun_many(
                urls=urls,
                config=run_config
            )
            
            for res in results:
                if res is None or not hasattr(res, 'markdown'):
                    results.remove(res)
            
            raw_markdowns = [res.markdown.raw_markdown if res is not None else "" for res in results]
            fit_markdowns = [res.markdown.fit_markdown if res is not None else "" for res in results]
            
            fit_markdowns = [markdown if len(markdown) > self.min_word_threshold else None for markdown in fit_markdowns]

            return raw_markdowns, fit_markdowns

    def get_markdown(self, url, user_query, enable_cache=False):
        """
        Run either fetch_markdown or fetch_multiple_markdown, depending on whether
        the argument `url` is a list or not. This is a convenience function to allow
        for simpler use.

        Args:
            user_query (str): The query to BM25 filter the results with.

        Returns:
            tuple: A tuple of two elements. The first element is a list of raw markdown
            strings, and the second element is a list of markdown strings that fit the
            user query according to the BM25 filter.
        """

        
        if isinstance(url, list):
            used_func_alias = self.fetch_multiple_markdown
        else:
            used_func_alias = self.fetch_markdown
        
        loop = asyncio.new_event_loop()
        
        return loop.run_until_complete(
            used_func_alias(url, user_query, enable_cache)
            )
        
crawler_service = CrawlerService()
