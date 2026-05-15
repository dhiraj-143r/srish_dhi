"""
InboxPilot — Firecrawl Tool Wrapper
Web scraping and research capabilities using Firecrawl API.
Converts messy web pages into clean, LLM-ready content.
"""
import logging
from firecrawl import FirecrawlApp
from config import config

logger = logging.getLogger("inbox-pilot.tools.firecrawl")

# Initialize Firecrawl client
app = FirecrawlApp(api_key=config.FIRECRAWL_API_KEY)


async def scrape_url(url: str) -> dict:
    """Scrape a URL and return clean markdown content."""
    try:
        result = app.scrape(url, params={"formats": ["markdown"]})
        return {
            "url": url,
            "status": "success",
            "content": result.get("markdown", ""),
            "title": result.get("metadata", {}).get("title", ""),
            "description": result.get("metadata", {}).get("description", ""),
        }
    except Exception as e:
        logger.error(f"Failed to scrape {url}: {e}")
        return {"url": url, "status": "failed", "error": str(e), "content": ""}


async def research_sender(email_address: str) -> dict:
    """Research a sender by scraping their company website and profile."""
    domain = email_address.split("@")[-1] if "@" in email_address else ""
    research = {
        "email": email_address,
        "domain": domain,
        "company_info": None,
        "findings": [],
    }

    if not domain or domain in ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "agentmail.to"]:
        research["findings"].append("Sender uses a personal email provider — no company website to scrape.")
        return research

    # Scrape company website
    try:
        company_url = f"https://{domain}"
        company_data = await scrape_url(company_url)
        if company_data["status"] == "success":
            # Truncate to avoid token limits
            content = company_data["content"][:3000]
            research["company_info"] = {
                "url": company_url,
                "title": company_data.get("title", ""),
                "description": company_data.get("description", ""),
                "content_preview": content,
            }
            research["findings"].append(f"Scraped company website: {company_url}")
    except Exception as e:
        logger.warning(f"Failed to scrape company site for {domain}: {e}")
        research["findings"].append(f"Could not access company website: {domain}")

    return research


async def scrape_urls_from_email(urls: list[str]) -> list[dict]:
    """Scrape multiple URLs found in an email body."""
    results = []
    for url in urls[:3]:  # Limit to 3 URLs to avoid rate limits
        try:
            data = await scrape_url(url)
            results.append(data)
        except Exception as e:
            results.append({"url": url, "status": "failed", "error": str(e)})
    return results
