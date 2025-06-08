import gradio as gr
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse, urljoin
import os
import time
from concurrent.futures import ThreadPoolExecutor
import tempfile
import base64
from io import BytesIO
from PIL import Image
import atexit
import shutil
from llm_analyzer import analyze_screenshots

# Define viewport sizes
VIEWPORT_SIZES = {
    'desktop': (1920, 1080),
    'mobile': (375, 812)  # iPhone X dimensions
}

# Keep track of temporary files for cleanup
temp_files = set()

def cleanup_temp_files():
    """Clean up all temporary files created during the session."""
    print("\nCleaning up temporary files...")
    for file_path in temp_files:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Removed temporary file: {file_path}")
        except Exception as e:
            print(f"Error removing temporary file {file_path}: {str(e)}")

# Register cleanup function to run on exit
atexit.register(cleanup_temp_files)

def setup_driver(viewport_type='desktop'):
    """Set up and return a configured Chrome WebDriver."""
    print(f"Setting up Chrome WebDriver for {viewport_type} view...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Set viewport size
    width, height = VIEWPORT_SIZES[viewport_type]
    chrome_options.add_argument(f"--window-size={width},{height}")
    
    # Add mobile emulation for mobile view
    if viewport_type == 'mobile':
        mobile_emulation = {
            "deviceMetrics": {"width": width, "height": height, "pixelRatio": 3.0},
            "userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
        }
        chrome_options.add_experimental_option("mobileEmulation", mobile_emulation)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    print(f"Chrome WebDriver setup complete for {viewport_type} view!")
    return driver

def get_urls(url):
    """Extract both subdomains and paths from a given URL."""
    try:
        print(f"\nStarting URL discovery for {url}...")
        # Parse the main domain
        parsed_url = urlparse(url)
        main_domain = parsed_url.netloc
        
        # Get the base domain (e.g., example.com from sub.example.com)
        parts = main_domain.split('.')
        if len(parts) > 2:
            base_domain = '.'.join(parts[-2:])
        else:
            base_domain = main_domain
            
        print(f"Base domain identified: {base_domain}")
        
        # Make a request to the main domain
        print("Fetching main page content...")
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all links
        print("Analyzing page for URLs...")
        urls = set()
        
        # Process all links
        for link in soup.find_all('a'):
            href = link.get('href')
            if href:
                try:
                    # Convert relative URLs to absolute
                    full_url = urljoin(url, href)
                    parsed_href = urlparse(full_url)
                    
                    # Add if it's a subdomain or path of our base domain
                    if parsed_href.netloc and base_domain in parsed_href.netloc:
                        urls.add(full_url)
                except:
                    continue
        
        # Add the main URL if it's not already included
        urls.add(url)
        
        # Convert to list and sort
        url_list = sorted(list(urls))
        print(f"Found {len(url_list)} URLs:")
        for found_url in url_list:
            print(f"  - {found_url}")
        return url_list
    except Exception as e:
        print(f"Error getting URLs: {str(e)}")
        return [url]

def take_screenshot(url, viewport_type='desktop', return_base64=False):
    """Take a screenshot of a given URL with specified viewport."""
    try:
        print(f"\nTaking {viewport_type} screenshot of {url}...")
        driver = setup_driver(viewport_type)
        print(f"Navigating to {url}")
        driver.get(url)
        print("Waiting for page to load...")
        time.sleep(2)  # Wait for page to load
        
        # Take screenshot to memory
        screenshot = driver.get_screenshot_as_png()
        driver.quit()
        
        if return_base64:
            # Return base64 encoded image for API/MCP
            base64_screenshot = base64.b64encode(screenshot).decode('utf-8')
            return base64_screenshot
        else:
            # Save to temporary file for UI display
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp.write(screenshot)
                screenshot_path = tmp.name
                temp_files.add(screenshot_path)  # Track for cleanup
            return screenshot_path
            
    except Exception as e:
        print(f"Error taking {viewport_type} screenshot of {url}: {str(e)}")
        if 'driver' in locals():
            driver.quit()
        return None

def process_url(url, return_base64=False):
    """Process a URL and return screenshots of all discovered URLs."""
    print(f"\n{'='*50}")
    print(f"Starting process for URL: {url}")
    print(f"{'='*50}")
    
    # Ensure URL has proper format
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        print(f"Added https:// prefix to URL")
    
    # Get URLs
    urls = get_urls(url)
    
    # Take screenshots in parallel for both desktop and mobile
    desktop_screenshots = []
    mobile_screenshots = []
    
    for viewport_type in ['desktop', 'mobile']:
        print(f"\nStarting parallel {viewport_type} screenshot capture of {len(urls)} URLs...")
        with ThreadPoolExecutor(max_workers=5) as executor:
            screenshot_paths = list(executor.map(
                lambda url: take_screenshot(url, viewport_type, return_base64),
                urls
            ))
        
        # Filter out None values and create gallery items
        print(f"\nProcessing {viewport_type} results...")
        for found_url, screenshot in zip(urls, screenshot_paths):
            if screenshot:
                if viewport_type == 'desktop':
                    desktop_screenshots.append((screenshot, f"URL: {found_url}"))
                else:
                    mobile_screenshots.append((screenshot, f"URL: {found_url}"))
    
    print(f"\nSuccessfully captured {len(desktop_screenshots)} desktop and {len(mobile_screenshots)} mobile screenshots")
    print(f"{'='*50}\n")
    return desktop_screenshots, mobile_screenshots

# Create Gradio interface
with gr.Blocks(title="Website Screenshot Tool") as demo:
    gr.Markdown("# Website Screenshot Tool")
    gr.Markdown("Enter a web address to get screenshots of all its pages and subdomains in both desktop and mobile views.")
    gr.Markdown("Note: Only one user can process screenshots at a time. Please wait if the queue is busy.")
    
    with gr.Row():
        url_input = gr.Textbox(label="Web Address", placeholder="Enter a web address (e.g., example.com)")
        submit_btn = gr.Button("Generate Screenshots")
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("## Desktop Screenshots")
            desktop_gallery = gr.Gallery(
                label="Desktop View",
                show_label=True,
                elem_id="desktop_gallery",
                columns=[2],
                rows=[2],
                height="auto"
            )
        
        with gr.Column():
            gr.Markdown("## Mobile Screenshots")
            mobile_gallery = gr.Gallery(
                label="Mobile View",
                show_label=True,
                elem_id="mobile_gallery",
                columns=[2],
                rows=[2],
                height="auto"
            )
    
    # UI handler
    def ui_handler(url):
        return process_url(url, return_base64=False)
    
    # API handler
    def api_handler(url):
        return process_url(url, return_base64=True)
    
    # Register both handlers
    submit_btn.click(
        fn=ui_handler,
        inputs=url_input,
        outputs=[desktop_gallery, mobile_gallery],
        queue=True,
        concurrency_limit=1
    )
    
    # Expose API endpoint
    demo.launch(share=True)

if __name__ == "__main__":
    print("\nStarting Website Screenshot Tool...")
    print("Initializing Gradio interface...")
    demo.queue().launch() 