#!/usr/bin/env python3
"""Human-in-the-loop reproduction loop template."""

from __future__ import annotations


def step(instruction: str) -> None:
    print(f"\n>>> {instruction}")
    input("    [Enter when done] ")


def capture(question: str) -> str:
    print(f"\n>>> {question}")
    return input("    > ")


# --- edit below ---------------------------------------------------------

step("Open the app at http://localhost:3000 and sign in.")

errored = capture("Click the 'Export' button. Did it throw an error? (y/n)")

error_message = capture("Paste the error message (or 'none'):")

# --- edit above ---------------------------------------------------------

print("\n--- Captured ---")
print(f"ERRORED={errored}")
print(f"ERROR_MSG={error_message}")
