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
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup

# Reconfigure standard output to use UTF-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

def load_credentials():
    """Load login credentials from a JSON file."""
    with open("xcreds.json", "r") as file:
        return json.load(file)

def login_to_x(driver, username, password, x_username):
    """Linux-specific login function with visual feedback"""
    try:
        print("Navigating to login page...")
        driver.get("https://twitter.com/i/flow/login")
        wait = WebDriverWait(driver, 30)

        print("Entering username...")
        username_field = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[autocomplete='username']"))
        )
        time.sleep(1)
        username_field.send_keys(username)  # Start with email
        username_field.send_keys(Keys.RETURN)
        time.sleep(2)

        # Check for additional username verification step
        try:
            print("Checking for username verification...")
            username_verify = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[data-testid='ocfEnterTextTextInput']"))
            )
            print("Username verification required, entering X username...")
            time.sleep(1)
            username_verify.send_keys(x_username)
            username_verify.send_keys(Keys.RETURN)
            time.sleep(2)
        except Exception as e:
            print("No username verification required, continuing...")

        print("Entering password...")
        password_field = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
        )
        time.sleep(1)
        password_field.send_keys(password)
        password_field.send_keys(Keys.RETURN)

        print("Waiting for login completion...")
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='primaryColumn']"))
        )
        print("Login successful!")

        print("Navigating to Elon Musk's profile...")
        time.sleep(2)
        driver.get("https://x.com/elonmusk")
        time.sleep(2)

    except Exception as e:
        print(f"Login failed: {str(e)}")
        raise

def extract_posts(html_content):
    """
    Extracts Elon Musk's most recent non-pinned post
    Args:
        html_content (str): Raw HTML content
    Returns:
        str: Most recent non-pinned post text, or None if not found
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    articles = soup.find_all('article')
    
    for article in articles:
        pinned = article.find('div', {'data-testid': 'socialContext'})
        if pinned and 'Pinned' in pinned.text:
            continue
            
        text_div = article.find('div', {'data-testid': 'tweetText'})
        if text_div:
            post_text = ' '.join([span.text for span in text_div.find_all('span')])
            if post_text.strip():
                return post_text.strip()
    
    return None

def download_x_page(output_file, username, password, x_username):
    """
    Downloads Elon Musk's X page using Chrome in headless mode on Linux.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")
    
    chrome_service = Service('/usr/bin/chromedriver')
    
    try:
        print("Setting up Chrome driver...")
        driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
        driver.set_page_load_timeout(60)
        
        print("Logging in to X...")
        login_to_x(driver, username, password, x_username)
        
        wait = WebDriverWait(driver, 60)
        print("Waiting for posts to load...")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "article")))
        
        print("Scrolling to load more content...")
        for i in range(3):
            print(f"Scroll {i+1}/3...")
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(2)
        
        print("Extracting most recent post...")
        post = extract_posts(driver.page_source)
        
        if post:
            print("\nElon Musk's Most Recent Post:")
            print("-" * 50)
            print(post)
            print("-" * 50)
        else:
            print("No recent posts found")
        
        print("\nSaving page content...")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"Download complete! HTML saved to: {output_file}")
        
        return True
        
    except Exception as e:
        print(f"Error during page download: {str(e)}")
        return False
    finally:
        driver.quit()

def main():
    """Main script flow"""
    output_file = os.path.expanduser("~/muskhtml.html")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    creds_path = os.path.join(script_dir, "xcreds.json")
    
    try:
        if not os.path.exists(creds_path):
            print(f"Error: Credentials file not found at {creds_path}")
            print("Creating example credentials file...")
            example_creds = {
                "username": "your_email",
                "password": "your_password",
                "x_username": "your_x_username"
            }
            with open(creds_path, "w") as f:
                json.dump(example_creds, f, indent=4)
            print(f"Please edit {creds_path} with your X credentials")
            sys.exit(1)
            
        credentials = load_credentials()
        success = download_x_page(
            output_file,
            credentials["username"],
            credentials["password"],
            credentials["x_username"]
        )
        
        if not success:
            print("Scraping failed!")
            sys.exit(1)
            
    except FileNotFoundError:
        print(f"Error: Credentials file not found at {creds_path}")
        print("Please create an 'xcreds.json' file with your X credentials")
        print('Format: {"username": "your_email", "password": "your_password", "x_username": "your_x_username"}')
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
