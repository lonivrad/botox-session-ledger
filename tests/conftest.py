import sys
import os

# Make the script importable without requiring package restructuring
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "agents",
        "skills",
        "botox-session-ledger",
        "scripts",
    ),
)
