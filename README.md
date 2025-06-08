# Subdomain Screenshot Tool

This is a Gradio application that allows users to input a web address and get screenshots of its subdomains. The tool uses Selenium with Chrome in headless mode to capture screenshots and BeautifulSoup to crawl for subdomains.

## Prerequisites

- Python 3.11 or higher
- Chrome browser installed
- pip (Python package installer)

## Installation

1. Clone this repository or download the files
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

1. Run the application:

```bash
python app.py
```

2. Open your web browser and navigate to the URL shown in the terminal (typically http://127.0.0.1:7860)

3. Enter a web address in the input field (e.g., "example.com")

4. Click "Generate Screenshots" to start the process

5. The application will:
   - Crawl the website to find subdomains
   - Take screenshots of each subdomain
   - Display the results in a gallery view

## Features

- Parallel processing of screenshots for faster results
- Headless browser operation
- Automatic subdomain detection
- Clean and intuitive user interface
- Temporary file management for screenshots

## Notes

- The application requires an internet connection
- Some websites may block automated access
- Processing time depends on the number of subdomains and their loading times
- Screenshots are taken at 1920x1080 resolution
