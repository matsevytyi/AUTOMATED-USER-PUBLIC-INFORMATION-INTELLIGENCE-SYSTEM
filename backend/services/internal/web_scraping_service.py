import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter,BM25ContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

import re

from backend.utils.config import Config

class WebScrapingService:
    
    def __init__(self, min_words_threshold=2):
        
        self.browser_config = BrowserConfig(
            headless=True,  
            verbose=False,
            user_agent_mode="custom",
            user_agent_generator_config={"user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"}
        )
        
        self.min_word_threshold = min_words_threshold
        # thresholds for adaptive fallback
        self.primary_bm25_threshold = 0.97
        self.fallback_bm25_threshold = 0.2
        self.enable_pruning_fallback = True
    
    # ====================== Public API ======================
        
    def smart_parse_website(self, url, user_query):
        
        """
        This function takes a URL and a user query, parses the website with AI (using the crawler service),
        and then formats the output into a JSON object.

        The output JSON object is a dictionary with the following keys:
        - raw: the raw markdown text of the website
        - fit: a list of strings, each representing a "fit" of the user query to the website text.

        If the user query is not found in the website text, the function returns None.
        """
        
        raw, fit = self._get_markdown(url, user_query)
        if not fit:
            fit = raw
        elif len(fit) < 10*self.min_word_threshold:
            fit = raw
        
        if isinstance(fit, list):
            return [self._answer_to_json(fit_text) if fit_text else None for fit_text in fit]
        else:
            return self._answer_to_json(fit)
        
    
    # ====================== Private API (may be used) ======================
        

    def _answer_to_json(self, raw_text):
        """
        Converts a raw markdown text to a JSON object.

        The JSON object will have the following keys:
        - name: the name of the link (if present)
        - link: the link URL (if present)
        - title: the title of the page (if present)
        - description: the description of the page (if present)
        - sections: a list of dictionaries, each with the following keys:
            - heading: the heading of the section (in **bold**)
            - content: a list of strings, each representing a line of content in the section
        - resources: a list of dictionaries, each with the following keys:
            - name: the name of the resource (if present)
            - link: the link URL of the resource (if present)

        The function will return None if the input is None or empty.
        """
        
        if not raw_text:
            return None
        
        # name and link from markdown-style link
        result = re.sub(r'\(http[s]?://\S+\)', '', raw_text)
        result = re.sub(r'http[s]?://\S+', '', result)
        result = result.replace('\n', '')
        result = result.replace('*', '')
        result = result.replace('#', '')
        result = re.sub(r'\]', '', result)
        result = re.sub(r'\[', '', result)
        result = re.sub(r'\(javascript:void\\\(0\\\);\)', '', result)

        return result
        
    def _get_markdown(self, url, user_query, enable_cache=False):
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
            used_func_alias = self._fetch_multiple_markdown
        else:
            used_func_alias = self._fetch_markdown
        
        loop = asyncio.new_event_loop()
        
        return loop.run_until_complete(
            used_func_alias(url, user_query, enable_cache)
            )
        
    
    # ====================== Private API ======================    

    async def _fetch_markdown(self, url: str, user_query, enable_cache=False):
        # Try primary BM25 threshold first, then fallback thresholds (adaptive)
        thresholds = [self.primary_bm25_threshold, self.fallback_bm25_threshold]

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            last_err = None
            for i, th in enumerate(thresholds):
                run_config = CrawlerRunConfig(
                    cache_mode=CacheMode.ENABLED if enable_cache else CacheMode.DISABLED,
                    markdown_generator=DefaultMarkdownGenerator(
                        content_filter=BM25ContentFilter(user_query=user_query, bm25_threshold=th)
                    ),
                )

                try:
                    result = await crawler.arun(url=url, config=run_config)
                    if result is None or not hasattr(result, 'markdown') or result.markdown is None:
                        last_err = f"No result/markdown for {url} at bm25={th}"
                        print(last_err)
                        # try next threshold
                        continue

                    fit = result.markdown.fit_markdown or ''
                    
                    if len(fit) >= self.min_word_threshold:
                        if i == 0:
                            # primary succeeded
                            return result.markdown.raw_markdown, fit
                        else:
                            print(f"[INFO] Primary BM25 missed; fallback bm25={th} succeeded for {url}")
                            return result.markdown.raw_markdown, fit
                    else:
                        print(f"Not enough words found at bm25={th} (found {len(fit)})")
                        continue
                except Exception as e:
                    print(e)
                    continue

            # If BM25 passes didn't return enough, optionally try a pruning/no-filter pass
            if self.enable_pruning_fallback:
                print("trying pruning fallback")
                try:
                    print(f"[INFO] BM25 fallbacks failed for {url}; trying PruningContentFilter")
                    run_config = CrawlerRunConfig(
                        cache_mode=CacheMode.ENABLED if enable_cache else CacheMode.DISABLED,
                        markdown_generator=DefaultMarkdownGenerator(
                            content_filter=PruningContentFilter()
                        ),
                    )
                    result = await crawler.arun(url=url, config=run_config)
                    if result is None or not hasattr(result, 'markdown') or result.markdown is None:
                        print(f"[ERROR] Pruning fallback returned no markdown for {url}")
                        return None, None

                    fit = result.markdown.fit_markdown or ''
                    if len(fit) >= self.min_word_threshold:
                        print(f"[INFO] Pruning fallback succeeded for {url}")
                        return result.markdown.raw_markdown, fit
                    else:
                        print(f"[ERROR] Pruning fallback found too little content ({len(fit)}) for {url}")
                        return None, None
                except Exception as e:
                    print(f"[ERROR] Exception while pruning fallback for {url}: {e}")
                    return None, None

            print(f"[ERROR] Exception while crawling {url}: {last_err}")
            return None, None

    async def _fetch_multiple_markdown(self, urls: list, user_query, enable_cache=False):
        
        
        run_config = CrawlerRunConfig(
            
            cache_mode=CacheMode.ENABLED if enable_cache else CacheMode.DISABLED,
            
            markdown_generator=DefaultMarkdownGenerator(
                content_filter=BM25ContentFilter(user_query=user_query, bm25_threshold=0.95) # was 0.97
            ),
        )
        
        async with AsyncWebCrawler(config=self.browser_config) as crawler:

            results = await crawler.arun_many(
                urls=urls,
                config=run_config
            )

            # Normalize results list by removing None entries
            normalized = []
            for res in results:
                if res is None or not hasattr(res, 'markdown') or res.markdown is None:
                    normalized.append(None)
                else:
                    normalized.append(res)

            raw_markdowns = []
            fit_markdowns = []

            # For any entry that is missing or too short, run the single-url fallback fetch
            for idx, res in enumerate(normalized):
                url = urls[idx]
                if res is None:
                    # fallback to single fetch which has adaptive fallback
                    rm, fm = await self.fetch_markdown(url, user_query, enable_cache=enable_cache)
                    raw_markdowns.append(rm or "")
                    fit_markdowns.append(fm or None)
                    continue

                raw = res.markdown.raw_markdown if res is not None else ""
                fit = res.markdown.fit_markdown if res is not None else ""

                if not fit or len(fit) < self.min_word_threshold:
                    # try adaptive single fetch for this url
                    rm, fm = await self.fetch_markdown(url, user_query, enable_cache=enable_cache)
                    raw_markdowns.append(rm or raw)
                    fit_markdowns.append(fm or None)
                else:
                    raw_markdowns.append(raw)
                    fit_markdowns.append(fit)

            return raw_markdowns, fit_markdowns
        
web_scraping_service_singletone = WebScrapingService()


