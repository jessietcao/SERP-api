"""
Requirements:
    pip install selenium selenium-stealth
"""

import time
import random
import json
import logging
import re
from typing import List, Dict
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium_stealth import stealth
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# CONFIG -----------------------------------------------------------------------
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scraper")


# ---------------------------------------------------------------------------
# FINGERPRINT PROFILES
# ---------------------------------------------------------------------------
FINGERPRINT_PROFILES = [
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "platform": "Win32",
        "vendor": "Google Inc.",
        "renderer": "ANGLE (Intel UHD Graphics 620)",
        "screen": (1920, 1080),
        "hardwareConcurrency": 8,
        "deviceMemory": 8,
        "timezone": "America/Toronto",
        "languages": ["en-US", "en"]
    },
    {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
              "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "platform": "MacIntel",
        "vendor": "Apple Computer, Inc.",
        "renderer": "Apple GPU",
        "screen": (1440, 900),
        "hardwareConcurrency": 8,
        "deviceMemory": 8,
        "timezone": "America/Toronto",
        "languages": ["en-US", "en"]
    },
    {
        "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "platform": "Linux x86_64",
        "vendor": "Google Inc.",
        "renderer": "ANGLE (AMD Radeon RX 5700 XT)",
        "screen": (1366, 768),
        "hardwareConcurrency": 4,
        "deviceMemory": 4,
        "timezone": "UTC",
        "languages": ["en-US", "en"]
    }
]


# ---------------------------------------------------------------------------
# UTILS
# ---------------------------------------------------------------------------
def rand_sleep(a: float, b: float):
    time.sleep(random.uniform(a, b))


# ---------------------------------------------------------------------------
# DRIVER CREATION
# ---------------------------------------------------------------------------
def create_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    fp = random.choice(FINGERPRINT_PROFILES)

    options.add_argument(f"user-agent={fp['ua']}")
    w, h = fp["screen"]
    options.add_argument(f"--window-size={w},{h}")

    driver = webdriver.Chrome(options=options)

    # Stealth settings
    stealth(
        driver,
        languages=fp["languages"],
        vendor=fp["vendor"],
        platform=fp["platform"],
        webgl_vendor="Intel Inc.",
        renderer=fp["renderer"],
        fix_hairline=True,
    )

    patch_fingerprints(driver, fp)
    return driver


# ---------------------------------------------------------------------------
# FINGERPRINT PATCHING
# ---------------------------------------------------------------------------
def patch_fingerprints(driver, fp):
    script = f"""
    Object.defineProperty(navigator, 'webdriver', {{ get: () => false }});

    Object.defineProperty(navigator, 'platform', {{ get: () => '{fp["platform"]}' }});
    Object.defineProperty(navigator, 'vendor', {{ get: () => '{fp["vendor"]}' }});
    Object.defineProperty(navigator, 'userAgent', {{ get: () => '{fp["ua"]}' }});
    Object.defineProperty(navigator, 'languages', {{ get: () => {json.dumps(fp["languages"])} }});

    Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {fp["hardwareConcurrency"]} }});
    Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {fp["deviceMemory"]} }});

    Object.defineProperty(screen, 'width', {{ get: () => {fp["screen"][0]} }});
    Object.defineProperty(screen, 'height', {{ get: () => {fp["screen"][1]} }});
    """

    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})
    except Exception as e:
        logger.debug("Could not install fingerprint patch via CDP: %s", e)


# ---------------------------------------------------------------------------
# SHADOW DOM QUERY
# ---------------------------------------------------------------------------
def query_all_shadow(driver, selector: str):
    script = """
    function deepQuerySelectorAll(selector) {
        const results = [];
        function traverse(node) {
            if (!node) return;
            try {
                if (node.querySelectorAll) {
                    node.querySelectorAll(selector).forEach(el => results.push(el));
                }
            } catch(e){}
            if (node.shadowRoot) traverse(node.shadowRoot);
            node.childNodes.forEach(child => traverse(child));
        }
        traverse(document);
        return results;
    }
    return deepQuerySelectorAll(arguments[0]);
    """
    return driver.execute_script(script, selector)


# ---------------------------------------------------------------------------
# HUMAN SIM
# ---------------------------------------------------------------------------
def human_scroll(driver):
    for _ in range(random.randint(1, 3)):
        driver.execute_script(f"window.scrollBy(0, {random.randint(200, 800)});")
        rand_sleep(0.2, 0.9)


# ---------------------------------------------------------------------------
# SEARCH ENGINE HANDLERS
# ---------------------------------------------------------------------------
def get_duckduckgo_results(driver, query, max_results):
    driver.get(f"https://duckduckgo.com/?q={query}")
    rand_sleep(1, 2)
    human_scroll(driver)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-testid='result-title-a']"))
        )
    except Exception:
        logger.debug("DDG: wait timeout; continuing")

    titles = driver.find_elements(By.CSS_SELECTOR, "a[data-testid='result-title-a']")
    snippets = driver.find_elements(By.CSS_SELECTOR, "[data-result='snippet']")

    results = []
    for i in range(min(max_results, max(len(titles), len(snippets)))):
        t = titles[i] if i < len(titles) else None
        s = snippets[i] if i < len(snippets) else None
        results.append({
            "title": t.text.strip() if t else "",
            "url": t.get_attribute("href") if t else None,
            "snippet": s.text.strip() if s else ""
        })
    return results


def get_brave_results(driver, query, max_results):
    driver.get(f"https://search.brave.com/search?q={query}")
    rand_sleep(1, 2)
    human_scroll(driver)

    anchors = query_all_shadow(driver, "a.card-title")
    snippets = query_all_shadow(driver, "div.snippet")
    display_urls = query_all_shadow(driver, "cite")
    favicons = query_all_shadow(driver, "img.favicon, img.favicon-background")

    results = []
    count = min(max_results, max(len(anchors), len(snippets)))
    for i in range(count):
        a = anchors[i] if i < len(anchors) else None
        s = snippets[i] if i < len(snippets) else None
        disp = display_urls[i] if i < len(display_urls) else None
        icon = favicons[i] if i < len(favicons) else None
        results.append({
            "title": a.text.strip() if a else "",
            "url": a.get_attribute("href") if a else None,
            "snippet": s.text.strip() if s else "",
            "display_url": disp.text.strip() if disp else None,
            "favicon": icon.get_attribute("src") if icon else None
        })
    return results


def get_google_results(driver, query, max_results):
    driver.get(f"https://www.google.com/search?q={query}")
    rand_sleep(0.8, 1.6)
    human_scroll(driver)
    try:
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Accept') or contains(text(),'I agree')]"))
        ).click()
    except:
        pass

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.g, div.tF2Cxc, div.Ww4FFb"))
        )
    except:
        logger.debug("Google: wait timeout; proceeding with best-effort extraction")

    blocks = driver.find_elements(By.CSS_SELECTOR, "div.g, div.tF2Cxc, div.Ww4FFb")
    results = []
    seen = set()
    for b in blocks:
        if len(results) >= max_results:
            break
        try:
            t = b.find_element(By.TAG_NAME, "h3")
            title = t.text.strip()
            a = b.find_element(By.CSS_SELECTOR, "a")
            href = a.get_attribute("href")
            if not href or href in seen:
                continue
            seen.add(href)
            snippet = ""
            for sel in ["div.VwiC3b", "div.IsZvec", "div.s3v9rd"]:
                try:
                    snippet = b.find_element(By.CSS_SELECTOR, sel).text.strip()
                    if snippet:
                        break
                except:
                    continue
            results.append({"title": title, "url": href, "snippet": snippet})
        except:
            continue
    while len(results) < max_results:
        results.append({"title": "", "url": None, "snippet": ""})
    return results


def get_bing_results(driver, query, max_results):
    driver.get(f"https://www.bing.com/search?q={query}")
    rand_sleep(1.2, 2.5)
    human_scroll(driver)

    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "li.b_algo")))
    except:
        logger.debug("Bing: wait timeout; proceeding")

    blocks = driver.find_elements(By.CSS_SELECTOR, "li.b_algo")
    results = []
    seen = set()
    for b in blocks:
        if len(results) >= max_results:
            break
        try:
            h2 = b.find_element(By.TAG_NAME, "h2")
            a = h2.find_element(By.TAG_NAME, "a")
            href = a.get_attribute("href")
            if not href or href in seen:
                continue
            seen.add(href)
            snippet = ""
            try:
                snippet = b.find_element(By.CSS_SELECTOR, "p").text.strip()
            except:
                snippet = ""
            results.append({"title": a.text.strip(), "url": href, "snippet": snippet})
        except:
            continue
    while len(results) < max_results:
        results.append({"title": "", "url": None, "snippet": ""})
    return results


def get_baidu_results(driver, query, max_results: int = 5) -> List[Dict]:
    """
    Extract Baidu organic results robustly with multiple fallbacks.
    """
    driver.get(f"https://www.baidu.com/s?wd={query}")
    rand_sleep(1.2, 2.5)
    # scroll a few times
    for _ in range(2):
        human_scroll(driver)

    try:
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.result, div.c-container, div.result-op"))
        )
    except Exception:
        logger.debug("Baidu: wait timeout; proceeding with best-effort extraction")

    results = []
    blocks = driver.find_elements(By.CSS_SELECTOR, "div.result.c-container, div.c-container, .result-op, div.result")
    seen = set()

    for block in blocks:
        if len(results) >= max_results:
            break
        try:
            title = ""
            url = None
            link_el = None
            title_selectors = ["h3 a", ".t a", ".c-title a", "a[target='_blank']", "a"]
            for sel in title_selectors:
                try:
                    link_el = block.find_element(By.CSS_SELECTOR, sel)
                    text = link_el.text.strip()
                    href = link_el.get_attribute("href")
                    if text and href:
                        title = text
                        url = href
                        break
                except:
                    continue

            if not title or not url:
                # fallback: any <a>
                try:
                    link_el = block.find_element(By.TAG_NAME, "a")
                    title = link_el.text.strip()
                    url = link_el.get_attribute("href")
                except:
                    continue

            # Clean URL if Baidu redirect link (common)
            if url and "http" in url and "www.baidu.com" not in url:
                # attempt to keep as-is; caller can dereference redirects if needed
                pass

            if not url or url in seen:
                continue
            seen.add(url)

            # Snippet extraction with many selectors and cleanup
            snippet = ""
            snippet_selectors = [
                "div[data-module='abstract']", ".summary-text_560AM", "div[role='text']",
                ".cu-line-clamp-2", ".c-color-text", ".c-abstract", ".c-span18", ".op-bk-polysemy"
            ]
            for sel in snippet_selectors:
                try:
                    s_el = block.find_element(By.CSS_SELECTOR, sel)
                    s_text = s_el.text.strip()
                    if s_text:
                        # remove Chinese date patterns and excessive whitespace
                        s_text = re.sub(r'\d{4}年\d{1,2}月\d{1,2}日', '', s_text)
                        s_text = re.sub(r'\s+', ' ', s_text).strip()
                        if s_text:
                            snippet = s_text
                            break
                except:
                    continue

            if not snippet:
                # fallback: take first 1-2 non-empty lines from block text excluding title
                full = block.text.strip()
                if title and title in full:
                    full = full.replace(title, "")
                lines = [ln.strip() for ln in full.split("\n") if ln.strip()]
                if lines:
                    snippet = " ".join(lines[:2])

            results.append({"title": title, "url": url, "snippet": snippet})
        except Exception as e:
            logger.debug(f"Baidu: failed to extract block: {e}")
            continue

    # pad
    while len(results) < max_results:
        results.append({"title": "", "url": None, "snippet": ""})
    return results


# ---------------------------------------------------------------------------
# MAIN WRAPPER (RETRIES + DRIVER CREATION)
# ---------------------------------------------------------------------------
def get_serp_results(query: str, engine: str = "duckduckgo", max_results: int = 5) -> List[Dict]:
    engine = engine.lower().strip()
    last_error = None
    backoff = INITIAL_BACKOFF

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            driver = create_driver()
            logger.info("Driver started (attempt %d). Engine=%s", attempt, engine)

            if engine == "duckduckgo":
                out = get_duckduckgo_results(driver, query, max_results)
            elif engine == "brave":
                out = get_brave_results(driver, query, max_results)
            elif engine == "google":
                out = get_google_results(driver, query, max_results)
            elif engine == "bing":
                out = get_bing_results(driver, query, max_results)
            elif engine == "baidu":
                out = get_baidu_results(driver, query, max_results)
            else:
                raise ValueError(f"Unsupported engine: {engine}")

            driver.quit()
            return out

        except Exception as e:
            last_error = e
            logger.warning("Attempt %d failed: %s", attempt, e)
            try:
                driver.quit()
            except Exception:
                pass
            time.sleep(backoff)
            backoff *= 2

    logger.error("All attempts failed. Last error: %s", last_error)
    raise last_error
