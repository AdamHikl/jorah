// The same JSON Schema subset as services/jorah-phone/jorah_phone/schema.py, for the plugin side.
// Only the keywords in KNOWN are understood; a schema with any other keyword is refused when loaded,
// and objects never accept unknown fields. Error messages name the place, never the value.

import { readFileSync } from "node:fs";
import { join } from "node:path";

const KNOWN = new Set(["$schema", "$id", "title", "description", "type", "properties", "required", "additionalProperties",
  "enum", "const", "minLength", "maxLength", "pattern", "minItems", "maxItems", "items", "minimum", "maximum", "format"]);
const TYPES = new Set(["object", "array", "string", "integer", "number", "boolean", "null"]);
const DATE_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:?\d{2})$/;

export class Invalid extends Error {
  constructor(path, message) {
    super(`${path}: ${message}`);
    this.path = path;
  }
}

export function checkSchema(schema, path = "$") {
  if (!schema || typeof schema !== "object" || Array.isArray(schema)) throw new Error(`${path}: a schema must be an object`);
  const unknown = Object.keys(schema).filter((k) => !KNOWN.has(k));
  if (unknown.length) throw new Error(`${path}: unsupported keyword(s): ${unknown.sort().join(", ")}`);
  for (const t of [].concat(schema.type ?? [])) if (!TYPES.has(t)) throw new Error(`${path}: unknown type ${t}`);
  if ("additionalProperties" in schema && schema.additionalProperties !== false) throw new Error(`${path}: only additionalProperties: false is supported`);
  if ("format" in schema && schema.format !== "date-time") throw new Error(`${path}: unsupported format ${schema.format}`);
  if ("pattern" in schema) new RegExp(schema.pattern, "u");
  for (const [name, sub] of Object.entries(schema.properties ?? {})) checkSchema(sub, `${path}.${name}`);
  for (const name of schema.required ?? []) if (!(name in (schema.properties ?? {}))) throw new Error(`${path}: required field ${name} has no schema`);
  if ("items" in schema) checkSchema(schema.items, `${path}[]`);
  return schema;
}

export function loadSchema(dir, name) {
  return checkSchema(JSON.parse(readFileSync(join(dir, `${name}.schema.json`), "utf8")));
}

export function isDateTime(text) {
  if (typeof text !== "string" || !DATE_TIME.test(text)) return false;
  const [y, mo, d] = text.slice(0, 10).split("-").map(Number);
  const [h, mi] = text.slice(11, 16).split(":").map(Number);
  const day = new Date(Date.UTC(y, mo - 1, d));
  return day.getUTCFullYear() === y && day.getUTCMonth() === mo - 1 && day.getUTCDate() === d && h < 24 && mi < 60
    && !Number.isNaN(Date.parse(text.replace(/([+-]\d{2})(\d{2})$/, "$1:$2")));
}

function typeOf(v) {
  if (v === null) return "null";
  if (typeof v === "boolean") return "boolean";
  if (typeof v === "number") return Number.isInteger(v) ? "integer" : "number";
  if (typeof v === "string") return "string";
  if (Array.isArray(v)) return "array";
  if (typeof v === "object") return "object";
  return "unknown";
}

const same = (a, b) => typeOf(a) === typeOf(b) && a === b;
const typeOk = (v, wanted) => [].concat(wanted).some((t) => t === typeOf(v) || (t === "number" && typeOf(v) === "integer"));

export function validate(schema, value, path = "$") {
  if ("const" in schema && !same(value, schema.const)) throw new Invalid(path, "has the wrong value");
  if ("enum" in schema && !schema.enum.some((o) => same(value, o))) throw new Invalid(path, "isn't one of the allowed values");
  if ("type" in schema && !typeOk(value, schema.type)) throw new Invalid(path, `must be ${[].concat(schema.type).join(" or ")}`);
  const kind = typeOf(value);
  if (kind === "integer" || kind === "number") {
    if (!Number.isFinite(value)) throw new Invalid(path, "must be a finite number");
    if ("minimum" in schema && value < schema.minimum) throw new Invalid(path, `is below ${schema.minimum}`);
    if ("maximum" in schema && value > schema.maximum) throw new Invalid(path, `is above ${schema.maximum}`);
  }
  if (kind === "string") {
    const length = [...value].length;
    if ("minLength" in schema && length < schema.minLength) throw new Invalid(path, `is shorter than ${schema.minLength}`);
    if ("maxLength" in schema && length > schema.maxLength) throw new Invalid(path, `is longer than ${schema.maxLength}`);
    if ("pattern" in schema && !new RegExp(schema.pattern, "u").test(value)) throw new Invalid(path, "has the wrong form");
    if (schema.format === "date-time" && !isDateTime(value)) throw new Invalid(path, "must be an ISO 8601 date and time with an offset");
  }
  if (kind === "array") {
    if ("minItems" in schema && value.length < schema.minItems) throw new Invalid(path, `has fewer than ${schema.minItems} items`);
    if ("maxItems" in schema && value.length > schema.maxItems) throw new Invalid(path, `has more than ${schema.maxItems} items`);
    if ("items" in schema) value.forEach((item, i) => validate(schema.items, item, `${path}[${i}]`));
  }
  if (kind === "object") {
    const props = schema.properties ?? {};
    for (const name of Object.keys(value)) if (!(name in props)) throw new Invalid(path, `has an unknown field ${JSON.stringify(name.slice(0, 40))}`);
    for (const name of schema.required ?? []) if (!(name in value)) throw new Invalid(path, `is missing ${name}`);
    for (const [name, sub] of Object.entries(props)) if (name in value) validate(sub, value[name], `${path}.${name}`);
  }
  return value;
}
