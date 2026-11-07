"""Render the Markdown subset used by the course and generated reports."""
import html
import re
from urllib.parse import urlsplit

INLINE = re.compile(r"\[([^\]\n]+)\]\(([^\s)]+)\)|`([^`]+)`")


def inline(text):
    parts = []
    end = 0
    for match in INLINE.finditer(text):
        parts.append(html.escape(text[end:match.start()]))
        label, target, code = match.groups()
        if code is not None:
            parts.append("<code>" + html.escape(code) + "</code>")
        else:
            escaped = html.escape(label)
            try:
                parsed = urlsplit(target)
                safe = parsed.scheme == "https" or (
                    not parsed.scheme and not parsed.netloc and "\\" not in target
                )
            except ValueError:
                safe = False
            parts.append(f'<a href="{html.escape(target, quote=True)}">{escaped}</a>' if safe else escaped)
        end = match.end()
    parts.append(html.escape(text[end:]))
    return "".join(parts)


def document(text):
    blocks = []
    lines = iter(text.splitlines())
    for line in lines:
        if not line:
            continue
        if line.startswith("```"):
            code = []
            for code_line in lines:
                if code_line == "```":
                    break
                code.append(code_line)
            blocks.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
        elif match := re.fullmatch(r"(#{1,6}) (.*)", line):
            level = len(match[1])
            blocks.append(f"<h{level}>{inline(match[2])}</h{level}>")
        elif line.startswith("|"):
            rows = [line]
            for table_line in lines:
                if not table_line.startswith("|"):
                    break
                rows.append(table_line)
            body = []
            for i, row in enumerate(rows):
                if i == 1 and re.fullmatch(r"[| :\-]+", row):
                    continue
                tag = "th" if i == 0 else "td"
                cells = "".join(f"<{tag}>{inline(value.strip())}</{tag}>" for value in row.strip("|").split("|"))
                body.append("<tr>" + cells + "</tr>")
            blocks.append('<div class="scroller"><table>' + "".join(body) + "</table></div>")
        else:
            blocks.append("<p>" + inline(line) + "</p>")
    return ("<!doctype html><html lang='zh-CN'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Web3 Agent Lab · 教学阅读</title><link rel='stylesheet' href='/lab.css'>"
            "<main><p><a href='/'>返回实验室</a></p><section>" + "".join(blocks) +
            "</section></main></html>").encode()
