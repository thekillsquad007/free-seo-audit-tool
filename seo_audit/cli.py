import argparse
import os
import sys
from .crawler import Crawler
from .analyzers import run_all_analyzers
from .reporters import JsonReporter, HtmlReporter


def main():
    parser = argparse.ArgumentParser(
        description="SEO Audit Tool - Crawl and analyze any website for SEO issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  seo-audit https://example.com
  seo-audit https://example.com --max-pages 100 --max-depth 5
  seo-audit https://example.com --output-dir ./my-reports --name my-report
  seo-audit https://example.com --no-html
        """,
    )
    parser.add_argument("url", help="The website URL to audit (e.g., https://example.com)")
    parser.add_argument("--max-pages", type=int, default=50, help="Maximum pages to crawl (default: 50)")
    parser.add_argument("--max-depth", type=int, default=3, help="Maximum crawl depth (default: 3)")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds (default: 30)")
    parser.add_argument("--delay", type=float, default=0.3, help="Delay between requests in seconds (default: 0.3)")
    parser.add_argument("--output-dir", default="reports", help="Output directory for reports (default: reports)")
    parser.add_argument("--name", default=None, help="Custom report name (default: domain-based)")
    parser.add_argument("--no-html", action="store_true", help="Skip HTML report generation")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON report generation")

    args = parser.parse_args()

    if not args.url.startswith(("http://", "https://")):
        print("Error: URL must start with http:// or https://")
        sys.exit(1)

    print(f"SEO Audit starting for: {args.url}")
    print(f"Crawling up to {args.max_pages} pages (max depth: {args.max_depth})...")
    print()

    crawler = Crawler(
        base_url=args.url,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        timeout=args.timeout,
        delay=args.delay,
    )
    pages = crawler.crawl()

    if not pages:
        print("Error: No pages were crawled successfully.")
        print(f"Crawl errors: {crawler.errors[:5]}")
        sys.exit(1)

    print(f"Crawled {len(pages)} page(s)")
    if crawler.errors:
        print(f"Encountered {len(crawler.errors)} error(s) during crawl")

    print("Running SEO analysis...")
    result = run_all_analyzers(pages, args.url)

    if crawler.errors:
        result.crawl_errors = crawler.errors[:20]
    result.total_pages_crawled = len(pages)

    print(f"\nResults: {result.issue_count} issue(s) found")
    print(f"Overall score: {result.overall_score}/100")
    print()

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    report_name = args.name or url_to_name(args.url)

    if not args.no_json:
        json_path = os.path.join(args.output_dir, f"{report_name}.json")
        JsonReporter().save(result, json_path)
        print(f"JSON report: {json_path}")

    if not args.no_html:
        html_path = os.path.join(args.output_dir, f"{report_name}.html")
        HtmlReporter().save(result, html_path)
        print(f"HTML report: {html_path}")


def url_to_name(url: str) -> str:
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    return domain.replace(".", "_")
