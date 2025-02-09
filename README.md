# imgScrape
抓取指定链接内图片，指定总页数可自动抓取所有页码内图片

示例: python scraper.py https://example.com 800 10  
- 800是最小宽度，目前对尺寸的检查已停用。
- 指定了article-fulltext这个div内的图片才下载，这个可以修改成目标网站的，也可以停用。
- 10为总页数
