#!/usr/bin/env python3

import sys
import time
import pickle
import json
import os
import platform
import base64
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import traceback

# Reconfigure standard output to use UTF-8 encoding
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    # For systems that don't support reconfigure
    pass

def load_credentials():
    """Load login credentials from a JSON file."""
    with open("xcreds.json", "r") as file:
        return json.load(file)

def take_screenshot(driver, name):
    """Take a screenshot for debugging purposes"""
    try:
        screenshot = driver.get_screenshot_as_base64()
        print(f"\n--- SCREENSHOT: {name} ---")
        print(f"Base64 screenshot saved ({len(screenshot)} bytes)")
        
        # Also save to file if possible
        debug_dir = "debug_screenshots"
        if not os.path.exists(debug_dir):
            os.makedirs(debug_dir)
        
        with open(f"{debug_dir}/{name}.png", "wb") as f:
            f.write(base64.b64decode(screenshot))
        print(f"Screenshot saved to {debug_dir}/{name}.png")
    except Exception as e:
        print(f"Failed to take screenshot: {e}")

def try_multiple_login_approaches(driver, username, password, x_username):
    """Try multiple approaches to log in to X/Twitter"""
    wait = WebDriverWait(driver, 30)
    
    approaches = [
        try_standard_login,
        try_alternate_login,
        try_minimal_login
    ]
    
    for i, approach in enumerate(approaches):
        try:
            print(f"\nTrying login approach #{i+1}...")
            if approach(driver, wait, username, password, x_username):
                print(f"Login approach #{i+1} succeeded!")
                return True
        except Exception as e:
            print(f"Login approach #{i+1} failed: {e}")
            traceback.print_exc()
    
    print("All login approaches failed")
    return False

def try_standard_login(driver, wait, username, password, x_username):
    """The standard login approach"""
    print("Navigating to login page...")
    driver.get("https://twitter.com/i/flow/login")
    take_screenshot(driver, "login_page")
    time.sleep(5)
    
    print("Checking for login elements...")
    try:
        page_source = driver.page_source
        with open("debug_login_page.html", "w", encoding="utf-8") as f:
            f.write(page_source)
        print("Saved login page HTML to debug_login_page.html")
        
        # Check if login elements exist
        has_username = "username" in page_source.lower() or "email" in page_source.lower()
        has_username_field = driver.find_elements(By.CSS_SELECTOR, "input[autocomplete='username']")
        
        print(f"Page contains username/email keywords: {has_username}")
        print(f"Username field elements found: {len(has_username_field)}")
        
        if not has_username_field:
            print("Username field not found, login page may not have loaded properly")
            return False
    except Exception as e:
        print(f"Error checking login page: {e}")
    
    print("Entering username...")
    username_field = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[autocomplete='username']"))
    )
    username_field.clear()
    username_field.send_keys(username)
    time.sleep(1)
    username_field.send_keys(Keys.RETURN)
    take_screenshot(driver, "after_username")
    time.sleep(3)
    
    # Check for verification
    try:
        if driver.find_elements(By.CSS_SELECTOR, "input[data-testid='ocfEnterTextTextInput']"):
            print("Username verification required")
            username_verify = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[data-testid='ocfEnterTextTextInput']"))
            )
            username_verify.clear()
            username_verify.send_keys(x_username)
            time.sleep(1)
            username_verify.send_keys(Keys.RETURN)
            take_screenshot(driver, "after_verification")
            time.sleep(3)
    except:
        print("No username verification required")
    
    print("Entering password...")
    password_field = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password']"))
    )
    password_field.clear()
    password_field.send_keys(password)
    time.sleep(1)
    password_field.send_keys(Keys.RETURN)
    take_screenshot(driver, "after_password")
    time.sleep(5)
    
    # Check if login was successful
    try:
        primary_column = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='primaryColumn']"))
        )
        print("Login successful!")
        return True
    except:
        print("Login failed - primary column not found")
        return False

def try_alternate_login(driver, wait, username, password, x_username):
    """An alternate login approach with different selectors"""
    print("Navigating to login page (alternate)...")
    driver.get("https://twitter.com/login")
    take_screenshot(driver, "alt_login_page")
    time.sleep(5)
    
    # First check if we're already logged in
    try:
        if driver.current_url.startswith("https://twitter.com/home"):
            print("Already logged in!")
            return True
    except:
        pass
    
    print("Entering username (alternate)...")
    try:
        username_field = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='text']"))
        )
        username_field.clear()
        username_field.send_keys(username)
        time.sleep(1)
        
        # Look for the next button
        next_button = driver.find_element(By.XPATH, "//span[text()='Next']")
        next_button.click()
        
        take_screenshot(driver, "alt_after_username")
        time.sleep(3)
    except Exception as e:
        print(f"Error with alternate username: {e}")
        return False
    
    # Check for verification
    try:
        if driver.find_elements(By.CSS_SELECTOR, "input[name='text']"):
            print("Username verification required (alternate)")
            username_verify = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='text']"))
            )
            username_verify.clear()
            username_verify.send_keys(x_username)
            time.sleep(1)
            
            # Look for the next button again
            next_button = driver.find_element(By.XPATH, "//span[text()='Next']")
            next_button.click()
            
            take_screenshot(driver, "alt_after_verification")
            time.sleep(3)
    except:
        print("No username verification required (alternate)")
    
    print("Entering password (alternate)...")
    try:
        password_field = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='password']"))
        )
        password_field.clear()
        password_field.send_keys(password)
        time.sleep(1)
        
        # Look for the login button
        login_button = driver.find_element(By.XPATH, "//span[text()='Log in']")
        login_button.click()
        
        take_screenshot(driver, "alt_after_password")
        time.sleep(5)
    except Exception as e:
        print(f"Error with alternate password: {e}")
        return False
    
    # Check if login was successful
    try:
        if driver.current_url.startswith("https://twitter.com/home"):
            print("Login successful (alternate)!")
            return True
        else:
            print(f"Unexpected URL after login: {driver.current_url}")
            return False
    except:
        print("Login failed (alternate)")
        return False

def try_minimal_login(driver, wait, username, password, x_username):
    """A minimal approach using direct navigation to Elon's profile"""
    print("Trying minimal approach (direct to profile)...")
    try:
        driver.get("https://twitter.com/elonmusk")
        take_screenshot(driver, "direct_profile")
        time.sleep(5)
        
        # Check if we can see tweets without logging in
        if driver.find_elements(By.CSS_SELECTOR, "article"):
            print("Found articles without login!")
            return True
        else:
            print("No articles found without login")
            return False
    except Exception as e:
        print(f"Error with minimal approach: {e}")
        return False

def download_x_page(output_file, username, password, x_username):
    """
    Downloads Elon Musk's X page using Chrome in headless mode.
    Works on both Windows and Linux.
    """
    chrome_options = Options()
    
    # Check if in debug mode
    debug_mode = os.environ.get("DEBUG_MUSK", "false").lower() == "true"
    if not debug_mode:
        chrome_options.add_argument("--headless=new")
    
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Platform-specific settings
    if platform.system() == "Linux":
        # Additional Linux-specific options
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--window-size=1366,768")
        chrome_options.add_argument("--disable-browser-side-navigation")
        chrome_options.add_argument("--disable-features=NetworkService")
        chrome_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.images": 2,  # Don't load images
        })
        user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
    else:
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-notifications")
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
    
    chrome_options.add_argument(f"--user-agent={user_agent}")
    
    # Create debug directories
    debug_dir = "debug_screenshots"
    if not os.path.exists(debug_dir):
        os.makedirs(debug_dir)
    
    # Get ChromeDriver path
    chromedriver_path = None
    if platform.system() == "Windows":
        if os.path.exists("C:\\chromedriver.exe"):
            chromedriver_path = "C:\\chromedriver.exe"
        elif os.path.exists(".\\chromedriver.exe"):
            chromedriver_path = ".\\chromedriver.exe"
    else:
        if os.path.exists("/usr/bin/chromedriver"):
            chromedriver_path = "/usr/bin/chromedriver"
        elif os.path.exists("/usr/local/bin/chromedriver"):
            chromedriver_path = "/usr/local/bin/chromedriver"
    
    try:
        print("Setting up Chrome driver...")
        if chromedriver_path:
            chrome_service = Service(chromedriver_path)
            driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
        else:
            driver = webdriver.Chrome(options=chrome_options)
            
        driver.set_page_load_timeout(60)
        
        print("Testing simple page load...")
        try:
            driver.get("https://example.com")
            print("Successfully loaded example.com")
            take_screenshot(driver, "example_page")
        except Exception as e:
            print(f"Error loading example.com: {e}")
            raise
        
        print("Attempting login...")
        if not try_multiple_login_approaches(driver, username, password, x_username):
            raise Exception("All login approaches failed")
        
        print("Navigating to Elon Musk's profile...")
        driver.get("https://twitter.com/elonmusk")
        take_screenshot(driver, "musk_profile")
        time.sleep(5)
        
        wait = WebDriverWait(driver, 30)
        
        print("Waiting for posts to load...")
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "article")))
            print("Articles found!")
            take_screenshot(driver, "found_articles")
        except Exception as e:
            print(f"Error waiting for articles: {e}")
            
            # Save page for debugging
            with open("debug_no_articles.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("Saved page HTML to debug_no_articles.html")
            raise
        
        print("Scrolling to load more content...")
        try:
            driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(2)
            driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(2)
            take_screenshot(driver, "after_scroll")
        except Exception as e:
            print(f"Error during scroll: {e}")
        
        print("Saving page content...")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"HTML saved to: {output_file}")
        
        print("Extracting most recent post...")
        post = extract_posts(driver.page_source)
        
        if post:
            print("\nElon Musk's Most Recent Post:")
            print("-" * 50)
            print(post)
            print("-" * 50)
            return post
        else:
            print("No recent posts found")
            return None
        
    except Exception as e:
        print(f"Error during page download: {str(e)}")
        traceback.print_exc()
        return None
    finally:
        if 'driver' in locals():
            driver.quit()

def extract_posts(html_content):
    """Extract Musk's posts from HTML content"""
    soup = BeautifulSoup(html_content, 'html.parser')
    articles = soup.find_all('article')
    
    print(f"Found {len(articles)} articles")
    
    for article in articles:
        pinned = article.find('div', {'data-testid': 'socialContext'})
        if pinned and 'Pinned' in pinned.text:
            print("Skipping pinned post")
            continue
            
        text_div = article.find('div', {'data-testid': 'tweetText'})
        if text_div:
            post_text = ' '.join([span.text for span in text_div.find_all('span')])
            if post_text.strip():
                print(f"Found valid post: {post_text[:50]}...")
                return post_text.strip()
        else:
            # Try alternate method
            text_spans = article.select('span[data-testid="tweetText"] span')
            if text_spans:
                post_text = ' '.join([span.text for span in text_spans])
                if post_text.strip():
                    print(f"Found valid post (alt method): {post_text[:50]}...")
                    return post_text.strip()
    
    print("No valid posts found in HTML")
    return None

def main():
    """Main script flow with enhanced error reporting"""
    # Use a platform-appropriate output file path
    if platform.system() == "Windows":
        output_file = os.path.join(os.environ.get("USERPROFILE", "C:\\"), "muskhtml.html")
    else:
        output_file = os.path.expanduser("~/muskhtml.html")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    creds_path = os.path.join(script_dir, "xcreds.json")
    
    # Print system info
    print("\n=== SYSTEM INFORMATION ===")
    print(f"Platform: {platform.platform()}")
    print(f"Python: {platform.python_version()}")
    print(f"Memory: {os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / (1024.**3):.1f} GB") if platform.system() == "Linux" else None
    print("=========================\n")
    
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
        post = download_x_page(
            output_file,
            credentials["username"],
            credentials["password"],
            credentials["x_username"]
        )
        
        if not post:
            print("Scraping failed!")
            sys.exit(1)
            
    except FileNotFoundError:
        print(f"Error: Credentials file not found at {creds_path}")
        print("Please create an 'xcreds.json' file with your X credentials")
        print('Format: {"username": "your_email", "password": "your_password", "x_username": "your_x_username"}')
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
