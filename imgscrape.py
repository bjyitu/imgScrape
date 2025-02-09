import sys
import os
import subprocess
import argparse
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from datetime import datetime
from PIL import Image
from io import BytesIO

def create_save_folder():
    """创建保存目录"""
    img_dir = "img"
    os.makedirs(img_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(img_dir, timestamp)
    os.makedirs(save_path, exist_ok=True)
    return save_path

def get_image_dimensions(url):
    """获取图片实际尺寸"""
    try:
        response = requests.get(url, stream=True, timeout=10)
        if response.status_code == 200:
            image = Image.open(BytesIO(response.content))
            return image.size
        return (0, 0)
    except Exception as e:
        print(f"尺寸获取失败: {url} - {str(e)}")
        return (0, 0)

def download_image(url, save_path):
    """下载并保存图片"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": urlparse(url).scheme + "://" + urlparse(url).netloc  # 添加 Referer 头
    }
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=15)
        if response.status_code == 200:
            # 去除URL参数并保留文件名及扩展名
            filename_with_ext = os.path.basename(url.split('?')[0])
            if not filename_with_ext:
                # 如果没有从 URL 中提取到文件名，生成一个带时间戳的文件名，并尝试从响应头推测扩展名
                content_type = response.headers.get('Content-Type')
                if content_type == 'image/jpeg':
                    ext = '.jpg'
                elif content_type == 'image/png':
                    ext = '.png'
                elif content_type == 'image/webp':
                    ext = '.webp'
                else:
                    ext = '.jpg'  # 默认使用 .jpg
                filename_with_ext = f"image_{datetime.now().strftime('%f')}{ext}"

            save_path = os.path.join(save_path, filename_with_ext)
            #print(f"准备保存图片到: {save_path}")  # 添加日志信息
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            #print(f"图片保存成功: {save_path}")  # 添加日志信息
            return True
        else:
            print(f"下载失败: {url} - 状态码: {response.status_code}")
            return False
    except Exception as e:
        print(f"下载失败: {url} - {str(e)}")
        return False

def extract_image_url(img_tag, base_url):
    """从img标签中提取最优图片URL"""
    attrs = ['data-src', 'data-original', 'src']
    for attr in attrs:
        img_url = img_tag.get(attr)
        if img_url:
            return urljoin(base_url, img_url)
    
    # 处理srcset属性
    srcset = img_tag.get('srcset')
    if srcset:
        first_part = srcset.split(',')[0].strip()
        img_url = first_part.split(' ')[0]
        return urljoin(base_url, img_url)
    
    return None


def scrape_images(target_url, min_width, save_path, total_pages, current_page=1, visited=None):
    """主抓取函数"""
    if visited is None:
        visited = set()
    
    # 检查目标 URL 是否包含页码标记，如果没有则添加 ?page=1
    parsed_url = urlparse(target_url)
    query = parse_qs(parsed_url.query)
    if 'page' not in query:
        query['page'] = '1'
        target_url = urlunparse(parsed_url._replace(query=urlencode(query, doseq=True)))
    
    if target_url in visited:
        return
    visited.add(target_url)
    if current_page > total_pages:
        print(f"已达到指定的总页数 {total_pages}，停止请求。")
        return
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        response = requests.get(target_url, headers=headers, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        # 只查找<div class="article-fulltext">中的img标签
        article_div = soup.find('div', class_='article-fulltext')
        if article_div:
            img_tags = article_div.find_all("img")
        else:
            img_tags = []

        #查找所有img标签
        #img_tags = soup.find_all("img")
        
        print(f"找到的图片URL数量: {len(img_tags)}")
        for img in img_tags:
            img_url = extract_image_url(img, target_url)
            if not img_url:
                continue
            print(f"发现图片URL: {img_url}")  # 打印发现的图片URL
            width, height = get_image_dimensions(img_url)
            
            #if width > min_width:
            if download_image(img_url, save_path):
                print(f"成功下载: {os.path.basename(img_url)} ({width}x{height})")
            else:
                print(f"下载失败: {img_url}")
        
        # 查找下一页（优先rel-next，其次包含page参数的链接）
        next_page_link = soup.find('a', rel='next')
        if not next_page_link:
            next_page_link = soup.find('a', string=lambda t: t and '下一页' in t)
        
        if next_page_link:
            next_url = urljoin(target_url, next_page_link.get('href'))
            scrape_images(next_url, min_width, save_path, total_pages, current_page + 1, visited)
        else:
            # 尝试自动生成分页URL
            parsed_url = urlparse(target_url)
            query = parse_qs(parsed_url.query)
            if 'page' in query:
                current_page_num = int(query['page'][0])
                query['page'] = str(current_page_num + 1)
                next_url = urlunparse(parsed_url._replace(query=urlencode(query, doseq=True)))
                scrape_images(next_url, min_width, save_path, total_pages, current_page + 1, visited)
                
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            print(f"分页结束: {target_url}")
        else:
            print(f"抓取过程中发生HTTP错误: {str(e)}")
    except Exception as e:
        print(f"抓取过程中发生错误: {str(e)}")

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(
        description="网页图片抓取工具",
        epilog="示例: python scraper.py https://example.com 800 10  # 800是最小宽度，目前对尺寸的检查已停用。指定了article-fulltext这个div内的图片才下载，这个可以修改成目标网站的，也可以停用。其中10为总页数"
    )
    parser.add_argument("url", help="目标网页URL")
    parser.add_argument("--min-width", type=int, default=10, help="最小图片宽度要求")
    parser.add_argument("total_pages", type=int, help="指定的总页数")
    
    args = parser.parse_args()
    
    save_path = create_save_folder()
    visited = set()
    scrape_images(args.url, args.min_width, save_path, args.total_pages, visited=visited)