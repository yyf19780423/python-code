"""
7-crawl_directory_pages.py
----------------------------------
爬取特定目录下的所有页面
例如：只爬取 https://www.runoob.com/regexp/ 目录下的所有HTML文件
"""
import asyncio
import os
from urllib.parse import urljoin, urlparse
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator


class DirectoryCrawler:
    """目录级页面爬取器"""
    
    def __init__(self, directory_url, max_depth=1, max_pages=50, output_dir=None):
        """
        初始化爬虫
        
        Args:
            directory_url: 目录URL（如 https://www.runoob.com/regexp/）
            max_depth: 最大爬取深度（相对于目录）
            max_pages: 最大爬取页面数
            output_dir: 输出目录
        """
        self.directory_url = directory_url.rstrip('/') + '/'
        self.max_depth = max_depth
        self.max_pages = max_pages
        
        # 生成输出目录名
        if output_dir is None:
            parsed = urlparse(directory_url)
            dir_name = parsed.path.strip('/').replace('/', '_') or 'root'
            self.output_dir = f"crawled_{parsed.netloc}_{dir_name}"
        else:
            self.output_dir = output_dir
        
        # 爬取状态
        self.visited_urls = set()
        self.pending_urls = []
        self.crawled_pages = []
        
        # 解析基础信息
        parsed = urlparse(directory_url)
        self.base_domain = parsed.netloc
        self.base_scheme = parsed.scheme
        self.directory_path = parsed.path
        
        # 准备输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        print(f"📁 输出目录: {self.output_dir}")
        print(f"🎯 目标目录: {self.directory_url}")
    
    def is_in_target_directory(self, url):
        """检查URL是否在目标目录下"""
        try:
            parsed = urlparse(url)
            
            # 检查域名是否相同
            if parsed.netloc != self.base_domain:
                return False
            
            # 检查路径是否在目标目录下
            url_path = parsed.path
            return url_path.startswith(self.directory_path)
        except:
            return False
    
    def normalize_url(self, url):
        """标准化URL"""
        # 移除片段标识符
        url = url.split('#')[0]
        # 确保完整URL
        if url.startswith('//'):
            url = f"{self.base_scheme}:{url}"
        elif url.startswith('/'):
            url = f"{self.base_scheme}://{self.base_domain}{url}"
        return url
    
    def get_safe_filename(self, url):
        """生成安全的文件名"""
        parsed = urlparse(url)
        path = parsed.path.strip('/') or 'index'
        
        # 替换特殊字符
        filename = path.replace('/', '_')
        filename = ''.join(c if c.isalnum() or c in ('_', '-', '.') else '_' for c in filename)
        
        # 限制长度
        if len(filename) > 100:
            filename = filename[:100]
        
        if not filename.endswith('.md'):
            filename += '.md'
            
        return filename
    
    def save_page_content(self, url, result, depth):
        """保存页面内容到文件"""
        try:
            filename = self.get_safe_filename(url)
            filepath = os.path.join(self.output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# Source: {url}\n")
                f.write(f"**Depth**: {depth}\n")
                f.write(f"**Crawled at**: {result.timestamp if hasattr(result, 'timestamp') else 'N/A'}\n\n")
                f.write("---\n\n")
                f.write(result.markdown.raw_markdown if result.markdown else "No content")
            
            return filepath
        except Exception as e:
            print(f"❌ 保存失败 {url}: {e}")
            return None
    
    def extract_links_from_html(self, html_content, base_url):
        """从HTML内容中提取链接"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            links = []
            
            for link in soup.find_all('a', href=True):
                href = link.get('href', '').strip()
                if href and not href.startswith(('javascript:', 'mailto:', 'tel:')):
                    full_url = urljoin(base_url, href)
                    normalized_url = self.normalize_url(full_url)
                    
                    # 只保留目标目录下的链接
                    if self.is_in_target_directory(normalized_url):
                        links.append(normalized_url)
            
            return list(set(links))  # 去重
        except Exception as e:
            print(f"❌ 链接提取失败: {e}")
            return []
    
    async def crawl_directory(self):
        """开始爬取目录下的页面"""
        print(f"🚀 开始爬取目录: {self.directory_url}")
        print(f"📊 配置: 最大深度={self.max_depth}, 最大页面数={self.max_pages}")
        
        # 初始化爬虫
        browser_config = BrowserConfig(headless=True)
        crawl_config = CrawlerRunConfig(
            markdown_generator=DefaultMarkdownGenerator()
        )
        
        crawler = AsyncWebCrawler(config=browser_config)
        await crawler.start()
        
        try:
            # 从目录首页开始
            self.pending_urls.append((self.directory_url, 0))
            
            while self.pending_urls and len(self.crawled_pages) < self.max_pages:
                url, depth = self.pending_urls.pop(0)
                
                # 检查是否已访问
                if url in self.visited_urls:
                    continue
                
                # 检查深度限制
                if depth > self.max_depth:
                    continue
                
                self.visited_urls.add(url)
                
                print(f"🔍 [{depth}] 爬取: {url}")
                
                # 爬取页面
                result = await crawler.arun(url=url, config=crawl_config)
                
                if result.success:
                    print(f"✅ 成功: {url}")
                    
                    # 保存内容
                    filepath = self.save_page_content(url, result, depth)
                    
                    # 记录爬取结果
                    page_info = {
                        'url': url,
                        'depth': depth,
                        'filepath': filepath,
                        'markdown_length': len(result.markdown.raw_markdown) if result.markdown else 0,
                        'success': True
                    }
                    self.crawled_pages.append(page_info)
                    
                    # 提取新链接（如果未达到深度限制）
                    if depth < self.max_depth and result.html:
                        new_links = self.extract_links_from_html(result.html, url)
                        
                        for link in new_links:
                            if link not in self.visited_urls and link not in [u for u, _ in self.pending_urls]:
                                self.pending_urls.append((link, depth + 1))
                        
                        print(f"🔗 发现 {len(new_links)} 个新链接")
                    
                else:
                    print(f"❌ 失败: {url} - {result.error_message}")
                    self.crawled_pages.append({
                        'url': url,
                        'depth': depth,
                        'filepath': None,
                        'success': False,
                        'error': result.error_message
                    })
            
            # 生成报告
            self.generate_report()
            
        finally:
            await crawler.close()
    
    def generate_report(self):
        """生成爬取报告"""
        report_path = os.path.join(self.output_dir, "_CRAWL_REPORT.md")
        
        success_count = sum(1 for p in self.crawled_pages if p['success'])
        total_count = len(self.crawled_pages)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"# 目录爬取报告\n\n")
            f.write(f"**目标目录**: {self.directory_url}\n")
            f.write(f"**爬取页面**: {len(self.crawled_pages)} 个页面\n")
            f.write(f"**成功页面**: {success_count}/{total_count}\n")
            f.write(f"**最大深度**: {self.max_depth}\n\n")
            
            f.write("## 页面列表\n\n")
            for page in self.crawled_pages:
                status = "✅" if page['success'] else "❌"
                f.write(f"{status} [{page['depth']}] {page['url']}\n")
                if page['success'] and page['filepath']:
                    f.write(f"   📄 {page['filepath']} ({page['markdown_length']} chars)\n")
        
        print(f"📊 爬取完成! 成功: {success_count}/{total_count}")
        print(f"📄 报告已保存: {report_path}")


async def main():
    """主函数 - 修改这里的配置来爬取不同目录"""
    
    # 配置要爬取的目录
    directory_url = "https://www.runoob.com/git/"  # 修改为你要爬取的目录
    
    # 创建爬虫实例
    crawler = DirectoryCrawler(
        directory_url=directory_url,
        max_depth=1,      # 爬取深度（相对于目录）
        max_pages=30,     # 最大页面数
    )
    
    # 开始爬取
    await crawler.crawl_directory()


if __name__ == "__main__":
    asyncio.run(main())