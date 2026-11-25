import { markServerTimestampsUtc } from "./client";

const read = (body) => JSON.parse(JSON.stringify(body), markServerTimestampsUtc);

test("an unmarked server timestamp is read as UTC", () => {
  const { due_date } = read({ due_date: "2026-11-24T20:48:04" });
  expect(due_date).toBe("2026-11-24T20:48:04Z");
  expect(new Date(due_date).toISOString()).toBe("2026-11-24T20:48:04.000Z");
  expect(read({ at: "2026-11-24T20:48:04.123456" }).at).toBe("2026-11-24T20:48:04.123456Z");
});

test("date-only values, marked times and other strings are left as sent", () => {
  const body = read({ day: "2026-11-24", z: "2026-11-24T20:48:04Z", off: "2026-11-24T20:48:04+05:30",
                      name: "2026-11-24T20:48 meeting", n: 5, nested: [{ at: "2026-01-02T03:04:05" }] });
  expect(body.day).toBe("2026-11-24");
  expect(body.z).toBe("2026-11-24T20:48:04Z");
  expect(body.off).toBe("2026-11-24T20:48:04+05:30");
  expect(body.name).toBe("2026-11-24T20:48 meeting");
  expect(body.n).toBe(5);
  expect(body.nested[0].at).toBe("2026-01-02T03:04:05Z");
});
