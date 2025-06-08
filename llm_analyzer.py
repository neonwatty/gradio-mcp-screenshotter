import os
import base64
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(
    base_url="https://api.studio.nebius.com/v1/",
    api_key=os.environ.get("NEBIUS_API_KEY")
)

def analyze_screenshots(screenshots):
    """Analyze screenshots for styling issues using LLM."""
    try:
        print("\nAnalyzing screenshots for styling issues...")
        
        # Prepare the prompt
        prompt = """Please analyze these website screenshots for any serious styling issues. 
        Focus only on identifying clear, objective styling problems such as:
        - Text that is completely unreadable
        - Elements that are severely misaligned
        - Content that is completely cut off
        - Major layout breaks
        - Critical accessibility issues
        
        Do not make subjective judgments about design preferences or potential improvements.
        Simply identify if there are any serious styling problems that would affect usability.
        
        Format your response as:
        ISSUES_FOUND: [True/False]
        DETAILS: [Brief description of any issues found, or "No serious styling issues found"]
        """
        
        # Prepare messages for the API
        messages = [
            {"role": "system", "content": "You are a web design analysis assistant that identifies serious styling issues."},
            {"role": "user", "content": prompt}
        ]
        
        # Add screenshots to the messages
        for screenshot in screenshots:
            if isinstance(screenshot, str):  # If it's a file path
                with open(screenshot, 'rb') as img_file:
                    base64_image = base64.b64encode(img_file.read()).decode('utf-8')
            else:  # If it's already base64
                base64_image = screenshot
                
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this screenshot:"},
                    {"type": "image_url", "image_url": f"data:image/png;base64,{base64_image}"}
                ]
            })
        
        # Make the API call
        response = client.chat.completions.create(
            model="google/gemma-3-27b-it",
            max_tokens=512,
            temperature=0.5,
            top_p=0.9,
            extra_body={
                "top_k": 50
            },
            messages=messages
        )
        
        print("Analysis complete!")
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"Error analyzing screenshots: {str(e)}")
        return "Error: Could not analyze screenshots" 