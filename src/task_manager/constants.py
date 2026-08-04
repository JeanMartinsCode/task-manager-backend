"""Shared constants for the Task Manager backend."""

# SQLite's INTEGER storage class is a signed 64-bit value. The stdlib
# sqlite3 driver raises an uncaught OverflowError for parameters outside
# this range, which previously surfaced as a generic unhandled 500. Every
# ID path/query/body parameter is bounded to this range so out-of-range
# IDs are rejected with 422 before ever reaching the database layer.
MAX_SQLITE_INTEGER = 9_223_372_036_854_775_807
