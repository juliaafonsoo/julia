import agentql
from playwright.sync_api import sync_playwright


with sync_playwright() as playwright, playwright.chromium.launch(headless=False) as browser:
    page = agentql.wrap(browser.new_page())
    page.goto("https://scrapeme.live/shop/")

    QUERY = """
    {
        search_box
    }
    """

    response = page.query_elements(QUERY)

    response.search_box.fill("fish")
    page.keyboard.press("Enter")

    # Used only for demo purposes. It allows you to see the effect of script.
    page.wait_for_timeout(10000)