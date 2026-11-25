// A small YAML reader for the project folder's files (docs/plan/11-project-mode.md section 3), so
// the plugin needs no install. It reads the subset those files use: block mappings and sequences,
// compact mappings inside sequences, flow [..] and {..} (also over several lines), plain, single-
// and double-quoted scalars (also wrapped over several lines, as PyYAML writes long ones), block
// scalars (| and >, with chomping), comments, null, booleans and numbers. Dates and times stay
// strings. Anything else (anchors, aliases, tags, complex keys, several documents, duplicate keys,
// bad indentation) throws, so the caller shows the file as unknown instead of guessing. Flow
// mappings follow YAML: `{ a: x, y }` gives { a: "x", y: null }.

export class YamlError extends Error {
  constructor(line, why) {
    super(`line ${line + 1}: ${why}`);
    this.line = line + 1;
  }
}

const indentOf = (s) => s.length - s.trimStart().length;

// Cut a comment: '#' at the start or after whitespace, outside quotes.
function stripComment(s) {
  let q = null;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (q) {
      if (q === '"' && c === "\\") { i++; continue; }
      if (c === q) {
        if (q === "'" && s[i + 1] === "'") { i++; continue; }
        q = null;
      }
      continue;
    }
    if (c === '"' || c === "'") {
      // A quote opens a quoted scalar only at the start of a token.
      const prev = i === 0 ? " " : s[i - 1];
      if (/[\s[{,:-]/.test(prev)) q = c;
      continue;
    }
    if (c === "#" && (i === 0 || /\s/.test(s[i - 1]))) return s.slice(0, i).trimEnd();
  }
  return s.trimEnd();
}

const PLAIN_NULL = new Set(["", "~", "null", "Null", "NULL"]);
const INT = /^[-+]?\d+$/;
const FLOAT = /^[-+]?(\d+\.\d*|\.\d+|\d+(\.\d*)?[eE][-+]?\d+)$/;

function plainValue(raw, line) {
  const s = raw.trim();
  if (/^[&*!]/.test(s)) throw new YamlError(line, "anchors, aliases and tags aren't supported");
  if (s.startsWith("? ")) throw new YamlError(line, "complex keys aren't supported");
  if (PLAIN_NULL.has(s)) return null;
  if (/^(true|True|TRUE)$/.test(s)) return true;
  if (/^(false|False|FALSE)$/.test(s)) return false;
  if (INT.test(s)) {
    const n = Number(s);
    return Number.isSafeInteger(n) ? n : s;
  }
  if (FLOAT.test(s)) return Number(s);
  return s;
}

const ESCAPES = {
  "0": "\0", a: "\x07", b: "\b", t: "\t", "\t": "\t", n: "\n", v: "\v", f: "\f", r: "\r", e: "\x1b",
  " ": " ", '"': '"', "/": "/", "\\": "\\", N: "\x85", _: "\xa0", L: " ", P: " ",
};

// One escape at s[j] (a backslash) in a double-quoted scalar; returns [text, length].
function readEscape(s, j, line) {
  const e = s[j + 1];
  const hex = { x: 2, u: 4, U: 8 }[e];
  if (hex) {
    const h = s.slice(j + 2, j + 2 + hex);
    if (!new RegExp(`^[0-9a-fA-F]{${hex}}$`).test(h)) throw new YamlError(line, `bad escape \\${e}${h}`);
    return [String.fromCodePoint(parseInt(h, 16)), 2 + hex];
  }
  if (e !== undefined && Object.hasOwn(ESCAPES, e)) return [ESCAPES[e], 2];
  throw new YamlError(line, `unknown escape \\${e ?? ""}`);
}

// A quoted scalar starting at s[i]; returns [value, index after the closing quote], or null when
// `open` is set and the quote doesn't close in s. s may hold several lines joined with "\n" (a
// scalar PyYAML wrapped): each line break folds as YAML says (one break is a space, each blank line
// a newline, the whitespace around the break goes), and in double quotes a backslash before the
// break joins the lines with nothing between them.
function readQuoted(s, i, line, open = false) {
  const q = s[i];
  let j = i + 1;
  let out = "";
  let kept = 0; // out[0, kept) is escaped or folded text that a line break mustn't trim
  while (j < s.length) {
    const c = s[j];
    if (c === "\n" || (q === '"' && c === "\\" && s[j + 1] === "\n")) {
      const escaped = c === "\\";
      if (!escaped) out = out.slice(0, kept) + out.slice(kept).replace(/[ \t]+$/, "");
      j += escaped ? 2 : 1;
      let breaks = 0;
      for (;;) {
        while (s[j] === " " || s[j] === "\t") j++;
        if (s[j] !== "\n") break;
        breaks++;
        j++;
      }
      out += breaks ? "\n".repeat(breaks) : escaped ? "" : " ";
      kept = out.length;
      continue;
    }
    if (q === '"' && c === "\\") {
      if (j + 1 >= s.length) break; // a backslash ending the line escapes the line break after it
      const [t, n] = readEscape(s, j, line);
      out += t;
      kept = out.length;
      j += n;
      continue;
    }
    if (c === q) {
      if (q === "'" && s[j + 1] === "'") { out += "'"; kept = out.length; j += 2; continue; }
      return [out, j + 1];
    }
    out += c;
    j++;
  }
  if (open) return null;
  throw new YamlError(line, "unterminated quoted string");
}

// Flow collections: [a, b] and { k: v }.
function parseFlow(s, line) {
  let i = 0;
  const ws = () => { while (i < s.length && /\s/.test(s[i])) i++; };
  const plain = (stops) => {
    const start = i;
    while (i < s.length) {
      const c = s[i];
      if (stops.includes(c)) break;
      if (c === ":" && (i + 1 >= s.length || /[\s,\]}]/.test(s[i + 1])) && stops.includes(":")) break;
      i++;
    }
    return s.slice(start, i).trim();
  };
  const value = (stops) => {
    ws();
    const c = s[i];
    if (c === "[") return seq();
    if (c === "{") return map();
    if (c === '"' || c === "'") { const [v, j] = readQuoted(s, i, line); i = j; return v; }
    return plainValue(plain(stops), line);
  };
  function seq() {
    i++; // [
    const out = [];
    for (;;) {
      ws();
      if (s[i] === "]") { i++; return out; }
      if (i >= s.length) throw new YamlError(line, "unterminated [");
      out.push(value([",", "]"]));
      ws();
      if (s[i] === ",") { i++; continue; }
      if (s[i] === "]") { i++; return out; }
      throw new YamlError(line, "expected , or ] in a flow list");
    }
  }
  function map() {
    i++; // {
    const out = {};
    for (;;) {
      ws();
      if (s[i] === "}") { i++; return out; }
      if (i >= s.length) throw new YamlError(line, "unterminated {");
      let key;
      if (s[i] === '"' || s[i] === "'") { const [v, j] = readQuoted(s, i, line); i = j; key = v; } else key = plain([",", "}", ":"]);
      if (key === "") throw new YamlError(line, "empty key in a flow mapping");
      ws();
      let v = null;
      if (s[i] === ":") { i++; v = value([",", "}"]); ws(); }
      if (Object.hasOwn(out, key)) throw new YamlError(line, `duplicate key ${key}`);
      out[key] = v;
      if (s[i] === ",") { i++; continue; }
      if (s[i] === "}") { i++; return out; }
      throw new YamlError(line, "expected , or } in a flow mapping");
    }
  }
  const v = value([]);
  ws();
  if (i < s.length) throw new YamlError(line, "text after a flow collection");
  return v;
}

const balanced = (s) => {
  let depth = 0;
  let q = null;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (q) {
      if (q === '"' && c === "\\") { i++; continue; }
      if (c === q) q = null;
      continue;
    }
    if (c === '"' || c === "'") q = c;
    else if (c === "[" || c === "{") depth++;
    else if (c === "]" || c === "}") depth--;
  }
  return depth <= 0;
};

// Split "key: rest" at the first ": " (or a trailing ":") outside quotes and brackets.
function splitKey(content, line) {
  let i = 0;
  let key;
  if (content[0] === '"' || content[0] === "'") {
    const [v, j] = readQuoted(content, 0, line);
    i = j;
    while (content[i] === " ") i++;
    if (content[i] !== ":" || (i + 1 < content.length && content[i + 1] !== " ")) return null;
    key = v;
    return { key, rest: content.slice(i + 1).trim() };
  }
  if (/^[[{]/.test(content)) return null;
  for (; i < content.length; i++) {
    if (content[i] === ":" && (i + 1 === content.length || content[i + 1] === " " || content[i + 1] === "\t")) {
      key = content.slice(0, i).trim();
      if (!key) return null;
      if (/^[&*!?]/.test(key)) throw new YamlError(line, "anchors, aliases, tags and complex keys aren't supported");
      return { key, rest: content.slice(i + 1).trim() };
    }
  }
  return null;
}

const isSeqItem = (content) => content === "-" || content.startsWith("- ");

export function parseYaml(text) {
  const lines = String(text).replace(/^﻿/, "").split(/\r?\n/);
  // Tabs as indentation are not YAML.
  const tabbed = lines.findIndex((l) => /^ *\t/.test(l) && l.trim() !== "");
  if (tabbed >= 0) throw new YamlError(tabbed, "tab used for indentation");
  let pos = 0;
  // Document markers: one leading ---, an optional trailing ...; a second document is refused.
  const firstContent = lines.findIndex((l) => stripComment(l).trim() !== "");
  if (firstContent >= 0 && /^---(\s|$)/.test(lines[firstContent])) {
    const rest = lines[firstContent].slice(3).trim();
    lines[firstContent] = rest ? rest : "";
  }
  for (let k = 0; k < lines.length; k++) {
    if (/^---(\s|$)/.test(lines[k])) throw new YamlError(k, "more than one document");
    if (/^\.\.\.\s*$/.test(lines[k])) {
      if (lines.slice(k + 1).some((l) => stripComment(l).trim() !== "")) throw new YamlError(k, "text after the document end");
      lines.length = k;
      break;
    }
  }

  const significant = () => {
    while (pos < lines.length && stripComment(lines[pos]).trim() === "") pos++;
    return pos < lines.length;
  };

  function blockScalar(header, parentIndent, line) {
    const m = /^([|>])([+-]?)(\d?)([+-]?)$/.exec(header);
    if (!m) throw new YamlError(line, `bad block scalar header ${header}`);
    const folded = m[1] === ">";
    const chomp = m[2] || m[4];
    const explicit = m[3] ? Number(m[3]) : null;
    const body = [];
    let indent = explicit !== null ? parentIndent + explicit : null;
    while (pos < lines.length) {
      const l = lines[pos];
      if (l.trim() === "") { body.push(""); pos++; continue; }
      const n = indentOf(l);
      if (indent === null) {
        if (n <= parentIndent) break;
        indent = n;
      }
      if (n < indent) break;
      body.push(l.slice(indent));
      pos++;
    }
    // Trailing blank lines belong to chomping.
    let end = body.length;
    while (end > 0 && body[end - 1] === "") end--;
    const trailing = body.length - end;
    const kept = body.slice(0, end);
    let text;
    if (!folded) text = kept.join("\n");
    else {
      text = "";
      for (let k = 0; k < kept.length; k++) {
        const cur = kept[k];
        if (k === 0) { text = cur; continue; }
        const prev = kept[k - 1];
        if (cur === "") text += "\n";
        else if (prev === "" || /^\s/.test(cur) || /^\s/.test(prev)) text += (prev === "" ? "" : "\n") + cur;
        else text += ` ${cur}`;
      }
    }
    if (kept.length === 0) return chomp === "+" ? "\n".repeat(trailing) : "";
    if (chomp === "-") return text;
    if (chomp === "+") return `${text}\n${"\n".repeat(trailing)}`;
    return `${text}\n`;
  }

  // A value that starts after "key:" or "- " on line `line` (already stripped of its comment).
  function inlineValue(rest, ownIndent, line) {
    if (/^[|>]/.test(rest)) return blockScalar(rest, ownIndent, line);
    if (rest[0] === "[" || rest[0] === "{") {
      let s = rest;
      while (!balanced(s)) {
        if (pos >= lines.length) throw new YamlError(line, "unterminated flow collection");
        s += ` ${stripComment(lines[pos]).trim()}`;
        pos++;
      }
      return parseFlow(s, line);
    }
    if (rest[0] === '"' || rest[0] === "'") {
      // A quoted scalar may go on over more-indented (or blank) lines, as PyYAML wraps long ones.
      let s = rest;
      let r;
      while (!(r = readQuoted(s, 0, line, true))) {
        if (pos >= lines.length || (lines[pos].trim() !== "" && indentOf(lines[pos]) <= ownIndent)) {
          throw new YamlError(line, "unterminated quoted string");
        }
        s += `\n${lines[pos]}`;
        pos++;
      }
      if (stripComment(s.slice(r[1])).trim() !== "") throw new YamlError(line, "text after a quoted string");
      return r[0];
    }
    // Plain scalar, possibly continued on more-indented lines that aren't keys or items.
    let s = rest;
    while (pos < lines.length) {
      const l = lines[pos];
      const c = stripComment(l).trim();
      if (c === "") {
        // A blank line inside a plain scalar folds to a newline only if more text follows.
        let k = pos;
        while (k < lines.length && stripComment(lines[k]).trim() === "") k++;
        if (k < lines.length && indentOf(lines[k]) > ownIndent && !splitKey(stripComment(lines[k]).trim(), k)) {
          s += "\n";
          pos = k;
          continue;
        }
        break;
      }
      // A more-indented line goes on the scalar, "- " at its start too (YAML reads it so).
      if (indentOf(l) <= ownIndent || splitKey(c, pos)) break;
      s += s.endsWith("\n") ? c : ` ${c}`;
      pos++;
    }
    return plainValue(s, line);
  }

  function block(minIndent) {
    if (!significant()) return null;
    const n = indentOf(lines[pos]);
    if (n < minIndent) return null;
    const content = stripComment(lines[pos]).trim();
    if (isSeqItem(content)) return seq(n);
    if (splitKey(content, pos)) return map(n);
    const line = pos;
    pos++;
    return inlineValue(content, n - 1, line);
  }

  function map(n) {
    const out = {};
    while (significant()) {
      const l = lines[pos];
      const ind = indentOf(l);
      if (ind < n) break;
      if (ind > n) throw new YamlError(pos, "bad indentation");
      const content = stripComment(l).trim();
      if (isSeqItem(content)) break; // a list at the parent's indent belongs to the parent key
      const kv = splitKey(content, pos);
      if (!kv) throw new YamlError(pos, "expected key: value");
      if (Object.hasOwn(out, kv.key)) throw new YamlError(pos, `duplicate key ${kv.key}`);
      const line = pos;
      pos++;
      if (kv.rest === "") {
        if (!significant()) { out[kv.key] = null; break; }
        const next = indentOf(lines[pos]);
        const nc = stripComment(lines[pos]).trim();
        if (next === n && isSeqItem(nc)) out[kv.key] = seq(n);
        else if (next > n) out[kv.key] = block(next);
        else out[kv.key] = null;
      } else {
        out[kv.key] = inlineValue(kv.rest, n, line);
      }
    }
    return out;
  }

  function seq(n) {
    const out = [];
    while (significant()) {
      const l = lines[pos];
      const ind = indentOf(l);
      if (ind < n) break;
      if (ind > n) throw new YamlError(pos, "bad indentation");
      const content = stripComment(l).trim();
      if (!isSeqItem(content)) break;
      const rest = content === "-" ? "" : content.slice(2).trim();
      if (rest === "") {
        pos++;
        if (!significant() || indentOf(lines[pos]) <= n) { out.push(null); continue; }
        out.push(block(indentOf(lines[pos])));
        continue;
      }
      // "- key: v" or "- - x": re-read the rest as a block at its own column.
      const col = l.indexOf(rest, ind + 1);
      if (splitKey(rest, pos) || isSeqItem(rest)) {
        lines[pos] = " ".repeat(col) + l.slice(col);
        out.push(block(col));
        continue;
      }
      const line = pos;
      pos++;
      out.push(inlineValue(rest, n, line));
    }
    return out;
  }

  const value = block(0);
  if (significant()) throw new YamlError(pos, "unexpected text (bad indentation?)");
  return value;
}
