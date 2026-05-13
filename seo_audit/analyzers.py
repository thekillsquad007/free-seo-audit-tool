import json
import re
import urllib.parse
from collections import Counter
from .models import Issue, Severity, AuditResult, Page


class BaseAnalyzer:
    name = ""
    label = ""

    def analyze(self, pages: list[Page], target_url: str) -> tuple[list[Issue], float]:
        raise NotImplementedError

    def _issue(self, severity, message, recommendation, page_url, element=None, current=None, suggested=None):
        return Issue(
            analyzer=self.name,
            severity=severity,
            message=message,
            recommendation=recommendation,
            page_url=page_url,
            element=element,
            current_value=current,
            suggested_value=suggested,
        )

    def _score(self, issues: list[Issue], total_pages: int) -> float:
        if total_pages == 0:
            return 100.0
        deductions = sum({"critical": 15, "warning": 5, "info": 1}[i.severity.value] for i in issues)
        max_deductions = total_pages * 15
        if max_deductions == 0:
            return 100.0
        return round(max(0, 100 - (deductions / max_deductions) * 100), 1)


class MetaAnalyzer(BaseAnalyzer):
    name = "meta"
    label = "Meta Tags"

    def analyze(self, pages, target_url):
        issues = []
        seen_titles = {}
        seen_descriptions = {}

        for page in pages:
            title_tag = page.soup.find("title")
            if title_tag is None or not title_tag.get_text(strip=True):
                issues.append(self._issue(
                    Severity.CRITICAL, "Your page is missing a title tag",
                    "The page title is what shows up as the clickable headline in Google search results and in your browser tab. Without one, your pages won't look good in search results and people won't know what your page is about. Add a descriptive title like 'About Us | Your Store Name'.",
                    page.url, element="<title>",
                    suggested=f"{urllib.parse.urlparse(page.url).path.strip('/').replace('/', ' | ').replace('-', ' ').title()} | {urllib.parse.urlparse(target_url).netloc}"
                ))
            else:
                title = title_tag.get_text(strip=True)
                seen_titles[page.url] = title
                if len(title) < 30:
                    issues.append(self._issue(
                        Severity.WARNING, f"Your page title is too short ({len(title)} characters, aim for 50-60)",
                        "Short titles don't tell Google or your visitors enough about the page. Try writing a title that clearly describes what the page is about, like 'Organic Groceries Delivered | Your Store'.",
                        page.url, current=title,
                        suggested=title + " | " + urllib.parse.urlparse(target_url).netloc
                    ))
                elif len(title) > 70:
                    issues.append(self._issue(
                        Severity.WARNING, f"Your page title is too long ({len(title)} characters, aim for 50-60)",
                        "Google will cut off (truncate) long titles in search results, so people may not see the full thing. Keep it under 60 characters so it displays properly.",
                        page.url, current=title,
                        suggested=title[:57] + "..."
                    ))

            desc_tag = page.soup.find("meta", attrs={"name": "description"})
            if desc_tag is None or not desc_tag.get("content", "").strip():
                issues.append(self._issue(
                    Severity.CRITICAL, "Your page is missing a meta description",
                    "The meta description is the short paragraph that appears under your title in Google search results. It's your chance to convince people to click on your link. Add a clear 150-160 character summary of what the page offers.",
                    page.url, element="<meta name='description'>"
                ))
            else:
                desc = desc_tag["content"].strip()
                seen_descriptions[page.url] = desc
                if len(desc) < 120:
                    issues.append(self._issue(
                        Severity.WARNING, f"Your meta description is too short ({len(desc)} characters, aim for 150-160)",
                        "Short descriptions don't give people enough reason to click your link in search results. Expand it to describe what makes this page valuable.",
                        page.url, current=desc
                    ))
                elif len(desc) > 165:
                    issues.append(self._issue(
                        Severity.WARNING, f"Your meta description is too long ({len(desc)} characters, aim for 150-160)",
                        "Google will cut off descriptions that are too long, so important details may get hidden. Shorten it so the full message shows in search results.",
                        page.url, current=desc,
                        suggested=desc[:157] + "..."
                    ))

            viewport = page.soup.find("meta", attrs={"name": "viewport"})
            if viewport is None:
                issues.append(self._issue(
                    Severity.WARNING, "Your page is missing mobile viewport settings",
                    "Without this tag, your website won't display properly on phones and tablets. Add it so your site automatically adjusts to fit any screen size. This is required for Google's mobile-friendly ranking.",
                    page.url, element="<meta name='viewport'>",
                    suggested="<meta name='viewport' content='width=device-width, initial-scale=1'>"
                ))

            charset = page.soup.find("meta", charset=True) or page.soup.find("meta", attrs={"http-equiv": "Content-Type"})
            if charset is None:
                issues.append(self._issue(
                    Severity.INFO, "Your page is missing character encoding settings",
                    "This tells the browser how to display text correctly so special characters (like é, ü, or em dashes) don't show up as garbled nonsense. Add <meta charset='UTF-8'> to your <head> section.",
                    page.url, element="<meta charset='utf-8'>",
                    suggested="<meta charset='UTF-8'>"
                ))

        title_texts = list(seen_titles.values())
        dup_titles = [t for t, c in Counter(title_texts).items() if c > 1]
        for dup in dup_titles:
            dup_urls = [url for url, t in seen_titles.items() if t == dup]
            issues.append(self._issue(
                Severity.WARNING, f"Multiple pages share the same title: \"{dup}\"",
                "Every page on your site should have its own unique title. When pages share titles, Google gets confused about which page is which. Give each page a title that matches its specific content.",
                dup_urls[0], current=dup
            ))

        desc_texts = list(seen_descriptions.values())
        dup_descs = [d for d, c in Counter(desc_texts).items() if c > 1]
        for dup in dup_descs:
            dup_urls = [url for url, d in seen_descriptions.items() if d == dup]
            issues.append(self._issue(
                Severity.INFO, f"Multiple pages share the same meta description",
                "Each page should have its own description that matches what's on that page. Unique descriptions help Google show the right snippet for each page in search results.",
                dup_urls[0], current=dup
            ))

        return issues, self._score(issues, len(pages))


class HeadingsAnalyzer(BaseAnalyzer):
    name = "headings"
    label = "Heading Structure"

    def analyze(self, pages, target_url):
        issues = []
        for page in pages:
            h1_tags = page.soup.find_all("h1")
            if len(h1_tags) == 0:
                issues.append(self._issue(
                    Severity.CRITICAL, "Your page doesn't have a main heading (H1)",
                    "The main heading (H1) is like the title of a newspaper article — it tells readers and Google what this page is about at a glance. Every page needs exactly one clear H1. For example: <h1>Organic Spices for Healthy Cooking</h1>.",
                    page.url, element="<h1>",
                    suggested=f"<h1>{urllib.parse.urlparse(page.url).path.strip('/').replace('/', ' > ').replace('-', ' ').title()}</h1>"
                ))
            elif len(h1_tags) > 1:
                issues.append(self._issue(
                    Severity.WARNING, f"Your page has multiple main headings ({len(h1_tags)} H1 tags)",
                    "Think of H1 like a page title — you wouldn't give one article two different titles. Having more than one H1 confuses search engines about what your page is really about. Keep just one.",
                    page.url, element="<h1>"
                ))

            headings = page.soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
            prev_level = 0
            for h in headings:
                level = int(h.name[1])
                if prev_level and level > prev_level + 1:
                    issues.append(self._issue(
                        Severity.WARNING, f"Your headings skip a level (went from H{prev_level} to H{level})",
                        "Headings should go in order like an outline: H1 → H2 → H3, never H1 → H3. Skipping levels confuses screen readers used by visually impaired visitors and creates a messy structure for Google.",
                        page.url, element=str(h)[:100]
                    ))
                prev_level = level

            for h in headings:
                if not h.get_text(strip=True):
                    issues.append(self._issue(
                        Severity.INFO, f"You have an empty heading (H{h.name[1]}) on this page",
                        "Empty headings are like blank signposts — they help nobody. Either add text to describe that section, or remove the heading tag entirely.",
                        page.url, element=str(h)[:100]
                    ))

        return issues, self._score(issues, len(pages))


class ImagesAnalyzer(BaseAnalyzer):
    name = "images"
    label = "Image Optimization"

    def analyze(self, pages, target_url):
        issues = []
        for page in pages:
            images = page.soup.find_all("img")
            for img in images:
                src = img.get("src", "")
                alt = img.get("alt")
                if alt is None:
                    issues.append(self._issue(
                        Severity.WARNING, "An image is missing descriptive alt text",
                        "Alt text is the description that shows when an image can't load, and it's what screen readers tell visually impaired visitors. It also helps Google understand what the image shows. Add a brief description like 'Organic almonds in a wooden bowl'.",
                        page.url, element=f"<img src='{src[:80]}'>",
                        suggested=f"<img src='{src}' alt='Description of this image'>"
                    ))
                elif not alt.strip():
                    pass
                elif len(alt) > 125:
                    issues.append(self._issue(
                        Severity.INFO, f"An image has overly long alt text ({len(alt)} characters, aim for under 125)",
                        "Screen readers will cut off alt text that's too long. Keep descriptions short and to the point — imagine describing the image to someone in 10 words or fewer.",
                        page.url, element=f"<img src='{src[:80]}'>", current=alt
                    ))

            if not images:
                issues.append(self._issue(
                    Severity.INFO, "No images found on this page",
                    "Adding relevant images makes your page more engaging and visually appealing. People are more likely to stay on a page that has pictures breaking up the text.",
                    page.url
                ))

        return issues, self._score(issues, len(pages))


class LinksAnalyzer(BaseAnalyzer):
    name = "links"
    label = "Links & Navigation"

    def analyze(self, pages, target_url):
        issues = []
        crawled_urls = {p.url for p in pages}

        for page in pages:
            links = page.soup.find_all("a", href=True)
            if len(links) > 100:
                issues.append(self._issue(
                    Severity.WARNING, f"This page has a lot of links ({len(links)})",
                    "Too many links on one page can overwhelm visitors and make it harder for Google to decide which pages are important. Try to keep the main navigation focused — under 100 links is a good rule of thumb.",
                    page.url
                ))

            for a in links:
                href = a["href"].strip()
                text = a.get_text(strip=True)

                if href.startswith("javascript:"):
                    issues.append(self._issue(
                        Severity.WARNING, "A link uses JavaScript instead of a normal web address",
                        "Links that use 'javascript:' can't be followed by search engines, so linked pages won't get indexed. Use a regular URL instead, or use a <button> for actions that don't navigate anywhere.",
                        page.url, element=f"<a href='{href[:60]}'>", current=href,
                        suggested="Replace with a normal URL, or use <button> for JavaScript actions"
                    ))
                elif href in ("#", ""):
                    issues.append(self._issue(
                        Severity.INFO, "A link goes nowhere (empty href)",
                        "Links that point to '#' or empty URLs don't lead anywhere useful. They can confuse both visitors and search engines. Either add the correct URL or remove the link.",
                        page.url, element=f"<a href='{href}'>{text[:40]}</a>"
                    ))

                if text and text.lower() in ("click here", "read more", "more", "link", "this", "here"):
                    issues.append(self._issue(
                        Severity.INFO, f"A link uses vague text like \"{text}\"",
                        "Link text like 'click here' tells visitors and Google nothing about where the link goes. Instead, use descriptive text like 'View our organic tea collection' so people know what to expect.",
                        page.url, element=f"<a href='{href[:60]}'>", current=text
                    ))

                parsed = urllib.parse.urlparse(href)
                if not parsed.netloc:
                    full = urllib.parse.urljoin(page.url, href)
                    clean = urllib.parse.urldefrag(full).url.rstrip("/")
                    if clean not in crawled_urls and clean.startswith(target_url.rstrip("/")):
                        pass

        return issues, self._score(issues, len(pages))


class OpenGraphAnalyzer(BaseAnalyzer):
    name = "opengraph"
    label = "Open Graph / Social"

    def analyze(self, pages, target_url):
        issues = []
        og_properties = ["og:title", "og:description", "og:image", "og:url"]
        twitter_properties = ["twitter:card"]

        for page in pages:
            for prop in og_properties:
                tag = page.soup.find("meta", attrs={"property": prop}) or page.soup.find("meta", attrs={"name": prop})
                if tag is None or not tag.get("content", "").strip():
                    labels = {
                        "og:title": "a social sharing title",
                        "og:description": "a social sharing description",
                        "og:image": "a social sharing image",
                        "og:url": "a social sharing URL",
                    }
                    why_matters = {
                        "og:title": "Without it, Facebook, Twitter, and WhatsApp will guess (often badly) what to show when someone shares your page.",
                        "og:description": "This is the preview text people see when you share a link on social media. Without it, platforms will grab random text from your page.",
                        "og:image": "This is the picture that appears when your page is shared on social media. Without it, your links will look plain and get fewer clicks.",
                        "og:url": "This tells social platforms which URL to link to when someone shares your page, preventing broken or duplicate links.",
                    }
                    issues.append(self._issue(
                        Severity.WARNING, f"Your page is missing {labels.get(prop, prop)}",
                        why_matters.get(prop, f"Adding {prop} helps control how your page appears when shared on social media."),
                        page.url, element=f"<meta {prop}>"
                    ))

            for prop in twitter_properties:
                tag = page.soup.find("meta", attrs={"name": prop})
                if tag is None or not tag.get("content", "").strip():
                    issues.append(self._issue(
                        Severity.INFO, "Your page is missing Twitter card settings",
                        "Twitter cards make your links look nicer when shared on Twitter (X) — showing a preview image, title, and description. Add them so your tweets stand out.",
                        page.url, element=f"<meta name='{prop}'>"
                    ))

            og_img = page.soup.find("meta", attrs={"property": "og:image"}) or page.soup.find("meta", attrs={"name": "og:image"})
            if og_img and og_img.get("content"):
                img_url = og_img["content"]
                if not img_url.startswith(("http://", "https://")):
                    issues.append(self._issue(
                        Severity.INFO, "Your social sharing image uses a relative path instead of a full URL",
                        "Social media sites need the full web address (starting with https://) for your image to display correctly when shared. Using just '/images/pic.jpg' won't work on Facebook or Twitter.",
                        page.url, element=f"<meta property='og:image' content='{img_url[:80]}'>",
                        current=img_url,
                        suggested=urllib.parse.urljoin(page.url, img_url)
                    ))

        return issues, self._score(issues, len(pages))


class SchemaAnalyzer(BaseAnalyzer):
    name = "schema"
    label = "Schema Markup"

    def analyze(self, pages, target_url):
        issues = []
        for page in pages:
            scripts = page.soup.find_all("script", attrs={"type": "application/ld+json"})
            if not scripts:
                issues.append(self._issue(
                    Severity.INFO, "Your page doesn't have structured data (Schema markup)",
                    "Structured data is code that helps Google understand your content better and can make your search results stand out with special features like star ratings, prices, or FAQs. It's like giving Google a cheat sheet about your page. Tools like Google's Structured Data Markup Helper can help you add it.",
                    page.url
                ))
                continue

            for script in scripts:
                try:
                    data = json.loads(script.string) if script.string else {}
                    if isinstance(data, dict):
                        schema_type = data.get("@type", "Unknown")
                        if "@context" not in data:
                            issues.append(self._issue(
                                Severity.WARNING, "Your structured data is missing a required field (@context)",
                                "The @context field tells Google what format your structured data uses. Without it, Google may not understand your Schema markup at all. Add '@context': 'https://schema.org' to your JSON-LD.",
                                page.url, current=str(data)[:100]
                            ))
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and "@context" not in item:
                                issues.append(self._issue(
                                    Severity.WARNING, "An item in your structured data is missing the @context field",
                                    "Every item in your structured data list needs '@context': 'https://schema.org' so Google can understand it properly.",
                                    page.url, current=str(item)[:100]
                                ))
                except (json.JSONDecodeError, TypeError):
                    issues.append(self._issue(
                        Severity.WARNING, "Your structured data contains invalid JSON",
                        "If the JSON is broken, Google won't be able to read any of your structured data. Use a JSON validator (like jsonlint.com) to find and fix the error.",
                        page.url, element="<script type='application/ld+json'>"
                    ))

        return issues, self._score(issues, len(pages))


class PerformanceAnalyzer(BaseAnalyzer):
    name = "performance"
    label = "Performance"

    def analyze(self, pages, target_url):
        issues = []
        for page in pages:
            content_size = len(page.content)
            if content_size > 2 * 1024 * 1024:
                issues.append(self._issue(
                    Severity.WARNING, f"Your page is quite large ({content_size / 1024:.0f} KB)",
                    "Big pages load slowly, especially on mobile data. Visitors will leave if your site takes too long. Aim for under 500 KB. Compress images, remove unused code, and enable compression to speed things up.",
                    page.url
                ))
            elif content_size > 500 * 1024:
                issues.append(self._issue(
                    Severity.INFO, f"Your page size is {content_size / 1024:.0f} KB (tip: try to stay under 500 KB)",
                    "Large pages take longer to load, which hurts your Google ranking and drives away impatient visitors. Compressing images and cleaning up unnecessary code can make a big difference.",
                    page.url
                ))

            css_count = len(page.soup.find_all("link", rel="stylesheet"))
            if css_count > 5:
                issues.append(self._issue(
                    Severity.INFO, f"Your page loads {css_count} separate stylesheet files",
                    "Each CSS file requires a separate network request, slowing down your page. Combine multiple CSS files into one (your web developer can do this) to speed things up.",
                    page.url
                ))

            js_scripts = page.soup.find_all("script", src=True)
            js_count = len(js_scripts)
            if js_count > 10:
                issues.append(self._issue(
                    Severity.INFO, f"Your page loads {js_count} separate JavaScript files",
                    "Each JavaScript file adds loading time. Combine files where possible, remove unused scripts, and consider deferring non-essential scripts so they don't block your page from displaying.",
                    page.url
                ))

            img_count = len(page.soup.find_all("img"))
            if img_count > 20:
                issues.append(self._issue(
                    Severity.INFO, f"Your page has {img_count} images",
                    "Many images slow down page loading. Consider lazy loading (images load only when they scroll into view) and make sure images are compressed and sized appropriately.",
                    page.url
                ))

            encoding = page.headers.get("Content-Encoding", "")
            if "gzip" not in encoding and "br" not in encoding:
                if content_size > 100 * 1024:
                    issues.append(self._issue(
                        Severity.INFO, "Your server isn't compressing files before sending them",
                        "Compression (gzip or brotli) shrinks your files by 60-80% during transfer — like zipping a folder before emailing it. Ask your hosting provider or developer to enable it. Most servers can do this with a simple setting.",
                        page.url
                    ))

        return issues, self._score(issues, len(pages))


class RobotsAnalyzer(BaseAnalyzer):
    name = "robots"
    label = "Robots.txt & Sitemap"

    def analyze(self, pages, target_url):
        issues = []
        import requests
        parsed = urllib.parse.urlparse(target_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"

        try:
            resp = requests.get(robots_url, timeout=15, headers={"User-Agent": "SEOAuditBot/1.0"})
            if resp.status_code == 404:
                issues.append(self._issue(
                    Severity.WARNING, "Your robots.txt file is missing (404 error)",
                    "Robots.txt tells Google which parts of your site to crawl and which to ignore. Without it, Google might waste time crawling unimportant pages or miss important ones. Create a simple one at yourdomain.com/robots.txt.",
                    robots_url, element="robots.txt"
                ))
            elif resp.status_code != 200:
                issues.append(self._issue(
                    Severity.INFO, f"Your robots.txt returned an unusual status code ({resp.status_code})",
                    "Search engines expect robots.txt to load normally. If it's returning an error, Google may not be able to read your crawling instructions.",
                    robots_url, element="robots.txt"
                ))
            else:
                if "sitemap" not in resp.text.lower():
                    issues.append(self._issue(
                        Severity.INFO, "Your sitemap isn't mentioned in your robots.txt file",
                        "Adding your sitemap location to robots.txt helps Google find it immediately. Just add a line like 'Sitemap: https://yourdomain.com/sitemap.xml' to your robots.txt file.",
                        robots_url, element="robots.txt",
                        suggested=f"Sitemap: {sitemap_url}"
                    ))
        except requests.exceptions.RequestException as e:
            issues.append(self._issue(
                Severity.WARNING, f"Couldn't access your robots.txt file",
                "Search engines need to be able to read your robots.txt to know how to crawl your site. Check that the file exists and is publicly accessible.",
                robots_url
            ))

        try:
            resp = requests.get(sitemap_url, timeout=15, headers={"User-Agent": "SEOAuditBot/1.0"})
            if resp.status_code == 404:
                issues.append(self._issue(
                    Severity.WARNING, "Your sitemap file is missing (404 at /sitemap.xml)",
                    "A sitemap is like a roadmap that tells Google about all the pages on your site. Without one, Google has to discover your pages on its own, which can be slow. Create an XML sitemap using a tool like XML-Sitemaps.com.",
                    sitemap_url, element="sitemap.xml"
                ))
            elif resp.status_code == 200:
                content_type = resp.headers.get("Content-Type", "")
                if "xml" not in content_type and "text" not in content_type:
                    issues.append(self._issue(
                        Severity.WARNING, "Your sitemap might not be proper XML format",
                        "Search engines expect sitemaps to be valid XML. If it's in the wrong format, Google won't be able to read it. Use a sitemap validator tool to check yours.",
                        sitemap_url
                    ))
        except requests.exceptions.RequestException as e:
            issues.append(self._issue(
                Severity.INFO, f"Couldn't access your sitemap file",
                "Sitemaps help search engines discover all your pages. If yours isn't accessible, Google may miss some of your content.",
                sitemap_url
            ))

        return issues, self._score(issues, 1)


class ContentAnalyzer(BaseAnalyzer):
    name = "content"
    label = "Content Quality"

    def analyze(self, pages, target_url):
        issues = []
        for page in pages:
            body = page.soup.find("body")
            if body is None:
                continue
            text = body.get_text(separator=" ", strip=True)
            words = text.split()
            word_count = len(words)

            if word_count == 0:
                issues.append(self._issue(
                    Severity.CRITICAL, "This page has no readable content",
                    "A page with no content doesn't provide any value to visitors and will be ignored by Google. Add meaningful text, product descriptions, or articles so people have a reason to visit.",
                    page.url
                ))
            elif word_count < 300:
                issues.append(self._issue(
                    Severity.WARNING, f"This page has very little content ({word_count} words, aim for 300+)",
                    "Pages with only a few words don't rank well in Google and don't give visitors enough information. Add more detailed content — describe your products, share your story, or explain your services.",
                    page.url, current=f"{word_count} words"
                ))

            paragraphs = page.soup.find_all("p")
            for p in paragraphs:
                p_words = len(p.get_text(strip=True).split())
                if p_words > 150:
                    issues.append(self._issue(
                        Severity.INFO, f"A paragraph on this page is very long ({p_words} words)",
                        "Huge blocks of text are hard to read, especially on phones. Break them into shorter paragraphs of 2-4 sentences each. Your visitors will thank you!",
                        page.url, element=f"<p>{p.get_text(strip=True)[:80]}..."
                    ))
                    break

            if len(page.content) > 0:
                text_ratio = len(text) / len(page.content) * 100
                if text_ratio < 10 and word_count > 0:
                    issues.append(self._issue(
                        Severity.INFO, f"Your page has more code than actual content ({text_ratio:.0f}% text)",
                        "If most of your page is HTML/CSS code with very little readable text, it will load slower and may not rank well. Try to reduce unnecessary code and focus on adding quality content.",
                        page.url
                    ))

        return issues, self._score(issues, len(pages))


class URLAnalyzer(BaseAnalyzer):
    name = "urls"
    label = "URL Structure"

    def analyze(self, pages, target_url):
        issues = []
        for page in pages:
            parsed = urllib.parse.urlparse(page.url)
            path = parsed.path
            if not path or path == "/":
                continue

            segments = [s for s in path.split("/") if s]
            depth = len(segments)

            if depth > 4:
                issues.append(self._issue(
                    Severity.INFO, f"This URL is quite deep ({depth} levels of folders)",
                    "Short, simple URLs (like yoursite.com/products) are easier for people to remember and for Google to understand. Very deep URLs (like yoursite.com/cat/subcat/item/details) can be confusing. Try to keep URLs to 2-3 levels.",
                    page.url, current=page.url
                ))

            for seg in segments:
                if re.search(r"[A-Z]", seg):
                    issues.append(self._issue(
                        Severity.WARNING, f"URL contains capital letters (\"{seg}\")",
                        "Some web servers treat 'About-Us' and 'about-us' as different pages, causing confusion. Always use lowercase letters in URLs to keep things consistent. Tip: use hyphens between words instead of capitals.",
                        page.url, current=page.url,
                        suggested=page.url.lower()
                    ))
                    break

            for seg in segments:
                if "_" in seg:
                    issues.append(self._issue(
                        Severity.WARNING, f"URL uses underscores instead of hyphens (\"{seg}\")",
                        "Google treats hyphens (-) as word separators but underscores (_) as part of the word. So 'organic-food' reads as 'organic' and 'food', but 'organic_food' reads as 'organicfood'. Use hyphens to make your URLs readable.",
                        page.url, current=page.url,
                        suggested=page.url.replace("_", "-")
                    ))
                    break

            if len(page.url) > 100:
                issues.append(self._issue(
                    Severity.INFO, f"This URL is quite long ({len(page.url)} characters)",
                    "Short URLs are easier to share, copy, and remember. Long URLs also get cut off in search results. Keep them concise and descriptive.",
                    page.url, current=page.url
                ))

            if parsed.query:
                issues.append(self._issue(
                    Severity.INFO, f"URL includes tracking/query parameters (\"{parsed.query[:60]}\")",
                    "URLs with ? and parameters can cause duplicate content issues (the same page accessible at multiple URLs). Use canonical tags to tell Google which version is the main one, or clean up the URLs if possible.",
                    page.url, current=page.url
                ))

            canonical = page.soup.find("link", rel="canonical")
            if canonical is None:
                issues.append(self._issue(
                    Severity.INFO, "Your page is missing a canonical URL tag",
                    "A canonical tag tells Google 'this is the main version of this page.' It prevents problems when the same content appears at multiple URLs. Add one even if you don't think you have duplicate pages — it's good practice.",
                    page.url, element="<link rel='canonical'>",
                    suggested=f"<link rel='canonical' href='{page.url}'>"
                ))

        return issues, self._score(issues, len(pages))


def run_all_analyzers(pages: list[Page], target_url: str) -> AuditResult:
    analyzers = [
        MetaAnalyzer(),
        HeadingsAnalyzer(),
        ImagesAnalyzer(),
        LinksAnalyzer(),
        OpenGraphAnalyzer(),
        SchemaAnalyzer(),
        PerformanceAnalyzer(),
        RobotsAnalyzer(),
        ContentAnalyzer(),
        URLAnalyzer(),
    ]

    all_issues = []
    scores = {}

    for analyzer in analyzers:
        try:
            issues, score = analyzer.analyze(pages, target_url)
            all_issues.extend(issues)
            scores[analyzer.label] = score
        except Exception as e:
            scores[analyzer.label] = 0.0

    all_issues.sort(key=lambda x: (
        x.analyzer,
        {"critical": 0, "warning": 1, "info": 2}[x.severity.value],
    ))

    severity_counts = Counter(i.severity.value for i in all_issues)
    summary_parts = []
    if severity_counts.get("critical", 0):
        c = severity_counts["critical"]
        summary_parts.append(f"{c} critical {'issue' if c == 1 else 'issues'} to fix")
    if severity_counts.get("warning", 0):
        w = severity_counts["warning"]
        summary_parts.append(f"{w} {'warning' if w == 1 else 'warnings'} to address")
    if severity_counts.get("info", 0):
        i = severity_counts["info"]
        summary_parts.append(f"{i} {'suggestion' if i == 1 else 'suggestions'} to improve")
    summary = ", ".join(summary_parts) if summary_parts else "Great job — no issues found!"

    return AuditResult(
        target_url=target_url,
        total_pages_crawled=len(pages),
        issues=all_issues,
        scores=scores,
        summary=summary,
    )



