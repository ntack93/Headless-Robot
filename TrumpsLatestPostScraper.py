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
        
        # Try different selectors in sequence
        selectors = [
            (By.CSS_SELECTOR, "div[data-testid='status']"),
            (By.CSS_SELECTOR, ".status"),
            (By.XPATH, "//div[contains(@class, 'status')]"),
            (By.TAG_NAME, "article")
        ]
        
        for by, selector in selectors:
            try:
                wait.until(EC.presence_of_element_located((by, selector)))
                print(f"Page loaded successfully using selector: {selector}")
                break
            except:
                continue
        
        # Multiple scrolls with longer delays
        print("Scrolling to load more content...")
        for _ in range(3):
            try:
                driver.execute_script("window.scrollBy(0, 1000);")
                time.sleep(3)  # Increased wait time
            except Exception as e:
                print(f"Scroll error: {e}")
                break

        # Final wait to ensure everything is loaded
        time.sleep(5)  # Increased final wait

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
    Reads the local HTML file and finds Trump's latest post using the specific HTML structure.
    """
    with open(html_file, 'r', encoding='utf-8') as file:
        content = file.read()

    soup = BeautifulSoup(content, 'html.parser')
    
    # Find the first status div that contains both the post content and timestamp
    status_divs = soup.find_all('div', class_='status cursor-pointer focusable')
    
    for div in status_divs:
        # Find the post content paragraph
        content_p = div.find('p', {'data-markup': 'true'})
        # Find the timestamp element
        time_element = div.find('time')
        
        if content_p and time_element:
            # Get the text content and timestamp
            post_text = content_p.get_text(strip=True)
            post_time = time_element.get('title')
            
            if post_text and post_time:
                print(f"Debug - Found status div with content")
                print(f"Debug - Post text: {post_text}")
                print(f"Debug - Time: {post_time}")
                return post_text, post_time

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
