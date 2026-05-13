import json
import os

from .models import AuditResult


class BaseReporter:
    def generate(self, result: AuditResult) -> str:
        raise NotImplementedError

    def save(self, result: AuditResult, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        content = self.generate(result)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


class JsonReporter(BaseReporter):
    def generate(self, result: AuditResult) -> str:
        return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)


class HtmlReporter(BaseReporter):
    def generate(self, result: AuditResult) -> str:
        score = result.overall_score
        score_color = "#22c55e" if score >= 80 else "#eab308" if score >= 50 else "#ef4444"
        score_label = "Looking good!" if score >= 80 else "Needs work" if score >= 50 else "Urgent attention needed"

        sections_html = ""
        prev_analyzer = None
        for issue in result.issues:
            analyzer = issue.analyzer
            if analyzer != prev_analyzer:
                if prev_analyzer is not None:
                    sections_html += "</div></details>"
                sections_html += f"""
                <details class="category-group" {"open" if prev_analyzer is None else ""}>
                    <summary class="category-summary">{issue.analyzer}</summary>
                    <div class="category-issues">
                """
                prev_analyzer = analyzer
            sections_html += self._issue_card(issue)
        if prev_analyzer is not None:
            sections_html += "</div></details>"

        scores_rows = ""
        for cat, s in sorted(result.scores.items(), key=lambda x: x[1]):
            color = "#22c55e" if s >= 80 else "#eab308" if s >= 50 else "#ef4444"
            label = "Great" if s >= 80 else "Needs work" if s >= 50 else "Poor"
            scores_rows += f"""
            <div class="score-item">
                <div class="score-label">
                    <span>{cat}</span>
                    <span><span class="score-status">{label}</span> <span class="score-value">{s}</span></span>
                </div>
                <div class="score-bar-bg">
                    <div class="score-bar" style="width:{s}%;background:{color}"></div>
                </div>
            </div>
            """

        severity_badges = ""
        critical = sum(1 for i in result.issues if i.severity.value == "critical")
        warnings = sum(1 for i in result.issues if i.severity.value == "warning")
        info = sum(1 for i in result.issues if i.severity.value == "info")
        if critical:
            severity_badges += f'<span class="badge badge-critical">{critical} Must fix</span> '
        if warnings:
            severity_badges += f'<span class="badge badge-warning">{warnings} Should fix</span> '
        if info:
            severity_badges += f'<span class="badge badge-info">{info} Nice to fix</span> '

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SEO Audit Report - {result.target_url}</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Oxygen,Ubuntu,sans-serif;background:#f0f4f8;color:#1e293b;line-height:1.6}}
.container{{max-width:960px;margin:0 auto;padding:24px 16px}}
.header{{background:linear-gradient(135deg,#1e293b,#334155);color:#fff;border-radius:12px;padding:32px;margin-bottom:24px}}
.header h1{{font-size:1.75rem;margin-bottom:4px}}
.header .subtitle{{color:#94a3b8;font-size:0.9rem;margin-bottom:12px}}
.header .meta{{color:#94a3b8;font-size:0.85rem}}
.header .meta span{{margin-right:20px}}
.score-hero{{display:flex;align-items:center;gap:32px;margin-top:20px}}
.score-circle{{width:100px;height:100px;border-radius:50%;background:conic-gradient({score_color} {score}%, #1e293b {score}%);display:flex;align-items:center;justify-content:center;flex-shrink:0}}
.score-circle-inner{{width:80px;height:80px;border-radius:50%;background:#1e293b;display:flex;align-items:center;justify-content:center;font-size:1.5rem;font-weight:700;color:#fff}}
.score-details h2{{font-size:1.1rem;font-weight:400;margin-bottom:4px}}
.score-label-text{{font-size:0.85rem;color:#94a3b8;margin-top:2px}}
.score-details .badges{{margin-top:8px}}
.badge{{display:inline-block;padding:3px 10px;border-radius:999px;font-size:0.8rem;font-weight:600}}
.badge-critical{{background:#fecaca;color:#dc2626}}
.badge-warning{{background:#fef08a;color:#ca8a04}}
.badge-info{{background:#bfdbfe;color:#2563eb}}
.card{{background:#fff;border-radius:10px;padding:24px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,0.08)}}
.card h3{{font-size:1.1rem;margin-bottom:16px;color:#334155}}
.legend{{display:flex;gap:16px;margin-bottom:16px;font-size:0.8rem;color:#64748b;flex-wrap:wrap}}
.legend-dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px}}
.scores-grid{{display:grid;gap:12px}}
.score-item{{}}
.score-label{{display:flex;justify-content:space-between;margin-bottom:4px;font-size:0.85rem}}
.score-value{{font-weight:600;margin-left:6px}}
.score-status{{font-size:0.75rem;color:#64748b}}
.score-bar-bg{{height:8px;background:#e2e8f0;border-radius:999px;overflow:hidden}}
.score-bar{{height:100%;border-radius:999px;transition:width 0.6s ease}}
.category-group{{background:#fff;border-radius:10px;margin-bottom:8px;box-shadow:0 1px 3px rgba(0,0,0,0.08);overflow:hidden}}
.category-summary{{padding:14px 20px;font-weight:600;cursor:pointer;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-size:0.95rem;text-transform:capitalize}}
.category-summary:hover{{background:#f1f5f9}}
.category-issues{{padding:8px 0}}
.issue-card{{padding:12px 20px;border-bottom:1px solid #f1f5f9;font-size:0.9rem}}
.issue-card:last-child{{border-bottom:none}}
.issue-header{{display:flex;align-items:flex-start;gap:8px;margin-bottom:4px}}
.issue-severity{{flex-shrink:0;width:8px;height:8px;border-radius:50%;margin-top:7px}}
.severity-critical{{background:#dc2626}}
.severity-warning{{background:#eab308}}
.severity-info{{background:#3b82f6}}
.issue-message{{font-weight:500}}
.issue-url{{color:#64748b;font-size:0.8rem;word-break:break-all;margin-bottom:6px;margin-left:16px}}
.issue-recommendation{{color:#475569;font-size:0.85rem;margin-left:16px;padding:8px 12px;background:#f8fafc;border-radius:6px;border-left:3px solid #e2e8f0;line-height:1.5}}
.issue-current{{color:#94a3b8;font-size:0.8rem;margin-left:16px;word-break:break-all}}
.summary-card{{background:#fff;border-radius:10px;padding:24px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0.08);text-align:center}}
.summary-card h2{{font-size:1.3rem;color:#334155;margin-bottom:8px}}
.summary-card p{{color:#64748b}}
.footer{{text-align:center;color:#94a3b8;font-size:0.8rem;padding:24px;margin-top:16px}}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>SEO Audit Report</h1>
        <div class="subtitle">A quick health check for your website. Here's what's working and what could be better.</div>
        <div class="meta">
            <span>Website: {result.target_url}</span>
            <span>Pages checked: {result.total_pages_crawled}</span>
            <span>Report date: {result.timestamp}</span>
        </div>
        <div class="score-hero">
            <div class="score-circle">
                <div class="score-circle-inner">{score}</div>
            </div>
            <div class="score-details">
                <h2>Overall SEO Score</h2>
                <div class="score-label-text">{score_label}</div>
                <div class="badges">{severity_badges}</div>
            </div>
        </div>
    </div>

    {self._crawl_errors_html(result.crawl_errors) if result.crawl_errors else ""}

    <div class="card">
        <h3>Category Scores</h3>
        <div class="legend">
            <span><span class="legend-dot" style="background:#22c55e"></span> Great shape</span>
            <span><span class="legend-dot" style="background:#eab308"></span> Could improve</span>
            <span><span class="legend-dot" style="background:#ef4444"></span> Needs attention</span>
        </div>
        <div class="scores-grid">{scores_rows}</div>
    </div>

    <div class="summary-card">
        <h2>Issues Found: {result.issue_count}</h2>
        <p>{result.summary}</p>
    </div>

    <h3 style="margin-bottom:12px;color:#334155">Issues by Category</h3>
    {sections_html}

    <div class="footer">
        Generated by SEO Audit Tool &mdash; Fix the "Must fix" items first, then work through the rest at your own pace.
    </div>
</div>
</body>
</html>"""

    def _crawl_errors_html(self, errors):
        items = "".join(f"<li>{e}</li>" for e in errors[:10])
        return f"""
        <div class="card" style="border-left:4px solid #ef4444">
            <h3>Encountered {len(errors)} problem{'s' if len(errors) != 1 else ''} while checking your site</h3>
            <p style="color:#64748b;font-size:0.85rem;margin-bottom:8px">Some pages couldn't be reached. This may affect the accuracy of this report.</p>
            <ul style="color:#dc2626;font-size:0.85rem;margin-left:16px">{items}</ul>
            {"<p style='color:#94a3b8;font-size:0.8rem;margin-top:4px'>...and " + str(len(errors)-10) + " more</p>" if len(errors) > 10 else ""}
        </div>
        """

    def _issue_card(self, issue):
        severity_class = f"severity-{issue.severity.value}"
        current = ""
        if issue.current_value:
            current = f'<div class="issue-current">Current: {issue.current_value[:200]}</div>'
        return f"""
        <div class="issue-card">
            <div class="issue-header">
                <span class="issue-severity {severity_class}"></span>
                <span class="issue-message">{issue.message}</span>
            </div>
            <div class="issue-url">{issue.page_url}</div>
            {current}
            <div class="issue-recommendation">{issue.recommendation}</div>
        </div>
        """
