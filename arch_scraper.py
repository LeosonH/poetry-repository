"""
Poetry Foundation Theme Scraper
Scrapes poems from poetryfoundation.org by theme and saves them as text files.
"""

import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import time
import re
from pathlib import Path

class PoetryFoundationScraper:
    def __init__(self, base_url="https://www.poetryfoundation.org"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def get_page(self, url):
        """Fetch a webpage with error handling."""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def clean_filename(self, name):
        """Clean a string to be used as a folder/file name."""
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        name = re.sub(r'\s+', '_', name)
        return name.strip('_')
    
    def extract_poems_from_theme(self, theme_url):
        """Extract poem links from a theme page."""
        print(f"Examining theme page: {theme_url}")
        response = self.get_page(theme_url)
        if not response:
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        poems = []
        
        # Look for poem links using current Poetry Foundation selectors
        # Updated selectors based on current site structure
        poem_selectors = [
            'a.link-red[href*="/poems"]',
            'a.link-underline-on[href*="/poems"]',
            'h3 a[href*="/poems"]',
            'a[href*="/poetrymagazine/poems/"]',
            'a[href*="/poems/"]'
        ]
        
        for selector in poem_selectors:
            elements = soup.select(selector)
            for element in elements:
                if element.name == 'a':
                    link = element
                else:
                    link = element.find_parent('a')
                
                if link and link.get('href'):
                    href = link.get('href')
                    if '/poems/' in href:
                        # Get title from the link text or nested elements
                        poem_title = link.get_text(strip=True)
                        if not poem_title or len(poem_title) < 3:
                            continue
                        
                        # Skip navigation elements and common non-poem text
                        skip_words = ['more', 'browse', 'search', 'filter', 'sort', 'next', 'previous', 'page']
                        if any(word in poem_title.lower() for word in skip_words):
                            continue
                            
                        full_url = urllib.parse.urljoin(self.base_url, href)
                        # Avoid duplicates
                        if not any(p['url'] == full_url for p in poems):
                            poems.append({
                                'title': poem_title,  # Don't clean filename here, do it later
                                'url': full_url
                            })
        
        print(f"Found {len(poems)} poems")
        return poems
    
    def save_poem(self, poem_content, folder_path, filename):
        """Save poem content to a text file."""
        try:
            print(f"  Saving: {filename}")
            
            if not poem_content or len(poem_content.strip()) < 10:
                print(f"  Skipped: {filename} (content too short or empty)")
                return False
            
            file_path = folder_path / f"{filename}.txt"
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(poem_content)
            
            word_count = len(poem_content.split())
            print(f"  ✓ Saved: {filename}.txt ({word_count} words)")
            return True
            
        except Exception as e:
            print(f"  ✗ Error saving {filename}: {e}")
            return False
    
    def scrape_poem_content(self, poem_url, poem_title):
        """Scrape content from a single poem page."""
        print(f"\nScraping poem: {poem_title}")
        print(f"URL: {poem_url}")
        
        response = self.get_page(poem_url)
        if not response:
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # First, try to get the actual poem title from the page
        actual_title = poem_title
        title_selectors = [
            'h1.c-feature-hd',
            'h1[class*="title"]',
            '.c-feature-hd h1',
            'h1.poem-title',
            'h1',
            '.o-title h1'
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title_text = title_elem.get_text(strip=True)
                if title_text and len(title_text) > 1:
                    actual_title = title_text
                    break
        
        # Try different selectors commonly used by Poetry Foundation
        poem_content = None
        
        # Look for poem content in common containers - updated selectors
        selectors = [
            'div.o-poem',
            'div[class*="poem"][class*="text"]', 
            'div.c-feature-bd',
            'div.poem-text',
            'div.o-poems',
            'div[data-view="PoemView"]',
            'pre.poem',
            'pre',
            '.c-feature-bd .o-poem',
            '.poem-body',
            '[class*="poem-content"]'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                # Remove any nested author/title information
                author_elements = element.find_all(['a', 'span'], href=True)
                for auth_elem in author_elements:
                    if '/poets/' in str(auth_elem.get('href', '')):
                        auth_elem.decompose()
                
                poem_content = element.get_text(separator='\n', strip=True)
                if poem_content and len(poem_content) > 30:
                    break
        
        # Fallback: try to find the main content
        if not poem_content:
            main_content = soup.select_one('main, article, .main-content, .content')
            if main_content:
                poem_content = main_content.get_text(separator='\n', strip=True)
        
        # Extract author information if available
        author = "Unknown Author"
        # Updated selectors for Poetry Foundation's current structure
        author_selectors = [
            'span.c-txt_attribution',
            'div.c-feature-sub', 
            'a[href*="/poets/"]',
            '.c-feature-bd a[href*="/poets/"]',
            '.o-author a',
            '.c-feature-hd + .c-feature-sub',
            'div.author',
            '.poem-author',
            '[class*="author"]',
            'span[class*="by"]'
        ]
        
        for selector in author_selectors:
            author_elem = soup.select_one(selector)
            if author_elem:
                author_text = author_elem.get_text(strip=True)
                # Clean up common prefixes
                author_text = re.sub(r'^(by|author:?)\s*', '', author_text, flags=re.IGNORECASE)
                if author_text and len(author_text) > 1:
                    author = author_text
                    break
        
        if poem_content:
            # Clean up the poem content
            lines = poem_content.split('\n')
            cleaned_lines = []
            
            for line in lines:
                line = line.strip()
                # Skip empty lines at the beginning
                if not cleaned_lines and not line:
                    continue
                # Skip lines that are likely navigation or metadata
                skip_patterns = ['browse poems', 'more poems', 'related poems', 'share this poem']
                if any(pattern in line.lower() for pattern in skip_patterns):
                    continue
                cleaned_lines.append(line)
            
            # Rejoin and format the content nicely
            cleaned_content = '\n'.join(cleaned_lines)
            formatted_content = f"Title: {actual_title}\nAuthor: {author}\n\n{cleaned_content}"
            return formatted_content
        
        return None
    
    def scrape_poems_by_theme(self, theme_name):
        """Main method to scrape poems from a specific theme."""
        print(f"Starting Poetry Foundation scraper for theme: {theme_name}")
        
        # Construct theme URL - Poetry Foundation uses categories URL structure
        theme_url_patterns = [
            f"https://www.poetryfoundation.org/categories/{theme_name.lower().replace(' ', '-')}"
        ]
        
        poems = []
        for theme_url in theme_url_patterns:
            print(f"Trying URL pattern: {theme_url}")
            poems = self.extract_poems_from_theme(theme_url)
            if poems:
                break
        
        if not poems:
            print(f"No poems found for theme '{theme_name}'. Try a different theme name.")
            return
        
        # Create folder for this theme
        theme_folder = Path('poems') / self.clean_filename(theme_name)
        theme_folder.mkdir(parents=True, exist_ok=True)
        
        total_poems_saved = 0
        
        # Process each poem
        for i, poem in enumerate(poems, 1):
            print(f"\n=== Processing poem {i}/{len(poems)} ===")
            
            # Check if already exists
            file_path = theme_folder / f"{poem['title']}.txt"
            if file_path.exists():
                print(f"  Skipping existing: {poem['title']}.txt")
                continue
            
            # Scrape poem content
            poem_content = self.scrape_poem_content(poem['url'], poem['title'])
            
            if poem_content:
                # Use cleaned filename for saving
                filename = self.clean_filename(poem['title'])
                if self.save_poem(poem_content, theme_folder, filename):
                    total_poems_saved += 1
            
            # Rate limiting between poems
            time.sleep(3)
        
        print(f"\n" + "="*50)
        print(f"🎉 SCRAPING COMPLETE!")
        print(f"📊 Summary:")
        print(f"   • Theme: {theme_name}")
        print(f"   • Poems found: {len(poems)}")
        print(f"   • Poems saved: {total_poems_saved}")
        print(f"   • Poems saved to: ./poems/{self.clean_filename(theme_name)}/ folder")
        print(f"=" * 50)

def main():
    scraper = PoetryFoundationScraper()
    
    # Example usage - scrape poems from a specific theme
    theme_name = input("Enter theme name (e.g., 'love', 'nature', 'death', 'friendship'): ").strip()
    
    if theme_name:
        scraper.scrape_poems_by_theme(theme_name)
    else:
        print("No theme specified. Example themes: love, nature, death, friendship, hope")

if __name__ == "__main__":
    main()