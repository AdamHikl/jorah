// Calendar and wall-clock maths in Europe/Bratislava, including both daylight-saving nights.

import { test } from "node:test";
import assert from "node:assert/strict";
import { addDays, addMonths, daysBetween, isDate, isTime, localNow, longDate, weekdayName, zonedInstant } from "../lib/dates.js";

const TZ = "Europe/Bratislava";

test("addDays and daysBetween cross months, years and leap days", () => {
  assert.equal(addDays("2026-11-17", 180), "2027-05-16");
  assert.equal(addDays("2026-12-31", 1), "2027-01-01");
  assert.equal(addDays("2028-02-28", 1), "2028-02-29");
  assert.equal(addDays("2027-03-01", -1), "2027-02-28");
  assert.equal(daysBetween("2026-11-17", "2027-05-16"), 180);
  assert.equal(daysBetween("2027-05-16", "2026-11-17"), -180);
  // Across both clock changes the count stays in whole days.
  assert.equal(daysBetween("2027-03-27", "2027-03-29"), 2);
  assert.equal(daysBetween("2026-10-24", "2026-10-26"), 2);
});

test("addMonths keeps the day, or the month's last day when the month is shorter", () => {
  assert.equal(addMonths("2027-05-14", -1), "2027-04-14");
  assert.equal(addMonths("2027-01-31", 1), "2027-02-28");
  assert.equal(addMonths("2028-01-31", 1), "2028-02-29");
  assert.equal(addMonths("2027-03-31", -1), "2027-02-28");
  assert.equal(addMonths("2026-11-30", 3), "2027-02-28");
  assert.equal(addMonths("2027-01-15", -13), "2025-12-15");
});

test("isDate and isTime reject impossible values", () => {
  assert.ok(isDate("2028-02-29"));
  assert.ok(!isDate("2027-02-29"));
  assert.ok(!isDate("2027-13-01"));
  assert.ok(!isDate("27-01-01"));
  assert.ok(isTime("09:00") && isTime("23:59"));
  assert.ok(!isTime("24:00") && !isTime("9:00"));
});

test("weekday and long date", () => {
  assert.equal(weekdayName("2026-11-17"), "Tuesday");
  assert.equal(longDate("2027-04-15"), "Thursday 15 April 2027");
});

test("localNow: Adam's date, not UTC's, around midnight", () => {
  assert.equal(localNow(TZ, new Date("2026-11-17T23:30:00Z")).date, "2026-11-18");
  assert.equal(localNow(TZ, new Date("2026-11-17T23:30:00Z")).time, "00:30");
  assert.equal(localNow(TZ, new Date("2027-06-30T22:30:00Z")).date, "2027-07-01");
});

test("zonedInstant: 09:00 in winter is 08:00 UTC, in summer 07:00 UTC", () => {
  assert.equal(zonedInstant("2026-12-01", "09:00", TZ).at.toISOString(), "2026-12-01T08:00:00.000Z");
  assert.equal(zonedInstant("2027-04-15", "09:00", TZ).at.toISOString(), "2027-04-15T07:00:00.000Z");
  assert.equal(zonedInstant("2027-04-15", "09:00", TZ).shifted, false);
});

test("zonedInstant: a time the spring night skips moves forward; the autumn repeat takes the first", () => {
  const gap = zonedInstant("2027-03-28", "02:30", TZ);
  assert.equal(gap.shifted, true);
  assert.equal(gap.at.toISOString(), "2027-03-28T01:30:00.000Z"); // 03:30 summer time
  const overlap = zonedInstant("2026-10-25", "02:30", TZ);
  assert.equal(overlap.shifted, false);
  assert.equal(overlap.at.toISOString(), "2026-10-25T00:30:00.000Z"); // 02:30 summer time, the first
  assert.equal(zonedInstant("2027-03-28", "03:00", TZ).at.toISOString(), "2027-03-28T01:00:00.000Z");
});
