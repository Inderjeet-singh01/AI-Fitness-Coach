import React from 'react';

function renderInline(text) {
  const chunks = String(text || '').split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^\)]+\))/g);
  return chunks.map((c, i) => {
    if (c.startsWith('**') && c.endsWith('**')) return <strong key={i}>{c.slice(2, -2)}</strong>;
    if (c.startsWith('`') && c.endsWith('`')) return <code key={i}>{c.slice(1, -1)}</code>;
    const m = c.match(/^\[([^\]]+)\]\(([^\)]+)\)$/);
    if (m) return <a key={i} href={m[2]} target="_blank" rel="noreferrer">{m[1]}</a>;
    return <React.Fragment key={i}>{c}</React.Fragment>;
  });
}

export function Report({ text }) {
  const clean = String(text || '').replace(/\r/g, '').replace(/^\s*---+\s*$/gm, '').trim();
  const lines = clean.split('\n');
  const nodes = [];
  let paragraph = [];
  let list = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    nodes.push(<p key={`p-${nodes.length}`}>{paragraph.map((line, i) => <React.Fragment key={i}>{i > 0 && <br />}{renderInline(line)}</React.Fragment>)}</p>);
    paragraph = [];
  };
  const flushList = () => {
    if (!list.length) return;
    const ordered = list[0].match(/^\d+[.)]\s+/);
    const Tag = ordered ? 'ol' : 'ul';
    nodes.push(<Tag key={`l-${nodes.length}`}>{list.map((item, i) => <li key={i}>{renderInline(item.replace(/^(?:[-*]|\d+[.)])\s+/, ''))}</li>)}</Tag>);
    list = [];
  };

  lines.forEach((raw, idx) => {
    const line = raw.trim();
    if (!line) { flushList(); flushParagraph(); return; }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      flushList(); flushParagraph();
      const H = `h${heading[1].length}`;
      nodes.push(React.createElement(H, { key: `h-${idx}` }, renderInline(heading[2])));
      return;
    }
    if (/^[-*]\s+/.test(line) || /^\d+[.)]\s+/.test(line)) {
      flushParagraph();
      const type = /^\d+[.)]\s+/.test(line) ? 'ordered' : 'unordered';
      if (list.length && ((/^\d+[.)]\s+/.test(list[0])) !== (type === 'ordered'))) flushList();
      list.push(line);
      return;
    }
    flushList();
    if (line.startsWith('> ')) paragraph.push(line.slice(2));
    else paragraph.push(line);
  });
  flushList(); flushParagraph();
  return <div className="report-text">{nodes}</div>;
}

export default Report;
