#!/usr/bin/env python3

import sys
import time
import pickle
import json
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup

# Reconfigure standard output to use UTF-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

def load_credentials():
    """Load login credentials from a JSON file."""
    with open("xcreds.json", "r") as file:
        return json.load(file)

def login_to_x(driver, username, password):
    """Log in to X using the provided credentials."""
    try:
        print("Navigating to login page...")
        driver.get("https://twitter.com/i/flow/login")  # Using full Twitter login URL
        wait = WebDriverWait(driver, 30)

        print("Waiting for username field...")
        username_field = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[autocomplete='username']"))
        )
        print("Found username field, entering credentials...")
        time.sleep(2)  # Short pause before typing
        username_field.send_keys(username)
        username_field.send_keys(Keys.RETURN)
        time.sleep(2)  # Wait for password field to be ready

        print("Waiting for password field...")
        password_field = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
        )
        print("Found password field, entering password...")
        time.sleep(1)
        password_field.send_keys(password)
        password_field.send_keys(Keys.RETURN)

        # Wait for successful login
        print("Waiting for login to complete...")
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='primaryColumn']"))
        )
        print("Login successful!")

        # Save cookies
        print("Saving cookies...")
        with open("cookies.pkl", "wb") as file:
            pickle.dump(driver.get_cookies(), file)

    except Exception as e:
        print(f"Login error details: {str(e)}")
        if "timeout" in str(e).lower():
            print("Page took too long to load. Check your internet connection.")
        elif "no such element" in str(e).lower():
            print("Could not find login elements. X might have updated their page structure.")
        print("Current URL:", driver.current_url)
        print("Page source preview:", driver.page_source[:500])
        driver.quit()
        sys.exit(1)

def load_cookies(driver):
    """Load cookies from a file and add them to the driver."""
    try:
        with open("cookies.pkl", "rb") as file:
            cookies = pickle.load(file)
            for cookie in cookies:
                driver.add_cookie(cookie)
        return True
    except FileNotFoundError:
        return False

def download_x_page(output_file, username, password):
    """
    Downloads Elon Musk's X page using Chrome in headless mode on Linux.
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
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")
    chrome_options.add_argument("--enable-javascript")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument('--lang=en_US')
    chrome_options.add_argument(f"--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{133} Safari/537.36")
    
    chrome_service = Service('/usr/bin/chromedriver')
    
    try:
        print("Setting up Chrome driver...")
        driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
        driver.set_page_load_timeout(60)  # Increased timeout
        driver.set_script_timeout(30)

        print("Navigating to Elon Musk's X page...")
        driver.get("https://x.com/elonmusk")
        if load_cookies(driver):
            driver.refresh()
        else:
            print("Logging in to X...")
            login_to_x(driver, username, password)

        wait = WebDriverWait(driver, 60)
        print("Waiting for first post...")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "article")))
        
        # Multiple scrolls with longer delays
        print("Scrolling to load more content...")
        for _ in range(3):
            try:
                driver.execute_script("window.scrollBy(0, 1000);")
                time.sleep(3)
            except Exception as e:
                print(f"Scroll error: {e}")
                break
        
        print("Retrieving page source...")
        page_source = driver.page_source
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(page_source)
        print(f"Download complete! HTML saved to: {output_file}")
    except Exception as e:
        print(f"Error during page download: {e}")
        print("Current URL:", driver.current_url)
        raise
    finally:
        driver.quit()

def get_latest_post(html_file):
    """
    Reads the local HTML file and looks for Musk's first non-pinned post.
    Returns the post content and full timestamp.
    """
    with open(html_file, 'r', encoding='utf-8') as file:
        content = file.read()
    
    soup = BeautifulSoup(content, 'html.parser')
    articles = soup.find_all('article')
    print("Debug - Found articles:", len(articles))
    
    for article in articles:
        # Skip if this is a pinned post
        pinned_indicator = article.find('div', string=lambda t: t and 'Pinned' in t)
        if pinned_indicator:
            print("Debug - Skipping pinned post")
            continue
            
        # Try multiple methods to find the post content
        content_selectors = [
            'div[data-testid="tweetText"]',  # Main tweet content
            'span[data-testid="tweetText"]',  # Alternative content location
            'div[lang]',  # Language-tagged content div
            'span[dir="auto"]'  # Auto-direction text
        ]
        
        for selector in content_selectors:
            content_element = article.select_one(selector)
            if content_element:
                # Get all text content, removing extra whitespace
                text = ' '.join(content_element.stripped_strings)
                if text and len(text) > 1:  # Ensure it's not empty or just whitespace
                    # Find timestamp - try multiple methods
                    timestamp = None
                    time_element = article.find('time')
                    if time_element:
                        timestamp = time_element.get('datetime')
                    
                    if not timestamp:
                        # Try finding timestamp in data attributes
                        time_div = article.find('div', {'data-testid': 'timestamp'})
                        if time_div:
                            timestamp = time_div.get_text(strip=True)
                    
                    print(f"Debug - Found post using selector: {selector}")
                    print(f"Debug - Post text: {text}")
                    print(f"Debug - Timestamp: {timestamp}")
                    return text, timestamp or "No timestamp"
    
    print("Debug - No valid posts found after trying all selectors")
    return None, None

if __name__ == "__main__":
    """
    Main script flow
    """
    # Use $HOME environment variable for Linux compatibility
    output_file = os.path.expanduser("~/muskhtml.html")
    
    # Ensure xcreds.json is in the same directory as the script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    creds_path = os.path.join(script_dir, "xcreds.json")
    
    try:
        if not os.path.exists(creds_path):
            print(f"Error: Credentials file not found at {creds_path}")
            print("Creating example credentials file...")
            example_creds = {
                "username": "your_username",
                "password": "your_password"
            }
            with open(creds_path, "w") as f:
                json.dump(example_creds, f, indent=4)
            print(f"Please edit {creds_path} with your X credentials")
            sys.exit(1)
            
        credentials = load_credentials()
        username = credentials["username"]
        password = credentials["password"]

        # Download the page
        download_x_page(output_file, username, password)

        # Scrape the downloaded HTML
        post_content, timestamp = get_latest_post(output_file)

        # Print result
        if post_content:
            print(f"Latest Post: {post_content} (Posted: {timestamp})")
        else:
            print("No recent post found.")
    except FileNotFoundError:
        print(f"Error: Credentials file not found at {creds_path}")
        print("Please create an 'xcreds.json' file with your X credentials")
        print('Format: {"username": "your_username", "password": "your_password"}')
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
