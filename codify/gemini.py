import os
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()

def review_code(language, code):
    # Configure Gemini with API key
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    # Load Gemini Flash Lite model
    model = genai.GenerativeModel("gemini-2.5-flash-lite")

    # Prompt for AI
    prompt = f"""
    You are an expert code reviewer.

    Programming Language: {language}

    Review the following code and provide feedback on:
    1. Code quality
    2. Bugs and errors
    3. Improvements and best practices

    Code:
    {code}
    """

    # Generate response
    response = model.generate_content(prompt)

    # Return AI result
    return response.text

    print(settings.GEMINI_API_KEY)