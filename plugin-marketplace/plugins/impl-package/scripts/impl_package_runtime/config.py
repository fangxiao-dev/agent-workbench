"""Stable document grammar exported for older Harness adapters.

The runtime is 3.5 Ticket-only.  These patterns are compatibility metadata for
adapters that still inspect legacy 3.2/3.4 documents; they are not a second
runtime state reader.
"""


CONFIG = {
    "documents": {
        "compositionPattern": r"Composition[^\n]*tickets=(true|false),\s*dag=(true|false)",
        "attemptPattern": r"(?im)^[^\r\n]*(?:Attempt ID|执行尝试 ID)[^：:\r\n]*[：:][ \t]*(?:\*\*)?[ \t]*([^\s*]+)",
        "ticketIdPattern": r"(?im)^[^\r\n]*Ticket ID[^：:\r\n]*[：:][ \t]*(?:\*\*)?[ \t]*([^\s*]+)",
        "taskHeadingPattern": r"(?m)^###\s+(T\d+)\s*[:：]",
        "taskBlockPattern": r"(?ms)^###\s+{task_id}\s*[:：].*?(?=^###\s+T\d+\s*[:：]|^##\s|\Z)",
        "taskStatePattern": r"(?m)^-\s*状态[：:]\s*([A-Z_-]+)",
        "ticketStatePattern": r"(?m)^-\s*值[：:]\s*\[?([^]\n]+)",
        "dagArtifactPatterns": ["dag.md", "*.patch-dag.md"],
        "ticketArtifactPatterns": ["tickets/*.md"],
    },
}
