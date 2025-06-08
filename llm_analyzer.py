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
        
        individual_analyses = []
        
        # Analyze each screenshot
        for i, screenshot in enumerate(screenshots, 1):
            print(f"\nAnalyzing screenshot {i} of {len(screenshots)}...")
            
            # Prepare messages for the API
            messages = [
                {"role": "system", "content": prompt}
            ]
            
            # Add screenshot to the messages
            print(f'INFO: Processing screenshot {i} --> {screenshot}')
            with open(screenshot, 'rb') as img_file:
                base64_image = base64.b64encode(img_file.read()).decode('utf-8')
                
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Analyze screenshot {i}:"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    }
                ]
            })
            
            # Make the API call for this screenshot
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
            
            analysis = response.choices[0].message.content
            individual_analyses.append(f"Screenshot {i} Analysis:\n{analysis}\n")
        
        # Generate summary of all analyses
        summary_prompt = f"""Please provide a summary of the following screenshot analyses. 
        Focus on identifying any patterns or common issues across the screenshots.
        
        Here are the individual analyses:
        {'\n'.join(individual_analyses)}
        
        Format your response as:
        SUMMARY: [Brief summary of findings across all screenshots]
        COMMON_ISSUES: [List any issues that appear in multiple screenshots]
        OVERALL_ASSESSMENT: [Overall assessment of the website's styling]
        """
        
        summary_messages = [
            {"role": "system", "content": "You are a web design analysis assistant that provides clear summaries of styling issues."},
            {"role": "user", "content": summary_prompt}
        ]
        
        summary_response = client.chat.completions.create(
            model="google/gemma-3-27b-it",
            max_tokens=512,
            temperature=0.5,
            top_p=0.9,
            extra_body={
                "top_k": 50
            },
            messages=summary_messages
        )
        
        # Combine individual analyses and summary
        final_response = "\n".join(individual_analyses) + "\n\nSUMMARY:\n" + summary_response.choices[0].message.content
        
        print("Analysis complete!")
        return final_response
        
    except Exception as e:
        print(f"Error analyzing screenshots: {str(e)}")
        return "Error: Could not analyze screenshots" 
        