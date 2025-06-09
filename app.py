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
import json

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
    
    # Configure WebDriver Manager environment variables
    os.environ['WDM_LOCAL'] = '1'
    os.environ['WDM_SSL_VERIFY'] = '0'
    os.environ['WDM_PATH'] = '/tmp/.wdm'
    
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

def analyze_screenshots_handler(desktop_screenshots, mobile_screenshots):
    """Handler for analyzing screenshots with LLM."""
    print("\nStarting LLM analysis of screenshots...")
    
    # Check if there are any screenshots
    if not desktop_screenshots and not mobile_screenshots:
        return "⚠️ No screenshots available for analysis. Please generate screenshots first."
    
    all_screenshots = [s[0] for s in desktop_screenshots + mobile_screenshots]
    analysis_results = analyze_screenshots(all_screenshots)
    
    # Parse the analysis results into a structured format
    try:
        # Split the analysis into individual screenshot analyses and summary
        parts = analysis_results.split("\n\nSUMMARY:\n")
        individual_analyses = parts[0].strip().split("\n\n")
        summary = parts[1] if len(parts) > 1 else ""
        
        # Create HTML for the analysis display
        html_output = """
        <div class="analysis-container">
            <div class="summary-card">
                <h3>📊 Overall Analysis</h3>
                <div class="summary-content">
        """
        
        # Add summary section
        if summary:
            try:
                summary_data = json.loads(summary)
                html_output += f"""
                    <div class="summary-item">
                        <h4>Summary</h4>
                        <p>{summary_data.get('summary', 'No summary available')}</p>
                    </div>
                    <div class="summary-item">
                        <h4>Common Issues</h4>
                        <div class="issue-tags">
                """
                
                for issue in summary_data.get('common_issues', []):
                    html_output += f'<span class="issue-tag">{issue}</span>'
                
                html_output += """
                        </div>
                    </div>
                    <div class="summary-item">
                        <h4>Overall Assessment</h4>
                        <p>{}</p>
                    </div>
                """.format(summary_data.get('overall_assessment', 'No assessment available'))
            except json.JSONDecodeError:
                html_output += "<p>Error parsing summary data</p>"
        
        html_output += """
                </div>
            </div>
            
            <div class="screenshot-analyses">
                <h3>🔍 Detailed Analysis</h3>
        """
        
        # Add individual screenshot analyses
        for analysis in individual_analyses:
            if "Screenshot" in analysis:
                try:
                    # Extract screenshot number and analysis data
                    screenshot_num = analysis.split("Screenshot")[1].split("Analysis")[0].strip()
                    analysis_data = json.loads(analysis.split("Analysis:\n")[1])
                    
                    # Determine status color
                    status_color = "red" if analysis_data.get('issues_found', False) else "green"
                    status_icon = "⚠️" if analysis_data.get('issues_found', False) else "✅"
                    
                    html_output += f"""
                        <div class="analysis-card">
                            <div class="analysis-header">
                                <h4>Screenshot {screenshot_num}</h4>
                                <span class="status-indicator" style="color: {status_color}">
                                    {status_icon}
                                </span>
                            </div>
                            <div class="analysis-content">
                                <p>{analysis_data.get('details', 'No details available')}</p>
                            </div>
                        </div>
                    """
                except json.JSONDecodeError:
                    html_output += f"""
                        <div class="analysis-card">
                            <div class="analysis-header">
                                <h4>Screenshot {screenshot_num}</h4>
                                <span class="status-indicator">❓</span>
                            </div>
                            <div class="analysis-content">
                                <p>Error parsing analysis data</p>
                            </div>
                        </div>
                    """
        
        html_output += """
            </div>
        </div>
        
        <style>
            .analysis-container {
                background: #f5f6fa;
                color: #222;
            }
            .summary-card, .analysis-card, .summary-item {
                background: #fff;
                color: #222;
                border-left: 4px solid #6c63ff;
            }
            .issue-tag {
                background: #e6e4ff;
                color: #6c63ff;
            }
            /* ...other light mode styles... */
            @media (prefers-color-scheme: dark) {
                .analysis-container {
                    background: #181a20;
                    color: #f5f6fa;
                }
                .summary-card, .analysis-card, .summary-item {
                    background: #23272f;
                    color: #f5f6fa;
                    border-left: 4px solid #6c63ff;
                }
                .issue-tag {
                    background: #2d254d;
                    color: #a99cff;
                }
                /* ...other dark mode styles... */
            }
            .summary-content {
                display: grid;
                gap: 20px;
            }
            .issue-tags {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
            }
            .screenshot-analyses {
                display: grid;
                gap: 15px;
            }
            .analysis-card {
                border-radius: 10px;
                padding: 16px;
                box-shadow: 0 1px 4px rgba(108, 99, 255, 0.08);
                margin-bottom: 16px;
            }
            .analysis-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 10px;
            }
            .analysis-header h4 {
                margin: 0;
                color: #6c63ff;
            }
            .status-indicator {
                font-size: 1.3em;
                font-weight: bold;
            }
            .analysis-content {
                line-height: 1.5;
            }
        </style>
        """
        
        return html_output
    except Exception as e:
        return f"Error formatting analysis results: {str(e)}"

# Create Gradio interface
with gr.Blocks(title="Website Screenshot Tool", theme=gr.themes.Soft()) as demo:
    with gr.Column(scale=1, min_width=800):
        gr.Markdown("""
# 🌐 Website Screenshot Tool
### Capture and analyze your website's appearance across different devices
""", elem_classes=["header"])
        
        gr.Markdown("Note: Only one user can process screenshots at a time. Please wait if the queue is busy.")
        
        # Top Row - Screenshotting
        with gr.Row():
            # URL Input Section
            url_input = gr.Textbox(
                label="Web Address",
                placeholder="Enter a web address (e.g., example.com)",
                info="Make sure to include http:// or https://",
                elem_classes=["input-field"]
            )
            submit_btn = gr.Button(
                "Generate Screenshots",
                variant="primary",
                elem_classes=["action-button"]
            )
        
        with gr.Row():
            # Desktop Screenshots Section
            with gr.Column():
                gr.Markdown("## Desktop Screenshots")
                desktop_gallery = gr.Gallery(
                    label="Desktop View",
                    show_label=True,
                    elem_id="desktop_gallery",
                    columns=[3],  # More flexible layout
                    rows=[3],
                    height="auto",
                    object_fit="contain",
                    elem_classes=["gallery"]
                )
            
            # Mobile Screenshots Section
            with gr.Column():
                gr.Markdown("## Mobile Screenshots")
                mobile_gallery = gr.Gallery(
                    label="Mobile View",
                    show_label=True,
                    elem_id="mobile_gallery",
                    columns=[3],  # More flexible layout
                    rows=[3],
                    height="auto",
                    object_fit="contain",
                    elem_classes=["gallery"]
                )
        
        # Bottom Row - Analysis
        with gr.Row():
            with gr.Group(elem_classes=["analysis-container"]):
                gr.Markdown("---")  # Horizontal line separator
                gr.Markdown("## LLM Analysis Results")
                gr.Markdown("")  # Add empty line for spacing
                gr.Markdown("")  # Add another empty line for more spacing
                analyze_btn = gr.Button(
                    "Analyze Screenshots with LLM",
                    variant="primary",
                    elem_classes=["action-button"],
                    scale=1,
                    min_width=200
                )
                analysis_output = gr.HTML(
                    label="Analysis Results",
                    show_label=True,
                    elem_classes=["analysis-results"],
                    value=" "  # Add a space to ensure minimum height
                )
    
    # UI handlers
    def ui_handler(url):
        if not url:
            raise gr.Error("Please enter a valid URL")
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            print(f"Added https:// prefix to URL")
        try:
            return process_url(url, return_base64=False)
        except Exception as e:
            raise gr.Error(f"Error processing URL: {str(e)}")
    
    # API handler
    def api_handler(url):
        if not url:
            raise gr.Error("Please enter a valid URL")
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        try:
            return process_url(url, return_base64=True)
        except Exception as e:
            raise gr.Error(f"Error processing URL: {str(e)}")
    
    # Register handlers
    submit_btn.click(
        fn=ui_handler,
        inputs=url_input,
        outputs=[desktop_gallery, mobile_gallery],
        queue=True,
        concurrency_limit=1,
        show_progress=True
    )
    
    analyze_btn.click(
        fn=analyze_screenshots_handler,
        inputs=[desktop_gallery, mobile_gallery],
        outputs=analysis_output,
        queue=True,
        concurrency_limit=1,
        show_progress=True
    )
    
    # Expose API endpoint
    demo.launch(share=True)

if __name__ == "__main__":
    print("\nStarting Website Screenshot Tool...")
    print("Initializing Gradio interface...")
    demo.queue().launch() 