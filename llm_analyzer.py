import os
import base64
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List, Optional, Union, Literal
import json

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(
    base_url="https://api.studio.nebius.com/v1/",
    api_key=os.environ.get("NEBIUS_API_KEY")
)

class ImageUrl(BaseModel):
    url: str

class ImageContent(BaseModel):
    type: Literal["image_url"]
    image_url: ImageUrl

class TextContent(BaseModel):
    type: Literal["text"]
    text: str

class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: Union[str, List[Union[TextContent, ImageContent]]]

class LLMResponse(BaseModel):
    issues_found: bool = Field(..., description="Whether any styling issues were found")
    details: str = Field(..., description="Description of any issues found or confirmation of no issues")

class AnalysisSummary(BaseModel):
    summary: str = Field(..., description="Brief summary of findings across all screenshots")
    common_issues: List[str] = Field(default_factory=list, description="List of issues that appear in multiple screenshots")
    overall_assessment: str = Field(..., description="Overall assessment of the website's styling")
    all_passed: bool = Field(..., description="True if all screenshots passed, False if any failed")

def parse_llm_response(text: str) -> LLMResponse:
    """Parse the LLM response text into a structured format."""
    try:
        # Extract the boolean value
        issues_found_line = next(line for line in text.split('\n') if line.startswith('ISSUES_FOUND:'))
        issues_found = issues_found_line.split(':', 1)[1].strip().lower() == 'true'
        
        # Extract the details
        details_line = next(line for line in text.split('\n') if line.startswith('DETAILS:'))
        details = details_line.split(':', 1)[1].strip()
        
        return LLMResponse(issues_found=issues_found, details=details)
    except Exception as e:
        print(f"Error parsing LLM response: {str(e)}")
        return LLMResponse(issues_found=False, details="Error parsing response")

def parse_summary_response(text: str, all_passed: bool) -> AnalysisSummary:
    """Parse the summary response text into a structured format."""
    try:
        lines = text.split('\n')
        summary = next(line.split(':', 1)[1].strip() for line in lines if line.startswith('SUMMARY:'))
        
        common_issues_line = next(line for line in lines if line.startswith('COMMON_ISSUES:'))
        common_issues = [issue.strip() for issue in common_issues_line.split(':', 1)[1].strip().split(',') if issue.strip()]
        
        overall_line = next(line for line in lines if line.startswith('OVERALL_ASSESSMENT:'))
        overall_assessment = overall_line.split(':', 1)[1].strip()
        
        return AnalysisSummary(
            summary=summary,
            common_issues=common_issues,
            overall_assessment=overall_assessment,
            all_passed=all_passed
        )
    except Exception as e:
        print(f"Error parsing summary response: {str(e)}")
        return AnalysisSummary(
            summary="Error parsing summary",
            common_issues=[],
            overall_assessment="Error parsing assessment",
            all_passed=all_passed
        )

def analyze_screenshots(screenshots: List[str]) -> str:
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
        ISSUES_FOUND: [true/false]
        DETAILS: [Brief description of any issues found, or "No serious styling issues found"]
        """
        
        individual_analyses = []
        issues_found_list = []
        
        # Analyze each screenshot
        for i, screenshot in enumerate(screenshots, 1):
            print(f"\nAnalyzing screenshot {i} of {len(screenshots)}...")
            
            # Add screenshot to the messages
            print(f'INFO: Processing screenshot {i} --> {screenshot}')
            with open(screenshot, 'rb') as img_file:
                base64_image = base64.b64encode(img_file.read()).decode('utf-8')
            
            # Create message with image
            messages = [
                {"role": "system", "content": prompt},
                {
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
                }
            ]
            
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
            
            # Parse the response
            analysis = parse_llm_response(response.choices[0].message.content)
            individual_analyses.append(f"Screenshot {i} Analysis:\n{analysis.model_dump_json(indent=2)}\n")
            issues_found_list.append(analysis.issues_found)
        
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
        
        # Parse the summary response
        all_passed = all(issues_found_list)
        summary = parse_summary_response(summary_response.choices[0].message.content, all_passed)
        
        # Combine individual analyses and summary
        final_response = "\n".join(individual_analyses) + "\n\nSUMMARY:\n" + summary.model_dump_json(indent=2)
        
        print("Analysis complete!")
        return final_response
        
    except Exception as e:
        print(f"Error analyzing screenshots: {str(e)}")
        return "Error: Could not analyze screenshots" 
        