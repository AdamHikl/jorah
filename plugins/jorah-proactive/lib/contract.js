// Checks the phone service's answers against the contract's own schemas
// (packages/contracts/phone/*.schema.json, docs/contracts/jorah-phone-v1.md). Only the JSON Schema
// keywords those files use are understood; any other keyword that could restrict a value makes
// loading fail, so a contract change can't quietly loosen this check.

import { readFileSync } from "node:fs";
import { join } from "node:path";

export class Invalid extends Error {
  constructor(path, why) {
    super(`${path}: ${why}`);
    this.path = path;
  }
}

const KNOWN = new Set(["$schema", "$id", "title", "description", "type", "const", "enum", "required", "properties",
  "additionalProperties", "items", "maxItems", "minItems", "pattern", "maxLength", "minLength", "minimum", "maximum", "format"]);

function checkKeywords(schema, path = "#") {
  if (!schema || typeof schema !== "object") return;
  for (const k of Object.keys(schema)) if (!KNOWN.has(k)) throw new Error(`schema keyword ${k} at ${path} isn't understood here`);
  for (const [k, v] of Object.entries(schema.properties ?? {})) checkKeywords(v, `${path}/${k}`);
  if (schema.items) checkKeywords(schema.items, `${path}/items`);
}

export function loadSchema(dir, name) {
  const schema = JSON.parse(readFileSync(join(dir, `${name}.schema.json`), "utf8"));
  checkKeywords(schema);
  return schema;
}

const typeOf = (v) => (v === null ? "null" : Array.isArray(v) ? "array" : Number.isInteger(v) ? "integer" : typeof v);
const DATE_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/;

export function validate(schema, value, path = "$") {
  if ("const" in schema && value !== schema.const) throw new Invalid(path, "wrong constant");
  if (schema.enum && !schema.enum.includes(value)) throw new Invalid(path, "not an allowed value");
  if (schema.type) {
    const types = Array.isArray(schema.type) ? schema.type : [schema.type];
    const t = typeOf(value);
    if (!types.includes(t) && !(t === "integer" && types.includes("number"))) throw new Invalid(path, `expected ${types.join("|")}`);
  }
  if (typeof value === "string") {
    if (schema.maxLength !== undefined && value.length > schema.maxLength) throw new Invalid(path, "too long");
    if (schema.minLength !== undefined && value.length < schema.minLength) throw new Invalid(path, "too short");
    if (schema.pattern && !new RegExp(schema.pattern, "u").test(value)) throw new Invalid(path, "wrong pattern");
    if (schema.format === "date-time" && (!DATE_TIME.test(value) || Number.isNaN(Date.parse(value)))) throw new Invalid(path, "not a date-time");
  }
  if (typeof value === "number") {
    if (schema.minimum !== undefined && value < schema.minimum) throw new Invalid(path, "too small");
    if (schema.maximum !== undefined && value > schema.maximum) throw new Invalid(path, "too large");
  }
  if (Array.isArray(value)) {
    if (schema.maxItems !== undefined && value.length > schema.maxItems) throw new Invalid(path, "too many items");
    if (schema.minItems !== undefined && value.length < schema.minItems) throw new Invalid(path, "too few items");
    if (schema.items) value.forEach((v, i) => validate(schema.items, v, `${path}[${i}]`));
  }
  if (value && typeof value === "object" && !Array.isArray(value)) {
    for (const k of schema.required ?? []) if (!(k in value)) throw new Invalid(`${path}.${k}`, "missing");
    for (const [k, v] of Object.entries(value)) {
      const sub = schema.properties?.[k];
      if (sub) validate(sub, v, `${path}.${k}`);
      else if (schema.additionalProperties === false) throw new Invalid(`${path}.${k}`, "not allowed");
    }
  }
  return value;
}
