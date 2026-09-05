# Verify Runbook

Run the verifier after approved apply. It checks configured paths, the target Git commit, local Markdown links, audit item shape and package inventory. Also inspect the exact diff to ensure only approved item IDs changed. The verifier remains read-only. If verification exposes a mechanical error caused by this apply within its approved destinations, the caller returns to the same authorized apply, repairs it, and verifies again. New semantics, destinations, unrelated failures, or destructive scope require the missing owner decision.
