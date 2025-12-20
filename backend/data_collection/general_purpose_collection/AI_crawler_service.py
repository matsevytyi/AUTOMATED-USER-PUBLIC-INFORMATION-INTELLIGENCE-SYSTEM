import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter,BM25ContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from backend.utils.config import Config

class CrawlerService:
    def __init__(self, min_words_threshold=1):
        self.browser_config = BrowserConfig(
            headless=True,  
            verbose=False,
            user_agent_mode="custom",
            user_agent_generator_config={"user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"}
        )
        self.min_word_threshold = min_words_threshold
        # thresholds for adaptive fallback
        self.primary_bm25_threshold = Config.BM_25_PRIMARY_THRESHOLD
        self.fallback_bm25_threshold = Config.BM_25_SECONDARY_THRESHOLD
        self.enable_pruning_fallback = Config.USE_PRUNING_FILTER_BACKUP
        

    async def fetch_markdown(self, url: str, user_query, enable_cache=False):
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
                        last_err = f"Not enough words found at bm25={th} (found {len(fit)})"
                        # continue to next threshold
                        continue
                except Exception as e:
                    last_err = str(e)
                    continue

            # If BM25 passes didn't return enough, optionally try a pruning/no-filter pass
            if self.enable_pruning_fallback:
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

    async def fetch_multiple_markdown(self, urls: list, user_query, enable_cache=False):
        
        
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
