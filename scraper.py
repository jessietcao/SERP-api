"""
Requirements: pip install selenium selenium-stealth 
"""

import time
import random
import json
import logging
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium_stealth import stealth
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import requests

# CONFIG 
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scraper")


#Fingerprint profiles
FINGERPRINT_PROFILES = [
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "platform": "Win32",
        "vendor": "Google Inc.",
        "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0)",
        "screen": (1920, 1080),
        "hardwareConcurrency": 8,
        "deviceMemory": 8,
        "timezone": "America/Toronto",
        "languages": ["en-US", "en"]
    },
    {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
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
        "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "platform": "Linux x86_64",
        "vendor": "Google Inc.",
        "renderer": "ANGLE (AMD, AMD Radeon RX 5700 XT Direct3D11 vs_5_0 ps_5_0)",
        "screen": (1366, 768),
        "hardwareConcurrency": 4,
        "deviceMemory": 4,
        "timezone": "UTC",
        "languages": ["en-US", "en"]
    }
]



def rand_sleep(a: float, b: float):
    time.sleep(random.uniform(a, b))


def create_driver( use_brave: bool = False):
    """
     chrome driver 
    """
    #standard scraper setups
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
    ua = fp["ua"]
    options.add_argument(f"user-agent={ua}")

    w, h = fp.get("screen", (1366, 768))
    options.add_argument(f"--window-size={w},{h}")

    driver = webdriver.Chrome(options=options)

    # stealth
    stealth(driver,
            languages=fp.get("languages", ["en-US", "en"]),
            vendor=fp.get("vendor", "Google Inc."),
            platform=fp.get("platform", "Win32"),
            webgl_vendor="Intel Inc.",
            renderer=fp.get("renderer", "Intel Iris OpenGL Engine"),
            fix_hairline=True,
            )

    # full fingerprint patch via CDP (evaluate on new document)
    patch_fingerprints(driver, fp)

    # small random mouse move to look human (works in headful; in headless it's limited)
    try:
        driver.execute_script("window.scrollTo(0, 1);")
    except Exception:
        pass

    return driver


def patch_fingerprints(driver, fp: dict):
    """
    Patch a number of navigator/WebGL/canvas/audio properties using CDP so each new page
    will see the patched values.
    fp = fingerprint profile dict
    """
    # We use Chrome DevTools protocol to inject script at document start
    script = f"""
    // Basic anti-selenium flags
    Object.defineProperty(navigator, 'webdriver', {{ get: () => false }});

    // coherent platform/vendor/UA
    Object.defineProperty(navigator, 'platform', {{ get: () => '{fp['platform']}' }});
    Object.defineProperty(navigator, 'vendor', {{ get: () => '{fp['vendor']}' }});
    Object.defineProperty(navigator, 'userAgent', {{ get: () => '{fp['ua']}' }});
    Object.defineProperty(navigator, 'languages', {{ get: () => {json.dumps(fp.get('languages', ['en-US','en']))} }});

    // hardware hints
    Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {fp.get('hardwareConcurrency', 4)} }});
    Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {fp.get('deviceMemory', 4)} }});

    // screen
    Object.defineProperty(screen, 'width', {{ get: () => {fp.get('screen', (1366,768))[0]} }});
    Object.defineProperty(screen, 'height', {{ get: () => {fp.get('screen', (1366,768))[1]} }});
    Object.defineProperty(screen, 'colorDepth', {{ get: () => 24 }});

    // plugins (simple but realistic list)
    Object.defineProperty(navigator, 'plugins', {{
      get: () => [{{name: 'Chrome PDF Plugin'}}, {{name: 'Chrome PDF Viewer'}}, {{name: 'Native Client'}}]
    }});

    // mimeTypes minimal stub
    Object.defineProperty(navigator, 'mimeTypes', {{
      get: () => [{{type:'application/pdf', suffixes:'pdf'}}]
    }});

    // Timezone (affects Intl)
    try {{
        Intl.DateTimeFormat = (function(orig) {{
            return function() {{ return orig.apply(this, arguments); }};
        }})(Intl.DateTimeFormat);
        // not changing implementation heavily, but keep timezone in mind server-side
    }} catch(e){{}}

    // Canvas fingerprint patch: add tiny noise
    (function() {{
      const toDataURL = HTMLCanvasElement.prototype.toDataURL;
      HTMLCanvasElement.prototype.toDataURL = function() {{
        try {{
          const ctx = this.getContext('2d');
          if (ctx) {{
            ctx.fillStyle = 'rgba(0,0,0,0)';
            ctx.fillRect(0, 0, 1, 1);
          }}
        }} catch(e){{}}
        return toDataURL.apply(this, arguments);
      }};
    }})();

    // WebGL parameter spoof for vendor/renderer unmasked
    (function() {{
      try {{
        const proto = WebGLRenderingContext && WebGLRenderingContext.prototype;
        if (proto) {{
          const getParameter = proto.getParameter;
          proto.getParameter = function(param) {{
            // UNMASKED_VENDOR_WEBGL = 37445, UNMASKED_RENDERER_WEBGL = 37446
            if (param === 37445) return '{fp.get("vendor", "Google Inc. (Intel)")}';
            if (param === 37446) return '{fp.get("renderer", "WebKit WebGL")}';
            return getParameter.call(this, param);
          }};
        }}
      }} catch(e){{}}
    }})();
    """

    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})
        logger.debug("Fingerprint patch installed")
    except Exception as e:
        logger.warning("Could not patch fingerprints via CDP: %s", e)


# Shadow DOM traversal 
def query_all_shadow(driver, selector: str):
    """
    Returns list of elements matching selector across all shadow roots.
    Each element returned is a WebElement reference inside the browser.
    """
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
            // shadow root
            if (node.shadowRoot) {
                traverse(node.shadowRoot);
            }
            node.childNodes.forEach(child => traverse(child));
        }
        traverse(document);
        return results;
    }
    return deepQuerySelectorAll(arguments[0]);
    """
    return driver.execute_script(script, selector)


#Human simulation 
def human_scroll(driver):
    # small random scrolls
    for _ in range(random.randint(1, 3)):
        driver.execute_script(f"window.scrollBy(0, {random.randint(200, 800)});")
        rand_sleep(0.2, 0.9)


# from playwright.sync_api import sync_playwright

# def fetch_brave_html(query: str) -> str:
#     url = f"https://search.brave.com/search?q={query}"

#     with sync_playwright() as pw:
#         browser = pw.chromium.launch(headless=False)
#         context = browser.new_context(user_agent=random.choice(FINGERPRINT_PROFILES)["ua"], viewport={"width": 1280, "height": 900})
#         page = context.new_page()
#         page.goto(url, wait_until="domcontentloaded")

#         # Simple human-like scroll
#         for _ in range(3):
#             page.mouse.wheel(0, random.randint(300,700))
        
#         html = page.content()
#         browser.close()
#         return html



# from ollama import chat  # import the function, not a class

# def extract_results_with_tinylama(html: str) -> list:
#     prompt = f"""
#     You are a search engine result extractor.
#     Extract only REAL organic results from the HTML input.

#     Input HTML:
#     {html}

#     Return ONLY valid JSON in this format:
#     [
#       {{ "title": "...", "url": "...", "snippet": "..." }},
#       ...
#     ]
#     """
    
#     response = chat(
#         model="tinyllama",
#         messages=[{"role":"user","content":prompt}]
#     )
    
#     # Parse TinyLlama response into Python list
#     import json
#     try:
#         results = json.loads(response["message"]["content"])
#     except Exception:
#         results = []
#     print(results)
#     return results

# Different search engines
def get_brave_results(driver, query: str, max_results: int = 5) -> List[Dict]:
    url = f"https://search.brave.com/search?q={query}"
    driver.get(url)

    rand_sleep(1.2, 2.4)
    human_scroll(driver)

    # Updated targeting:
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

    # html = fetch_brave_html(query)
    # results = extract_results_with_tinylama(html)
    return results


def get_duckduckgo_results(driver, query: str, max_results: int = 5) -> List[Dict]:
    url = f"https://duckduckgo.com/?q={query}"
    driver.get(url)

    # human-like delay + scroll
    rand_sleep(1.0, 2.2)
    human_scroll(driver)

    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-testid='result-title-a']")))
    except Exception:
        logger.debug("DDG: wait timeout; proceeding with best-effort extraction")

    titles = driver.find_elements(By.CSS_SELECTOR, "a[data-testid='result-title-a']")
    snippets = driver.find_elements(By.CSS_SELECTOR, "[data-result='snippet']")
    display_urls = driver.find_elements(By.CSS_SELECTOR, "cite")
    favicons = driver.find_elements(By.CSS_SELECTOR, "img.favicon")

    results = []
    for i in range(min(max_results, max(len(titles), len(snippets)))):
        t = titles[i] if i < len(titles) else None
        s = snippets[i] if i < len(snippets) else None
        disp = display_urls[i] if i < len(display_urls) else None
        icon = favicons[i] if i < len(favicons) else None

        title = t.text.strip() if t else ""
        href = t.get_attribute("href") if t else None
        snippet_text = s.text.strip() if s else ""
        display_url = disp.text.strip() if disp else None
        favicon = icon.get_attribute("src") if icon else None

        results.append({
            "title": title,
            "url": href,
            "snippet": snippet_text,
            "display_url": display_url,
            "favicon": favicon
        })

    return results


def get_google_results(driver, query: str, max_results: int = 5):
    """Robust Google search scraper"""
    url = f"https://www.google.com/search?q={query}"
    driver.get(url)
    
    # Handle consent popups
    try:
        consent = driver.find_element(By.XPATH, "//button[contains(text(),'I agree') or contains(text(),'Accept all')]")
        consent.click()
        time.sleep(1)
    except:
        pass
    
    # Wait for search results to load
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.g, div.tF2Cxc, div.Ww4FFb"))
    )
    
    results = []
    blocks = driver.find_elements(By.CSS_SELECTOR, "div.g, div.tF2Cxc, div.Ww4FFb")
    
    seen_urls = set()
    
    for block in blocks:
        if len(results) >= max_results:
            break
        try:
            # Title
            try:
                title = block.find_element(By.TAG_NAME, "h3").text
            except:
                title = ""
            
            # URL
            try:
                url = block.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
            except:
                url = ""
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            
            # Snippet
            snippet = ""
            for sel in ["div.VwiC3b", "div.IsZvec", "div.s3v9rd"]:
                try:
                    snippet = block.find_element(By.CSS_SELECTOR, sel).text
                    if snippet:
                        break
                except:
                    continue
            
            results.append({
                "title": title,
                "url": url,
                "snippet": snippet
            })
        except:
            continue
    
    # Pad if needed
    while len(results) < max_results:
        results.append({"title": "", "url": None, "snippet": ""})
    
    return results
def get_bing_results(driver, query: str, max_results: int = 5) -> List[Dict]:
    url = f"https://www.bing.com/search?q={query}"
    driver.get(url)

    rand_sleep(1.5, 3.0)
    human_scroll(driver)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.b_algo"))
        )
    except Exception:
        logger.debug("Bing: wait timeout; proceeding with best-effort extraction")

    results = []
    blocks = driver.find_elements(By.CSS_SELECTOR, "li.b_algo")
    for block in blocks[:max_results]:
        try:
            title_el = block.find_element(By.TAG_NAME, "h2")
            link_el = title_el.find_element(By.TAG_NAME, "a")
            snippet_el = block.find_element(By.CSS_SELECTOR, "p")
        except Exception:
            continue
        results.append({
            "title": title_el.text.strip() if title_el else "",
            "url": link_el.get_attribute("href") if link_el else None,
            "snippet": snippet_el.text.strip() if snippet_el else ""
        })
    return results


def get_baidu_results(driver, query: str, max_results: int = 5) -> List[Dict]:
    url = f"https://www.baidu.com/s?wd={query}"
    driver.get(url)

    rand_sleep(1.5, 3.0)
    # scroll a few times to load more results
    for _ in range(2):
        human_scroll(driver)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.result, .c-container, .result-op"))
        )
    except Exception:
        logger.debug("Baidu: wait timeout; proceeding with best-effort extraction")

    results = []
    blocks = driver.find_elements(By.CSS_SELECTOR, "div.result.c-container, div.c-container, .result-op")

    for block in blocks:
        if len(results) >= max_results:
            break

        try:
            # === Title & URL ===
            title = ""
            url = None
            link_el = None
            title_selectors = ["h3 a", ".t a", ".c-title a", "a[target='_blank']", "a"]

            for selector in title_selectors:
                try:
                    link_el = block.find_element(By.CSS_SELECTOR, selector)
                    if link_el.text.strip() and link_el.get_attribute('href'):
                        title = link_el.text.strip()
                        url = link_el.get_attribute('href')
                        break
                except:
                    continue

            if not title or not url:
                # fallback: try any <a> inside block
                try:
                    link_el = block.find_element(By.TAG_NAME, "a")
                    title = link_el.text.strip()
                    url = link_el.get_attribute("href")
                except:
                    continue  # skip if no link

            # === Snippet ===
            snippet = ""
            snippet_selectors = [
                "div[data-module='abstract']", ".summary-text_560AM",
                "div[role='text']", ".cu-line-clamp-2",
                ".c-color-text", ".c-abstract",
                ".c-span18", ".op-bk-polysemy"
            ]
            for selector in snippet_selectors:
                try:
                    snippet_el = block.find_element(By.CSS_SELECTOR, selector)
                    snippet_text = snippet_el.text.strip()
                    if snippet_text:
                        import re
                        snippet_text = re.sub(r'\d{4}年\d{1,2}月\d{1,2}日', '', snippet_text)
                        snippet_text = re.sub(r'\s+', ' ', snippet_text).strip()
                        if snippet_text:
                            snippet = snippet_text
                            break
                except:
                    continue

            # fallback: use remaining block text
            if not snippet:
                full_text = block.text.strip()
                # remove title from block text
                if title in full_text:
                    full_text = full_text.replace(title, "")
                # pick first 1-2 lines as snippet
                lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                if lines:
                    snippet = " ".join(lines[:2])

            results.append({
                "title": title,
                "url": url,
                "snippet": snippet
            })

        except Exception as e:
            logger.debug(f"Baidu: failed to extract block: {e}")
            continue

    # if still less than max_results, pad with empty dicts
    while len(results) < max_results:
        results.append({"title": "", "url": None, "snippet": ""})

    return results



# Extend the main wrapper
def get_serp_results(query: str, engine: str = "duckduckgo", max_results: int = 5) -> List[Dict]:
    engine = engine.lower().strip()
    attempt = 0
    backoff = INITIAL_BACKOFF
    last_err = None

    while attempt < MAX_RETRIES:
        attempt += 1
        try:
            driver = create_driver()
            logger.info("Driver started (attempt %d). Engine=%s", attempt, engine)

            if engine == "duckduckgo":
                results = get_duckduckgo_results(driver, query, max_results)
            elif engine == "brave":
                results = get_brave_results(driver, query, max_results)
            elif engine == "google":
                results = get_google_results(driver, query, max_results)
            elif engine == "bing":
                results = get_bing_results(driver, query, max_results)
            elif engine == "baidu":
                results = get_baidu_results(driver, query, max_results)
            else:
                raise ValueError("Unsupported engine. Supported: duckduckgo, brave, google, bing, baidu")

            driver.quit()
            return results

        except Exception as e:
            last_err = e
            logger.warning("Attempt %d failed: %s", attempt, e)
            try:
                driver.quit()
            except Exception:
                pass
            rand_sleep(backoff * 0.8, backoff * 1.5)
            backoff *= 2.0

    logger.error("All attempts failed. Last error: %s", last_err)
    raise last_err



