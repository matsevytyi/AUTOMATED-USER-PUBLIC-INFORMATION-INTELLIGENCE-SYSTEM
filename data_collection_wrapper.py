from darkdump import darkdump
# import facebook
# import general scraping



def collect_data(search_request, use_general=True, use_facebook=False, use_darknet=False):
    
    results = []
    
    if use_darknet:
        darknet_data = darkdump.Darkdump().crawl(query=search_request, amount=100, scrape_sites=True, extract_full_text=True)
    
    return darknet_data

a = collect_data("marketplaces", use_darknet=True)
print(a)