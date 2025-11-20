
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium_stealth import stealth
import time

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver


def query_all_shadow(driver, selector):
    return driver.execute_script(
        """
        function deepQuerySelectorAll(selector) {
            const results = [];
            function search(node) {
                if (!node) return;
                
                if (node.querySelectorAll) {
                    node.querySelectorAll(selector).forEach(el => results.push(el));
                }
                
                // If node has shadow root, search inside
                if (node.shadowRoot) {
                    search(node.shadowRoot);
                }

                // Search children
                node.childNodes.forEach(child => search(child));
            }

            search(document);
            return results;
        }
        return deepQuerySelectorAll(arguments[0]);
        """,
        selector
    )


def get_brave_results(driver, query: str, max_results=5):
    driver.get(f"https://search.brave.com/search?q={query}")
    
    # Human-like delay
    import random
    time.sleep(random.uniform(2.1, 3.2))
    
    # Simulate human behaviour
    driver.execute_script("window.scrollBy(0, 600);")
    time.sleep(random.uniform(0.4, 0.8))

    # Use universal shadow-root search
    titles = query_all_shadow(driver, "div.title")
    snippets = query_all_shadow(driver, "div.generic-snippet")

    data = []
    for i in range(min(max_results, len(titles))):
        title_el = titles[i]
        snippet_el = snippets[i] if i < len(snippets) else None

        data.append({
            "title": title_el.text.strip(),
            "url": title_el.get_attribute("href"),
            "snippet": snippet_el.text.strip() if snippet_el else ""
        })

    return data



def get_duckduckgo_results(driver, query: str, max_results=5):
    driver.get(f"https://duckduckgo.com/?q={query}")
    time.sleep(2)

    titles = driver.find_elements(By.CSS_SELECTOR, "a[data-testid='result-title-a']")
    snippets = driver.find_elements(By.CSS_SELECTOR, "div[data-result='snippet']")

    data = []
    for i in range(min(max_results, len(titles))):
        t = titles[i]
        s = snippets[i] if i < len(snippets) else None

        data.append({
            "title": t.text,
            "url": t.get_attribute("href"),
            "snippet": s.text if s else ""
        })

    return data


def get_serp_results(query: str, engine="duckduckgo", max_results=5):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=options)

    stealth(
        driver,
        languages=["en-CA", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )

    # Select search engine
    engine = engine.lower()

    if engine == "duckduckgo":
        results = get_duckduckgo_results(driver, query, max_results)

    elif engine == "brave":
        results = get_brave_results(driver, query, max_results)

    else:
        raise ValueError("Unsupported engine: choose 'duckduckgo' or 'brave'")

    driver.quit()
    return results
