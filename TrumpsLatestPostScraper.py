#!/usr/bin/env python3

import sys
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Wait conditions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

from bs4 import BeautifulSoup

# Reconfigure standard output to use UTF-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

def download_truthsocial_page(output_file):
    """
    Downloads the fully rendered HTML of Donald Trump's Truth Social page,
    using Chrome in headless mode on Linux.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-infobars")
    # Add user agent to appear more like a real browser
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")
    
    chrome_service = Service('/usr/bin/chromedriver')
    
    try:
        driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
        driver.set_page_load_timeout(30)  # Set page load timeout
        
        print("Navigating to Trump's Truth Social page...")
        driver.get("https://truthsocial.com/@realDonaldTrump")

        # Wait for any element that indicates the page has loaded
        wait = WebDriverWait(driver, 30)
        print("Waiting for page to load...")
        
        # Wait explicitly for status posts to appear
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='status']")))
            print("Posts found on page!")
        except Exception as e:
            print(f"Warning: Timed out waiting for posts: {e}")
        
        # Let the page render completely
        time.sleep(4)
        
        # More aggressive scrolling to ensure more posts are loaded
        print("Scrolling to load content...")
        try:
            # Scroll down multiple times to load more content
            driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(1)
            driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(1)
            driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(1)
            # Don't scroll back to top, we want to capture posts that are now loaded
        except Exception as e:
            print(f"Scroll error: {e}")

        # Final wait to ensure everything is loaded
        time.sleep(3)

        print("Retrieving page source...")
        page_source = driver.page_source
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(page_source)

        print(f"Download complete! HTML saved to: {output_file}")

    except Exception as e:
        print(f"Error during page download: {e}")
        raise
    finally:
        driver.quit()

def get_latest_post(html_file):
    """
    Reads the local HTML file and finds Trump's latest text post.
    """
    with open(html_file, 'r', encoding='utf-8') as file:
        content = file.read()

    soup = BeautifulSoup(content, 'html.parser')
    
    print("Looking for Trump's posts...")
    
    # First attempt: Use aria-label containing Trump's name
    print("Method 1: Looking for posts with Trump's name in aria-label...")
    status_divs = soup.find_all('div', class_='status cursor-pointer focusable')
    print(f"Found {len(status_divs)} status divs")
    
    valid_posts = []
    
    for div in status_divs:
        # Check if it has Trump's name
        aria_label = div.get('aria-label', '')
        if 'Donald J. Trump' not in aria_label:
            continue
            
        # Find the content paragraph - might be nested deeply
        content_p = div.find('p', {'data-markup': 'true'})
        if not content_p:
            print(f"No content paragraph found for a Trump post")
            continue
            
        # Get text content
        post_text = content_p.get_text(strip=True)
        
        # Skip empty posts or just URLs
        if not post_text or (post_text.startswith('http') and ' ' not in post_text):
            print(f"Skipping post: appears to be just a URL or empty")
            continue
            
        # Find timestamp
        time_element = div.find('time')
        if not time_element:
            print(f"No timestamp found for a Trump post")
            continue
            
        post_time = time_element.get('title')
        timestamp = time_element.get('datetime')
        
        # Check data-index of parent containers
        parent_with_index = None
        for parent in div.parents:
            if parent.has_attr('data-index'):
                parent_with_index = parent
                break
                
        index = 999
        if parent_with_index:
            try:
                index = int(parent_with_index.get('data-index', '999'))
                print(f"Found post with data-index={index}")
            except ValueError:
                pass
                
        print(f"Found valid Trump post: {post_text[:50]}...")
        valid_posts.append((post_text, post_time, timestamp, index))
    
    # If we found valid posts, return the one with lowest index (most recent)
    if valid_posts:
        # Sort by index (ascending)
        sorted_posts = sorted(valid_posts, key=lambda x: x[3])
        print(f"Found {len(valid_posts)} valid posts, returning most recent (index {sorted_posts[0][3]})")
        return sorted_posts[0][0], sorted_posts[0][1]
    
    # If no posts found, try other methods
    print("No posts found with primary method, trying alternative approaches...")
    
    # Method 2: Find all paragraphs with data-markup and work backward
    print("Method 2: Looking for post content paragraphs...")
    content_ps = soup.find_all('p', {'data-markup': 'true'})
    print(f"Found {len(content_ps)} content paragraphs")
    
    valid_posts = []
    
    for p in content_ps:
        post_text = p.get_text(strip=True)
        
        # Skip empty posts or just URLs
        if not post_text or (post_text.startswith('http') and ' ' not in post_text):
            continue
            
        # Find the closest status div upward
        status_div = None
        for parent in p.parents:
            if parent.name == 'div' and 'status' in parent.get('class', []):
                status_div = parent
                break
                
        if not status_div:
            continue
            
        # Check if it has Trump's name
        aria_label = status_div.get('aria-label', '')
        if 'Donald J. Trump' not in aria_label and 'realDonaldTrump' not in aria_label:
            continue
            
        # Find timestamp
        time_element = status_div.find('time')
        if not time_element:
            continue
            
        post_time = time_element.get('title')
        timestamp = time_element.get('datetime')
        
        print(f"Found valid Trump post via method 2: {post_text[:50]}...")
        valid_posts.append((post_text, post_time, timestamp))
    
    # Sort by timestamp (most recent first)
    if valid_posts:
        # Sort by timestamp (most recent first)
        sorted_posts = sorted(valid_posts, key=lambda x: x[2] if x[2] else "", reverse=True)
        print(f"Found {len(valid_posts)} valid posts via alternative method, returning most recent")
        return sorted_posts[0][0], sorted_posts[0][1]
    
    print("No posts found after trying all methods")
    return None, None

if __name__ == "__main__":
    """
    Main script flow
    """
    # Use $HOME environment variable for Linux compatibility
    output_file = os.path.expanduser("~/trumphtml.html")

    # Download the page
    download_truthsocial_page(output_file)

    # Scrape the downloaded HTML
    post_content, post_time = get_latest_post(output_file)

    # Print result
    if post_content and post_time:
        print(f"Latest Post: {post_content}")
        print(f"Posted on: {post_time}")
    else:
        print("No recent post found.")
