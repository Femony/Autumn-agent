# step 0: import packages and modules %%
# step 1: get OpenAI API keys %%
# step 2: define tools for agents %%
# step 3: define the agents %%
# step 4: define helper functions


# step 0
#helps the functions/ agent to work asynchronously
import asyncio
import json
import time
import os
from openai import Agent, Runner, function_tool
from openai import OpenAI
from datetime import datetime, timedelta
from fpdf import FPDF
import yagmail
import schedule
from bs4 import BeautifulSoup
import requests
from dotenv import load_dotenv

# step 1

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")
FROM_NAME = os.getenv("FROM_NAME", "Autumn")
MODEL = os.getenv("MODEL", "gpt-5-mini") 
STORAGE_FILE = os.getenv("STORAGE_FILE", "storage.json")

if not OPENAI_API_KEY:
    raise RuntimeError("Set OPENAI_API_KEY in your .env first")

client = OpenAI(api_key=OPENAI_API_KEY)

# to help in storage 
def load_storage():
    """Loads the storage file where we store scraped article URLs."""
    if not os.path.exists(STORAGE_FILE):
        return {"articles": {}}  # url -> metadata
    with open(STORAGE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_storage(data):
    """Saves the updated scraped article list."""
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# step 2
# generate summaries from a website
# we are letting the ai model know that this function is not ordinary, but a tool that will help the agent

@function_tool
def fetch_blog_content(url: str) -> dict:

    print(f"Scraping: {url}")

    html = requests.get(url, timeout=10).text
    soup = BeautifulSoup(html, "html.parser")

    # extract titles
    titles = [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3'])]

    # extract paragraphs
    paragraphs = [p.get_text(strip=True) for p in soup.find_all('p')]

    content = "\n".join(paragraphs)

    return {
        "titles": titles,
        "content": content[:20000]  # safety limit
    }

#filtering function
def looks_like_article(url: str) -> bool:
    """
    Universal article detector for major tech/AI company blogs.
    """

    # MUST be long enough to be a real article
    if len(url) < 25:
        return False

    # EXCLUDE pages we never want
    blacklist = [
        "signup", "tag", "category", "author", "login",
        "privacy", "terms", "search", "events", "jobs",
        "careers", "press-contact"
    ]
    if any(b in url.lower() for b in blacklist):
        return False

    # INCLUDE if URL contains a year (most articles do)
    for year in ["2024", "2025", "2023", "2022"]:
        if year in url:
            return True

    # ACCEPT common article folders
    keywords = [
        "blog", "post", "news", "research", "article",
        "stories", "insights", "update", "announcements"
    ]
    if any(k in url.lower() for k in keywords):
        return True

    # ACCEPT URLs ending with slugs
    if url.rstrip("/").count("/") >= 4:
        return True

    return False

# to extract all subpages in a website

def extract_article_links(blog_url: str):
    print(f"[LINK SCRAPER] Fetching articles from: {blog_url}")

    html = requests.get(blog_url, timeout=10).text
    soup = BeautifulSoup(html, "html.parser")

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]

        # Skip useless or external links
        if "#" in href or "login" in href:
            continue

        # Convert relative → absolute
        if href.startswith("/"):
            href = blog_url.rstrip("/") + href

        # Basic filtering
        if looks_like_article(href):
            links.append(href)

    print(f"Found {len(links)} possible article links.")
    return list(set(links))  # unique list
# step 3: define the agent

Autumn = Agent(
    name = "Autumn",
    instructions="""You are a very reliable, valid, talented and authentic news_reporter agent for a STEM student.
                    STEM students in engineering and computer science rely on you to get all the latest advancements in their field to know how to move forward,
                    what fields to focus on, 
                    and what new opportunities can they take advantage of or work on.
                    Your job:
                    1. Use the "fetch_blog_content" tool to retrieve titles and article text from the given URL.
                    2. Clean the text (remove duplicates, boilerplate, navigation text).
                    3. Identify ALL new technological advancements, new features, new updates, new products, new technologies used mentioned on the page.
                    4. For each advancement, extract:
                    - What it is
                    - What problem it solves
                    - In what field it matters (AI, cloud, hardware, robotics, etc.)
                    - Why it is important for engineering or CS students
                    5. Write a 200 to 250 word concise summary.. 
                    OUTPUT FORMAT:
                    === REPORT START ===
                    [Company Name & Brief Relevance]
                    1. [Advancement Title]
                    - Description:
                    - Why it matters:
                    2. [Advancement Title]
                    - Description:
                    - Why it matters:

                    === DEFINITIONS ===
                    - Term: Definition
                    - Term: Definition
                    
                    === Conclusion === 
                    - State if there has been a strong appearance to a certain technology or feature based on the frequency it appeared in the article. 
                    Don't guess or make assumptions on your own.
                    === REPORT END ===

                    You must call the "fetch_blog_content" tool whenever you are provided with a URL.
                    Do NOT guess. Always fetch the real content first.""",
    model= "gpt-5-mini",
    tools=[fetch_blog_content],
    output_type=str
)

#fetch transcript from a website pag using tools and generates a structured summary
def summarize_blog(url: str):
    message = f"Please fetch and summarize the content from this URL: {url}"
    result = Autumn.run(message)
    return result

COMPANY_BLOGS = {
    "NVIDIA": "https://nvidianews.nvidia.com",
    "OpenAI": "https://openai.com/research",
    "Meta": "https://ai.meta.com/blog/",
    "Meta-research": "https://research.facebook.com",
    "Google": "https://blog.google/technology/ai/",
    "Microsoft": "https://blogs.microsoft.com",
    "Apple": "https://machinelearning.apple.com/",
    "Anthropic": "https://www.anthropic.com/news",
    "Cursor": "https://cursor.com/blog"
}

def summarize_all_companies():
    """
    Runs the Autumn agent on ALL companies,
    generates one BIG combined report,
    and returns the combined text.
    """

    final_report = []
    final_report.append("=== DAILY AI & TECH REPORT ===\n")
    final_report.append("This report contains updates from: NVIDIA, OpenAI, Meta, Google, Microsoft, Apple, Anthropic, Cursor.\n")
    final_report.append("Generated by Autumn.\n\n")

    for company, url in COMPANY_BLOGS.items():
        print(f"\n--- Summarizing: {company} ---")

        try:
            summaries = scrape_full_blog(url)
            final_report.append("\n".join(summaries))
            final_report.append(f"\n\n==============================")
            final_report.append(f"\n{company} — Latest Updates")
            final_report.append("\n==============================\n")
            final_report.append(summary)
        
        except Exception as e:
            final_report.append(f"\n\n{company}: FAILED TO SCRAPE ({e})")

    return "\n".join(final_report)

# NEW: A — MULTI-PAGE SCRAPER PIPELINE

def scrape_full_blog(blog_home_url: str):
    """
    1. Extract article links
    2. Summarize each new article
    3. Save results into storage
    """
    storage = load_storage()
    already = storage["articles"]

    to_visit = extract_article_links(blog_home_url)

    new_summaries = []

    for url in to_visit:
        if url in already:
            continue  # already scraped

        print(f"\n[NEW ARTICLE] {url}")

        try:
            summary = summarize_blog(url)
            already[url] = {
                "date": str(datetime.now()),
                "summary": summary
            }
            new_summaries.append(summary)

            save_storage(storage)
        except Exception as e:
            print(f"Error summarizing {url}: {e}")

    return new_summaries

# generating the pdf and sends a weekly email
def make_pdf(summaries, pdf_path="weekly_report.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for s in summaries:
        pdf.multi_cell(0, 10, s)
        pdf.ln(10)

    pdf.output(pdf_path)
    return pdf_path


def send_weekly_email(summaries):
    """
    Sends a PDF digest of weekly summaries.
    """
    if not summaries:
        print("No summaries to send this week.")
        return

    pdf_path = make_pdf(summaries)

    yag = yagmail.SMTP(EMAIL_USER, EMAIL_PASS)

    yag.send(
        to=RECIPIENT_EMAIL,
        subject="Your Weekly Tech Digest – Autumn",
        contents="Attached is your weekly PDF report with all new summaries.",
        attachments=pdf_path
    )

    print("Weekly report sent ✔")


#schedular
# for daily scraping
def run_daily():
    print("[Daily Job] Scraping all companies...")
    summaries = []
    for company, url in COMPANY_BLOGS.items():
        print(f"[SCRAPING] {company}")
        s = scrape_full_blog(url)
        summaries.extend(s)
    return summaries

#the weekly script
def run_weekly():
    print("[Weekly Job] Sending weekly email...")
    storage = load_storage()
    
    # collect only this week's articles
    week_ago = datetime.now() - timedelta(days=7)

    weekly_summaries = []
    for url, meta in storage["articles"].items():
        date = datetime.fromisoformat(meta["date"])
        if date > week_ago:
            weekly_summaries.append(meta["summary"])

    send_weekly_email(weekly_summaries)


schedule.every().day.at("09:00").do(run_daily)        # daily scraping
schedule.every().friday.at("18:00").do(run_weekly)    # weekly report


def scheduler_loop():
    while True:
        schedule.run_pending()
        time.sleep(60)





