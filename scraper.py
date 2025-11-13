# scraper.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium_stealth import stealth
import time

def get_serp_results(query: str, max_results=5):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0 Safari/537.36")

    driver = webdriver.Chrome(options=options)
    
    # Hide automation fingerprints
    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )

    # Navigate to DuckDuckGo
    driver.get(f"https://duckduckgo.com/?q={query}")
    time.sleep(2)

    results = driver.find_elements(By.CSS_SELECTOR, "a[data-testid='result-title-a']")

    data = []
    for r in results[:max_results]:
        data.append({
            "title": r.text,
            "url": r.get_attribute("href")
        })

    driver.quit()
    return data

