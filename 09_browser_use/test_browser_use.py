"""
AgentCore Browser Use — Automate web form filling with Playwright

This script demonstrates how to:
1. Run the cost estimator agent to generate an AWS cost estimation
2. Open a managed Chrome browser via AgentCore Browser
3. Discover form fields dynamically using accessibility snapshots
4. Use Bedrock to intelligently map estimation data to form fields
5. Fill and submit the form via Playwright (sync API)
6. Verify each step with screenshots saved to disk

Use case: Register estimation results into web-based project management systems
that only expose HTML forms — no API, no MCP, no Gateway.

Reference:
https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-building-agents.html
"""

import argparse
import json
import logging
import os
import re
import sys
import time

import boto3
from bedrock_agentcore.tools.browser_client import browser_session
from playwright.sync_api import BrowserType, Page, Playwright, sync_playwright

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "01_code_interpreter"))
from cost_estimator_agent.cost_estimator_agent import AWSCostEstimatorAgent  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_FORM_URL = "https://pulse.aws/survey/QBRDHJJC"
POST_SUBMIT_WAIT = 15
MAX_FIELD_CHARS = 50
CHUNK_SIZE = 20
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")


def run_cost_estimation(architecture: str, region: str) -> str:
    """Run the cost estimator agent and return the raw estimation text."""
    cost_estimator = AWSCostEstimatorAgent(region=region)
    logger.info("Running cost estimation for: %s", architecture)
    result = cost_estimator.estimate_costs(architecture)
    logger.info("Cost estimation complete (%d chars)", len(result))
    return result


def discover_form_fields(page: Page) -> str:
    """Capture the form's accessibility tree as text.

    Uses Playwright's aria_snapshot() to get a readable representation
    of all form elements including textboxes, radio groups, and buttons.
    Bedrock parses this directly to map estimation data to fields.
    """
    return page.locator("body").aria_snapshot()


def generate_form_values(
    estimation_text: str,
    form_snapshot: str,
    region: str,
    signature: str = "",
) -> dict:
    """Use Bedrock to map estimation data to the discovered form fields.

    Sends the aria snapshot and the cost estimation text to the Bedrock
    Converse API, which returns a JSON mapping of field names to values.
    """
    bedrock_runtime = boto3.client("bedrock-runtime", region_name=region)
    model_id = "us.anthropic.claude-sonnet-4-20250514-v1:0"

    extra_context = ""
    if signature:
        extra_context = f"\nFor any signature field, use exactly: {signature}"

    prompt = (
        "You are given a web form's accessibility tree and AWS cost estimation data.\n"
        "Map the estimation data to the appropriate form fields.\n\n"
        f"Form accessibility tree:\n{form_snapshot}\n\n"
        f"Cost estimation data:\n{estimation_text}\n"
        f"{extra_context}\n\n"
        "Return a JSON object with two keys:\n"
        '- "textboxes": object mapping the exact textbox accessible name to '
        "its value (keep each value under 50 characters)\n"
        '- "radios": object mapping the exact radio option accessible name '
        "to true for the one to select\n\n"
        "Use the EXACT accessible names from the tree above as keys.\n"
        "Only include fields that should be filled. For radios, pick the "
        "most relevant AWS service based on the estimation.\n"
        "Return ONLY valid JSON, no markdown fences or explanation."
    )

    messages = [{"role": "user", "content": [{"text": prompt}]}]
    response = bedrock_runtime.converse(
        modelId=model_id,
        messages=messages,
        inferenceConfig={"maxTokens": 2000, "temperature": 0.0},
    )
    generated = response["output"]["message"]["content"][0]["text"]
    logger.info("Bedrock form mapping response:\n%s", generated)

    cleaned = re.sub(r"^```(?:json)?\s*", "", generated.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)

    return json.loads(cleaned)


def clear_screenshots() -> None:
    """Remove old screenshots to keep the directory clean."""
    if os.path.isdir(SCREENSHOT_DIR):
        for f in os.listdir(SCREENSHOT_DIR):
            if f.endswith(".png"):
                os.remove(os.path.join(SCREENSHOT_DIR, f))


def save_screenshot(page: Page, name: str) -> str:
    """Save a screenshot and return the file path."""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    page.screenshot(path=path, full_page=False)
    logger.info("Screenshot saved: %s", path)
    return path


def type_into_field(page: Page, locator, value: str) -> None:
    """Type text into a field using real keyboard events in small chunks.

    Sends keystrokes in small chunks with pauses to ensure reliable
    delivery over the remote CDP WebSocket connection.
    """
    locator.scroll_into_view_if_needed()
    locator.click()
    page.keyboard.press("Control+a")
    for start in range(0, len(value), CHUNK_SIZE):
        chunk = value[start : start + CHUNK_SIZE]
        page.keyboard.type(chunk)
        time.sleep(0.3)
    time.sleep(0.3)


def fill_form(
    playwright: Playwright,
    form_url: str,
    region: str,
    estimation_text: str,
    signature: str = "",
) -> None:
    """Open AgentCore Browser, discover form fields, and fill them.

    Connects Playwright to a managed Chrome session via AgentCore Browser,
    navigates to the form URL, discovers fields from the accessibility tree,
    uses Bedrock to generate appropriate values, then fills and submits.
    """
    logger.info("Opening AgentCore Browser session in %s...", region)

    with browser_session(region) as client:
        ws_url, headers = client.generate_ws_headers()

        print("=" * 60)
        print("LIVE VIEW: Watch the browser session in the AWS Console:")
        print(f"  Region:     {region}")
        print(f"  Session ID: {client.session_id}")
        print(f"  Browser ID: {client.identifier}")
        try:
            live_url = client.generate_live_view_url()
            print(f"  Live URL:   {live_url[:120]}...")
        except Exception:
            pass
        print(
            f"  Console: https://{region}.console.aws.amazon.com"
            "/bedrock-agentcore/builtInTools"
        )
        print("=" * 60)
        print()

        chromium: BrowserType = playwright.chromium
        browser = chromium.connect_over_cdp(ws_url, headers=headers)
        context = browser.contexts[0]
        page = context.pages[0]

        try:
            logger.info("Navigating to %s ...", form_url)
            page.goto(form_url, wait_until="networkidle", timeout=30000)
            logger.info("Page loaded: %s", page.title())

            logger.info("Waiting for form to render...")
            page.wait_for_selector("textarea", timeout=15000)

            try:
                cookie_btn = page.locator("button:has-text('Accept')").first
                if cookie_btn.is_visible(timeout=3000):
                    cookie_btn.click()
                    logger.info("Dismissed cookie consent dialog")
                    time.sleep(0.5)
            except Exception:
                logger.info("No cookie consent dialog found")

            save_screenshot(page, "01_form_loaded")

            # Discover form fields from the accessibility tree
            logger.info("Discovering form fields from aria snapshot...")
            form_snapshot = discover_form_fields(page)
            logger.info("Aria snapshot:\n%s", form_snapshot)

            # Use Bedrock to generate values for each discovered field
            logger.info("Generating form values with Bedrock...")
            form_values = generate_form_values(
                estimation_text, form_snapshot, region, signature
            )
            print("\nBedrock-generated form values:")
            print(json.dumps(form_values, indent=2))
            print()

            # Fill text fields
            textbox_values = form_values.get("textboxes", {})
            for field_name, value in textbox_values.items():
                value = value[:MAX_FIELD_CHARS]
                textbox = page.get_by_role("textbox", name=field_name)
                if textbox.count() > 0:
                    type_into_field(page, textbox.first, value)
                    confirmed = textbox.first.input_value()
                    print(
                        f"  Filled '{field_name}': {len(value)} chars written,"
                        f" {len(confirmed)} confirmed"
                    )
                else:
                    logger.warning("Textbox '%s' not found on page", field_name)

            save_screenshot(page, "02_fields_filled")

            # Select radio buttons
            radio_values = form_values.get("radios", {})
            for option_label, should_select in radio_values.items():
                if not should_select:
                    continue
                radio = page.get_by_role("radio", name=option_label)
                if radio.count() > 0:
                    radio.first.scroll_into_view_if_needed()
                    radio.first.click()
                    print(f"  Selected radio: {option_label}")
                else:
                    logger.warning("Radio option '%s' not found on page", option_label)

            # Verify all text fields before submit
            save_screenshot(page, "03_before_submit")
            time.sleep(0.5)

            all_ok = True
            for field_name, value in textbox_values.items():
                value = value[:MAX_FIELD_CHARS]
                textbox = page.get_by_role("textbox", name=field_name)
                if textbox.count() > 0:
                    confirmed = textbox.first.input_value()
                    if confirmed != value:
                        logger.warning(
                            "'%s' lost value! Expected %d chars, got %d. Re-typing.",
                            field_name,
                            len(value),
                            len(confirmed),
                        )
                        type_into_field(page, textbox.first, value)
                        all_ok = False

            if not all_ok:
                save_screenshot(page, "03b_after_retype")

            # Submit the form
            submit_btn = page.get_by_role("button", name="Submit")
            submit_btn.scroll_into_view_if_needed()
            time.sleep(0.5)

            logger.info("Clicking Submit...")
            submit_btn.click()

            time.sleep(3)
            save_screenshot(page, "04_after_submit")

            body_text = page.locator("body").inner_text()
            if "thank" in body_text.lower():
                logger.info("Form submitted successfully!")
                print("\nForm submitted successfully!")
            else:
                logger.warning("Submit may have failed — check screenshots")
                print("\nSubmit may have failed. Page text:")
                print(body_text[:500])

            logger.info(
                "Keeping browser open %ds for live view...", POST_SUBMIT_WAIT
            )
            time.sleep(POST_SUBMIT_WAIT)

        finally:
            page.close()
            browser.close()
            logger.info("Browser session closed.")

    print(f"\nScreenshots saved to: {SCREENSHOT_DIR}/")


def main():
    """Parse CLI arguments and orchestrate cost estimation and form filling."""
    parser = argparse.ArgumentParser(
        description="AgentCore Browser — Fill web forms with cost estimation data",
    )
    parser.add_argument(
        "--architecture",
        type=str,
        default=(
            "A simple web application with an Application Load Balancer, "
            "2 EC2 t3.medium instances, and an RDS MySQL database in us-east-1."
        ),
        help="Architecture description for cost estimation",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=DEFAULT_FORM_URL,
        help="Form URL to fill (default: AWS Pulse survey)",
    )
    parser.add_argument(
        "--signature",
        type=str,
        default="",
        help="Your signature to identify the submission",
    )
    parser.add_argument(
        "--region",
        type=str,
        default="",
        help="AWS region (default: from boto3 session)",
    )

    args = parser.parse_args()
    region = args.region or boto3.Session().region_name
    if not region:
        logger.error("AWS region not configured. Set AWS_DEFAULT_REGION or use --region.")
        sys.exit(1)

    # Step 1: Run cost estimation
    estimation_text = run_cost_estimation(args.architecture, region)
    print("\n===== Cost Estimation Result =====")
    print(estimation_text)
    print("==================================\n")

    # Step 2: Open browser, discover fields, fill, and submit
    clear_screenshots()

    with sync_playwright() as pw:
        fill_form(
            pw,
            form_url=args.url,
            region=region,
            estimation_text=estimation_text,
            signature=args.signature,
        )


if __name__ == "__main__":
    main()
