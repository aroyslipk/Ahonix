// Minimal, safe markdown renderer for the AHONIX analyst answers.
// Supports ### headings, **bold**, - bullet lists and paragraphs.
//
// Defense-in-depth: the inline() function escapes HTML entities BEFORE
// insertion. The _sanitize() pass strips any residual dangerous patterns
// as an extra safety net against future regressions.

function inline(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
}

function _sanitize(html) {
  // Strip script/iframe/object/embed tags (even if somehow injected)
  let clean = html.replace(/<\s*\/?\s*(script|iframe|object|embed|form|meta|link|style)[^>]*>/gi, "");
  // Strip on* event handler attributes
  clean = clean.replace(/\s+on\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]*)/gi, "");
  // Strip javascript: URIs
  clean = clean.replace(/javascript\s*:/gi, "");
  // Strip data: URIs in href/src (potential XSS vector)
  clean = clean.replace(/(href|src)\s*=\s*["']?\s*data\s*:/gi, "$1=\"\"");
  return clean;
}

export function renderMarkdown(md) {
  if (!md) return "";
  const lines = md.split("\n");
  let html = "";
  let inList = false;
  const closeList = () => {
    if (inList) {
      html += "</ul>";
      inList = false;
    }
  };
  for (let raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      closeList();
      continue;
    }
    if (line.startsWith("### ")) {
      closeList();
      html += `<h3>${inline(line.slice(4))}</h3>`;
    } else if (line.startsWith("## ")) {
      closeList();
      html += `<h3>${inline(line.slice(3))}</h3>`;
    } else if (/^\s*[-*]\s+/.test(line)) {
      if (!inList) {
        html += "<ul>";
        inList = true;
      }
      html += `<li>${inline(line.replace(/^\s*[-*]\s+/, ""))}</li>`;
    } else {
      closeList();
      html += `<p>${inline(line)}</p>`;
    }
  }
  closeList();
  return _sanitize(html);
}

