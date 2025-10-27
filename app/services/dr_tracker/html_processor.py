"""
HTML Processing Module for DR-Tracker.

Handles sanitization and preprocessing of uploaded Daily Report HTML files.
Ported from legacy code: legacy_code/ops_toolkit/src/daily_report/daily_report.py
"""

import re
import urllib.parse
import chardet
from bs4 import BeautifulSoup
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


def detect_file_encoding(file_bytes: bytes) -> Tuple[str, float]:
    """
    Detect the encoding of uploaded file using chardet.

    Args:
        file_bytes: Raw bytes from uploaded file

    Returns:
        Tuple of (encoding, confidence)
    """
    result = chardet.detect(file_bytes)
    encoding = result['encoding']
    confidence = result['confidence']

    logger.debug(f"Detected encoding: {encoding} (confidence: {confidence:.2%})")
    return encoding, confidence


def parse_html(file_bytes: bytes, encoding: str) -> BeautifulSoup:
    """
    Parse HTML content using BeautifulSoup with the specified encoding and lxml parser.

    Args:
        file_bytes: Raw bytes from uploaded file
        encoding: Character encoding to use

    Returns:
        BeautifulSoup object
    """
    try:
        html_content = file_bytes.decode(encoding, errors="replace")
    except (UnicodeDecodeError, LookupError, TypeError):
        logger.warning(f"Failed to decode with {encoding}, falling back to utf-8")
        html_content = file_bytes.decode("utf-8", errors="replace")

    return BeautifulSoup(html_content, "lxml")


def remove_unnecessary_html_attributes(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Remove unnecessary attributes from all tags except <a>, preserving href.

    Args:
        soup: BeautifulSoup object

    Returns:
        Modified BeautifulSoup object
    """
    for tag in soup.find_all(True):
        if tag.name.lower() != "a":
            tag.attrs = {}
        else:
            # Preserve only href attribute in <a> tags
            href = tag.get("href")
            tag.attrs = {}
            if href:
                tag.attrs["href"] = href

    return soup


def decode_safelinks(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Replace Microsoft Safe Links with the actual URLs in <a> tags.

    Args:
        soup: BeautifulSoup object

    Returns:
        Modified BeautifulSoup object
    """
    from urllib.parse import urlparse, parse_qs, unquote

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        parsed_url = urlparse(href)

        if "safelinks.protection.outlook.com" in parsed_url.netloc:
            query_params = parse_qs(parsed_url.query)
            url_param = query_params.get("url")
            if url_param:
                actual_url = unquote(url_param[0])
                a_tag["href"] = actual_url
                logger.debug(f"Decoded Safe Link: {actual_url}")

    return soup


def replace_safe_links(html_content: str) -> str:
    """
    Replace Microsoft Safe Links with actual URLs and remove text fragments.

    This function also removes text fragments from URLs, which can cause
    problems when creating hyperlinks for Excel.

    Args:
        html_content: HTML content as string

    Returns:
        Modified HTML content
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Find all anchor tags
    for a_tag in soup.find_all("a", href=True):
        safe_url = a_tag["href"]

        # Decode URL to handle any URL-encoded characters
        decoded_url = urllib.parse.unquote(safe_url)

        # Match and replace Safe Links with the actual URL
        match = re.search(r"[?&]url=([^&]+)", decoded_url)
        if match:
            # Decode the actual URL from Safe Link
            real_url = urllib.parse.unquote(match.group(1))
        else:
            real_url = decoded_url

        # Remove Text Fragments if present
        if "#:~:text=" in real_url:
            real_url = re.sub(r"(#:~:text=.*)$", "", real_url)

        # Assign the cleaned URL back to the anchor tag
        a_tag["href"] = real_url

    return str(soup)


def sanitize_html_text(html_text: str) -> str:
    """
    Sanitize HTML content by replacing typographic punctuation and other
    problematic Unicode characters with ASCII-safe equivalents.

    Args:
        html_text: HTML content as string

    Returns:
        Sanitized HTML content
    """
    replacements = {
        ''': "'",  # left single quote
        ''': "'",  # right single quote / apostrophe
        '–': '-',  # en dash
        '—': '-',  # em dash
    }

    # Replace all defined characters
    for orig, repl in replacements.items():
        html_text = html_text.replace(orig, repl)

    return html_text


def extract_html_body(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Extract the <body> part of the HTML.

    Args:
        soup: BeautifulSoup object

    Returns:
        Body element or original soup if no body found
    """
    body = soup.body
    return body if body else soup


def remove_non_content_tags(html_text: str) -> str:
    """
    Discard tags that do not carry content.

    Args:
        html_text: HTML content as string

    Returns:
        HTML with empty tags removed
    """
    soup = BeautifulSoup(html_text, "lxml")
    for tag in soup.find_all():
        if (
            not tag.get_text(strip=True) and
            not tag.find_all(string=True, recursive=True)
        ):
            tag.decompose()
    return str(soup)


def remove_empty_lines(html_text: str) -> str:
    """
    Remove empty lines from the HTML text.

    Args:
        html_text: HTML content as string

    Returns:
        HTML with empty lines removed
    """
    lines = html_text.splitlines()
    non_empty_lines = [line for line in lines if line.strip()]
    return "\n".join(non_empty_lines)


def discard_disclaimer(html_text: str) -> str:
    """
    Discard the 'disclaimer' section and everything after it.

    Args:
        html_text: HTML content as string

    Returns:
        HTML with disclaimer removed
    """
    disclaimer_pattern = re.compile(r"(?i)disclaimer")
    match = disclaimer_pattern.search(html_text)
    if match:
        return html_text[: match.start()]
    return html_text


def discard_content_before_DR(html_text: str) -> str:
    """
    Discard everything before the first occurrence of a line that contains
    "review and risk assessment.", including this line.

    Args:
        html_text: HTML content as string

    Returns:
        HTML with header content removed
    """
    pattern = re.compile(r"(?i)review and risk assessment\.", re.IGNORECASE)
    match = pattern.search(html_text)
    if match:
        return html_text[match.end():]
    return html_text


def remove_gphin(text: str) -> str:
    """
    Remove the word 'GPHIN' wherever it appears, case-insensitive.

    Args:
        text: Text content

    Returns:
        Text with GPHIN removed
    """
    return re.sub(r"GPHIN", "", text, flags=re.IGNORECASE)


def process_html_file(file_bytes: bytes) -> str:
    """
    Main pipeline: Run all HTML processing steps in sequence.

    This is the primary function for sanitizing Daily Report HTML files
    before sending to OpenAI for extraction.

    Steps:
    1. Detect encoding
    2. Parse HTML
    3. Remove unnecessary attributes
    4. Decode Safe Links
    5. Extract body
    6. Replace Safe Links (alternative method with text fragment removal)
    7. Sanitize text (replace typographic characters)
    8. Remove non-content tags
    9. Remove empty lines
    10. Discard disclaimer
    11. Discard content before DR section
    12. Remove GPHIN text

    Args:
        file_bytes: Raw bytes from uploaded HTML file

    Returns:
        Cleaned HTML content ready for OpenAI processing

    Raises:
        ValueError: If file processing fails
    """
    try:
        logger.info("Starting HTML processing pipeline")

        # Step 1: Detect encoding
        encoding, confidence = detect_file_encoding(file_bytes)
        logger.info(f"Detected encoding: {encoding} ({confidence:.1%} confidence)")

        # Step 2: Parse HTML
        soup = parse_html(file_bytes, encoding)

        # Step 3: Remove unnecessary attributes
        soup = remove_unnecessary_html_attributes(soup)

        # Step 4: Decode Safe Links (first pass)
        soup = decode_safelinks(soup)

        # Step 5: Extract body
        body = extract_html_body(soup)
        body_html = str(body)

        # Step 6: Replace Safe Links (second pass with text fragment removal)
        body_html = replace_safe_links(body_html)

        # Step 7: Sanitize text
        body_html = sanitize_html_text(body_html)

        # Step 8: Remove non-content tags
        body_html = remove_non_content_tags(body_html)

        # Step 9: Remove empty lines
        body_html = remove_empty_lines(body_html)

        # Step 10: Discard disclaimer
        body_html = discard_disclaimer(body_html)

        # Step 11: Discard content before DR
        body_html = discard_content_before_DR(body_html)

        # Step 12: Remove GPHIN
        body_html = remove_gphin(body_html)

        logger.info(f"HTML processing complete. Output length: {len(body_html)} chars")
        return body_html

    except Exception as e:
        logger.error(f"Error processing HTML file: {e}", exc_info=True)
        raise ValueError(f"Failed to process HTML file: {str(e)}")
