from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import CodeReview
from .gemini import review_code
from django.views.decorators.csrf import csrf_exempt
import json
from django.http import JsonResponse
import os
import google.generativeai as genai
from dotenv import load_dotenv
import re
from django.contrib.auth import logout

def home(request):
    return render(request, 'home.html')

@login_required(login_url="/login/")
def dashboard(request):

    if request.method == "POST":
        code = request.POST.get("code")
        language = request.POST.get("language")

        ai_result = review_code(language, code)

        # Save history (KEEPING THIS AS YOU REQUIRED)
        CodeReview.objects.create(
            user=request.user,
            code=code,
            language=language,
            ai_result=ai_result
        )

        # Store result temporarily in session
        request.session["ai_result"] = ai_result

        return redirect("dashboard")

    # ================= GET REQUEST =================

    ai_result = request.session.pop("ai_result", None)

    sections = None  # Default if no AI result
    if ai_result:
        sections = {
            "score": "",
            "errors": "",
            "improvements": "",
            "explanation": "",
            "final_code": "",
        }

        current_section = None

        for line in ai_result.splitlines():

            clean_line = line.strip().lower()

            # ---- DETECTION (Flexible) ----

            if "score" in clean_line:
                current_section = "score"
                continue

            elif "error" in clean_line or "bug" in clean_line:
                current_section = "errors"
                continue

            elif "improvement" in clean_line or "best practice" in clean_line:
                current_section = "improvements"
                continue

            elif "line by line" in clean_line or "line-by-line" in clean_line:
                current_section = "explanation"
                continue

            elif "final" in clean_line and "code" in clean_line:
                current_section = "final_code"
                continue

            # ---- ADD CONTENT ----

            if current_section:
                sections[current_section] += line + "\n"
    return render(request, "dashboard.html", {
        "sections": sections
    })

def logout_page(request):
    logout(request)
    return redirect("home")

def login_page(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            return render(request, 'login.html', {
                'error': 'Invalid username or password'
            })

    return render(request, 'login.html')


def register_page(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        if User.objects.filter(username=username).exists():
            return render(request, 'register.html', {
                'error': 'Username already exists'
            })

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        user.first_name = full_name
        user.save()

        return redirect('login_page')

    return render(request, 'register.html')


@login_required
def history(request):
    reviews = CodeReview.objects.filter(user=request.user).order_by('-created_at')
    return render(request, "history.html", {"reviews": reviews})


def chatbot_page(request):
    return render(request, "chatbot.html")


# ================== GEMINI SETUP ==================

load_dotenv()

genai.configure(
    api_key=os.getenv("GEMINI_API_KEY")
)

model = genai.GenerativeModel("gemini-2.5-flash")


# ================== CLEAN AI OUTPUT ==================

def clean_ai_text(text):
    # Remove markdown symbols like **** ### ``` etc
    text = re.sub(r'[`#*_>-]+', '', text)
    text = re.sub(r'\n{2,}', '\n', text)
    return text.strip()


# ================== CHATBOT API  ==================

@csrf_exempt
def chatbot_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_message = data.get("message", "").strip()

            if not user_message:
                return JsonResponse({"reply": "Please enter a question."})

            prompt = f"""
You are CODIFY AI CHATBOT.

Your role:
- Help users with programming, coding, debugging, and computer science concepts.
- Support beginners as well as intermediate learners.
- Focus mainly on programming languages, code errors, logic building, and writing programs.

General Rules:
- Always be clear, simple, and beginner-friendly.
- Avoid unnecessary technical jargon unless required.
- Do NOT use markdown symbols like **, ##, ###, ``` or special formatting characters.
- Keep responses clean and readable.

Response Behavior:

1) Greetings:
- If the user greets (hello, hi, hey, good morning, etc.),
  respond politely and introduce yourself as:
  "Hello! I am CODIFY AI CHATBOT. How can I help you with programming today?"

2) Normal Concept Questions:
- When the user asks general programming or theory questions,
  explain the answer in clear KEY POINTS.
- Use numbered or bullet-style plain text points.

3) Difference / Comparison Questions:
- If the user asks about differences (example: difference between list and tuple),
  present the answer in a TABLE format using plain text.
- Include columns such as Feature, Option 1, Option 2.

4) Code Error / Debugging:
- If the user provides code:
  - First, identify errors line by line.
  - Clearly explain what is wrong and why.
  - Suggest improvements.
  - Finally, provide the corrected and optimized code.

5) Program Writing Requests:
- If the user asks to write a program:
  - Explain the logic briefly.
  - Then provide clean, correct code.
  - Keep the code readable and well-structured.

6) Flowchart Required:
- If a question requires a flowchart:
  - Represent the flowchart in TEXT form using arrows.
  - Example:
    Start -> Input -> Process -> Output -> End

7) Output Quality:
- Keep answers structured.
- Avoid long paragraphs.
- Use spacing and short sections for clarity.

Your goal:
- Act like a friendly coding mentor.
- Make learning programming easy, logical, and enjoyable.
User Question:
{user_message}
"""

            response = model.generate_content(prompt)

            
            clean_reply = clean_ai_text(response.text)

            return JsonResponse({
                "reply": clean_reply
            })

        except Exception as e:
            return JsonResponse({
                "reply": f"Error: {str(e)}"
            })

    return JsonResponse({"reply": "Invalid request"}, status=400)

def clean_ai_text(text):
    if not text:
        return ""
    # Remove markdown symbols
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)  # remove code fences
    text = re.sub(r'[#*_`-]+', '', text)                  # remove markdown chars
    text = re.sub(r'\n{2,}', '\n', text)                   # remove extra lines
    return text.strip()