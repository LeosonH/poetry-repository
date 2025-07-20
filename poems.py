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
import csv
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
                        
                        # Remove "p1" prefix that indicates Poetry magazine publication
                        if poem_title.lower().startswith('p1'):
                            poem_title = poem_title[2:].strip()
                        
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
        
        # Remove "p1" prefix from actual title as well
        if actual_title.lower().startswith('p1'):
            actual_title = actual_title[2:].strip()
        
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
    
    def extract_author_name_from_url(self, author_url):
        """Extract clean author name from Poetry Foundation URL."""
        author_slug = author_url.split('/people/')[-1]
        author_name = author_slug.replace('-', ' ').title()
        return author_name
    
    def extract_poems_from_author(self, author_url):
        """Extract poem links from an author page."""
        print(f"Examining author page: {author_url}")
        response = self.get_page(author_url)
        if not response:
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        poems = []
        
        # Look for poem links specifically in the main content areas of author pages
        # More targeted selectors to avoid navigation and sidebar links
        poem_selectors = [
            '.c-feature .c-feature-hd a[href*="/poems/"]',  # Featured poems
            '.c-feature .c-feature-bd a[href*="/poems/"]',  # Featured poem bodies
            '.o-title a[href*="/poems/"]',                  # Poem titles
            'h3.c-feature-hd a[href*="/poems/"]',          # Poem headlines
            'h4.c-feature-hd a[href*="/poems/"]',          # Secondary headlines
            '.c-poem-list a[href*="/poems/"]',             # Poem list sections
            '.o-collections a[href*="/poems/"]'            # Collections
        ]
        
        for selector in poem_selectors:
            elements = soup.select(selector)
            for element in elements:
                href = element.get('href')
                if href and '/poems/' in href:
                    poem_title = element.get_text(strip=True)
                    if not poem_title or len(poem_title) < 3:
                        continue
                    
                    # Remove "p1" prefix that indicates Poetry magazine publication
                    if poem_title.lower().startswith('p1'):
                        poem_title = poem_title[2:].strip()
                    
                    # Enhanced filtering for navigation and non-poem content
                    skip_words = [
                        'more', 'browse', 'search', 'filter', 'sort', 'next', 'previous', 'page', 
                        'view all', 'see all', 'read more', 'continue reading', 'share', 'print',
                        'poems by', 'about', 'biography', 'contact', 'subscribe', 'newsletter',
                        'guide', 'guides', 'all poems', 'poem of the day', 'daily poem', 'featured',
                        'collection', 'anthology', 'archive', 'browse by', 'category', 'theme',
                        'popular poems', 'classic poems', 'recent poems', 'new poems'
                    ]
                    skip_phrases = [
                        'view all poems by', 'browse poems by', 'more poems by',
                        'see more', 'read all', 'poem guides', 'poem guide', 'all poems',
                        'poem of the day', 'poems of the day', 'daily poems', 'featured poems',
                        'popular poems', 'classic poems', 'recent poems', 'new poems',
                        'browse all', 'view more', 'see all poems', 'all poetry'
                    ]
                    
                    title_lower = poem_title.lower()
                    if any(word in title_lower for word in skip_words):
                        continue
                    if any(phrase in title_lower for phrase in skip_phrases):
                        continue
                    
                    # Skip very short titles that are likely navigation
                    if len(poem_title) < 5:
                        continue
                    
                    # Skip titles that are just numbers or common words
                    if poem_title.isdigit() or poem_title.lower() in ['more', 'next', 'prev', 'home']:
                        continue
                        
                    full_url = urllib.parse.urljoin(self.base_url, href)
                    
                    # Avoid duplicates
                    if not any(p['url'] == full_url for p in poems):
                        poems.append({
                            'title': poem_title,
                            'url': full_url
                        })
        
        # If no poems found with specific selectors, try a broader approach but with stricter filtering
        if not poems:
            print("No poems found with specific selectors, trying broader search...")
            broader_elements = soup.select('a[href*="/poems/"]')
            
            for element in broader_elements:
                href = element.get('href')
                if href and '/poems/' in href:
                    # Get the parent container to check context
                    parent = element.find_parent(['div', 'section', 'article'])
                    if parent and any(class_name in str(parent.get('class', [])) for class_name in ['nav', 'footer', 'sidebar', 'menu']):
                        continue
                    
                    poem_title = element.get_text(strip=True)
                    if not poem_title or len(poem_title) < 5:
                        continue
                    
                    # Remove "p1" prefix that indicates Poetry magazine publication
                    if poem_title.lower().startswith('p1'):
                        poem_title = poem_title[2:].strip()
                    
                    # Apply the same filtering as above
                    title_lower = poem_title.lower()
                    skip_words = [
                        'more', 'browse', 'search', 'filter', 'sort', 'next', 'previous', 'page', 
                        'view all', 'see all', 'read more', 'continue reading', 'share', 'print',
                        'poems by', 'about', 'biography', 'contact', 'subscribe', 'newsletter',
                        'guide', 'guides', 'all poems', 'poem of the day', 'daily poem', 'featured',
                        'collection', 'anthology', 'archive', 'browse by', 'category', 'theme',
                        'popular poems', 'classic poems', 'recent poems', 'new poems'
                    ]
                    skip_phrases = [
                        'view all poems by', 'browse poems by', 'more poems by',
                        'see more', 'read all', 'poem guides', 'poem guide', 'all poems',
                        'poem of the day', 'poems of the day', 'daily poems', 'featured poems',
                        'popular poems', 'classic poems', 'recent poems', 'new poems',
                        'browse all', 'view more', 'see all poems', 'all poetry'
                    ]
                    
                    if any(word in title_lower for word in skip_words):
                        continue
                    if any(phrase in title_lower for phrase in skip_phrases):
                        continue
                    
                    if poem_title.isdigit() or poem_title.lower() in ['more', 'next', 'prev', 'home']:
                        continue
                        
                    full_url = urllib.parse.urljoin(self.base_url, href)
                    
                    if not any(p['url'] == full_url for p in poems):
                        poems.append({
                            'title': poem_title,
                            'url': full_url
                        })
        
        print(f"Found {len(poems)} poems for this author")
        return poems
    
    def scrape_poems_by_author_range(self, csv_file_path, start_row=1, end_row=None):
        """Scrape poems from authors in a CSV file within specified row range."""
        print(f"Starting Poetry Foundation scraper for authors from CSV")
        print(f"CSV file: {csv_file_path}")
        
        if not os.path.exists(csv_file_path):
            print(f"Error: CSV file not found: {csv_file_path}")
            return
        
        authors_processed = 0
        total_poems_saved = 0
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                header = next(reader)  # Skip header row
                
                rows = list(reader)
                total_rows = len(rows)
                
                # Validate row range
                if start_row < 1:
                    start_row = 1
                if end_row is None or end_row > total_rows:
                    end_row = total_rows
                
                print(f"Processing rows {start_row} to {end_row} (out of {total_rows} total authors)")
                
                # Process authors in specified range
                for i in range(start_row - 1, end_row):  # Adjust for 0-based indexing
                    if i >= len(rows):
                        break
                        
                    row = rows[i]
                    if len(row) == 0:
                        continue
                        
                    author_url = row[0].strip()
                    if not author_url.startswith('http'):
                        continue
                    
                    author_name = self.extract_author_name_from_url(author_url)
                    print(f"\n=== Processing author {i + 1}/{total_rows}: {author_name} ===")
                    
                    # Create folder for this author
                    author_folder = Path('poems') / 'authors' / self.clean_filename(author_name)
                    author_folder.mkdir(parents=True, exist_ok=True)
                    
                    # Extract poems from author page
                    poems = self.extract_poems_from_author(author_url)
                    
                    if not poems:
                        print(f"  No poems found for {author_name}")
                        continue
                    
                    author_poems_saved = 0
                    
                    # Process each poem
                    for j, poem in enumerate(poems, 1):
                        print(f"\n  --- Processing poem {j}/{len(poems)} ---")
                        
                        # Check if already exists
                        filename = self.clean_filename(poem['title'])
                        file_path = author_folder / f"{filename}.txt"
                        if file_path.exists():
                            print(f"    Skipping existing: {filename}.txt")
                            continue
                        
                        # Scrape poem content
                        poem_content = self.scrape_poem_content(poem['url'], poem['title'])
                        
                        if poem_content:
                            if self.save_poem(poem_content, author_folder, filename):
                                author_poems_saved += 1
                                total_poems_saved += 1
                        
                        # Rate limiting between poems
                        time.sleep(2)
                    
                    authors_processed += 1
                    print(f"  ✓ Completed {author_name}: {author_poems_saved} poems saved")
                    
                    # Rate limiting between authors
                    time.sleep(3)
                    
        except Exception as e:
            print(f"Error processing CSV: {e}")
            return
        
        print(f"\n" + "="*60)
        print(f"🎉 AUTHOR SCRAPING COMPLETE!")
        print(f"📊 Summary:")
        print(f"   • Authors processed: {authors_processed}")
        print(f"   • Total poems saved: {total_poems_saved}")
        print(f"   • Poems saved to: ./poems/authors/ folder")
        print(f"=" * 60)

def main():
    scraper = PoetryFoundationScraper()
    
    print("Poetry Foundation Scraper")
    print("1. Scrape poems by theme")
    print("2. Scrape poems by author (from CSV file)")
    
    choice = input("Choose option (1 or 2): ").strip()
    
    if choice == "1":
        # Original theme scraping functionality
        theme_name = input("Enter theme name (e.g., 'love', 'nature', 'death', 'friendship'): ").strip()
        
        if theme_name:
            scraper.scrape_poems_by_theme(theme_name)
        else:
            print("No theme specified. Example themes: love, nature, death, friendship, hope")
    
    elif choice == "2":
        # New author scraping functionality
        csv_file = input("Enter CSV file path (default: 'data/poetry_author_links.csv'): ").strip()
        if not csv_file:
            csv_file = "data/poetry_author_links.csv"
        
        if not os.path.exists(csv_file):
            print(f"Error: CSV file '{csv_file}' not found.")
            return
        
        # Get total number of authors in CSV
        with open(csv_file, 'r', encoding='utf-8') as f:
            total_authors = sum(1 for line in f) - 1  # Subtract header row
        
        print(f"CSV contains {total_authors} authors.")
        
        try:
            start_row = int(input(f"Enter starting row (1-{total_authors}): ").strip())
            end_row_input = input(f"Enter ending row (1-{total_authors}, or press Enter for {total_authors}): ").strip()
            
            if end_row_input:
                end_row = int(end_row_input)
            else:
                end_row = total_authors
            
            if start_row < 1 or start_row > total_authors:
                print("Invalid start row. Using row 1.")
                start_row = 1
            
            if end_row < start_row or end_row > total_authors:
                print(f"Invalid end row. Using row {total_authors}.")
                end_row = total_authors
            
            scraper.scrape_poems_by_author_range(csv_file, start_row, end_row)
            
        except ValueError:
            print("Invalid row numbers. Please enter numeric values.")
    
    else:
        print("Invalid choice. Please select 1 or 2.")

if __name__ == "__main__":
    main()