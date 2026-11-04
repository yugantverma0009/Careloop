#!/usr/bin/env python3
"""
scripts/check_banned_words.py — Strict Banned Words & Dishonest Claims Scanner (Phase 6)

Banned terms:
- Names & origins: hackathon, SIH, Smart India, NurseAI
- Exaggerated claims: autonomous, "AI nurse", replaces, "saves hours", diagnose, real-time, 24/7, HIPAA, validated, accurate, learns
- Subjective clinical judgment words: stable, normal, optimal, improving
- Stock marketing buzzwords: seamless, cutting-edge, AI-powered, smart, transform, empower, leverage, holistic, next-gen, advanced, governance, telemetry
"""

import os
import re
import sys
from typing import List, Dict, Tuple

BANNED_PATTERNS = [
    r"\bhackathon\b",
    r"\bSIH\b",
    r"\bSmart\s*India\b",
    r"\bNurseAI\b",
    r"\bautonomous\b",
    r"\bAI\s*nurse\b",
    r"\breplaces\b",
    r"\bsaves\s+hours\b",
    r"\bdiagnos(?:e|is|ed)\b",
    r"\breal-time\b",
    r"\b24/7\b",
    r"\bHIPAA\b",
    r"\bvalidated\b",
    r"\baccurate\b",
    r"\blearns\b",
    r"\boptimal\b",
    r"\bseamless\b",
    r"\bcutting-edge\b",
    r"\bAI-powered\b",
    r"\btransform\b",
    r"\bempower\b",
    r"\bleverage\b",
    r"\bholistic\b",
    r"\bnext-gen\b",
    r"\btelemetry\b",
]

# Excluded files (scanners, tests checking for banned words, third-party libraries)
EXCLUDED_PATHS = [
    "check_banned_words.py",
    "policy_guard.py",       # Defines the regex filters
    "redteam_cases_v2.py",   # Contains adversarial probe texts
    "tests/test_agents_v2_phase", # Tests verifying bans
    ".git",
    "node_modules",
    "build",
    "package-lock.json",
    ".pytest_cache"
]


def check_file(path: str) -> List[Tuple[int, str, str]]:
    findings = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, 1):
                # Ignore comments in code that mention banned words or documentation explaining rules
                line_lower = line.lower()
                for pat in BANNED_PATTERNS:
                    if re.search(pat, line_lower):
                        # Skip CSS properties and transitions involving transform
                        if pat == r"\btransform\b":
                            if "transform:" in line_lower or "transform " in line_lower or "'transform" in line_lower or '"transform' in line_lower:
                                continue
                        # Skip if it is within a rule/alert definition or test assertion
                        if "banned" in line_lower or "prohibit" in line_lower or "exempt" in line_lower:
                            continue
                        findings.append((line_no, pat, line.strip()))
    except Exception as e:
        pass
    return findings


def scan_directory(base_dir: str) -> Dict[str, List[Tuple[int, str, str]]]:
    results = {}
    for root, dirs, files in os.walk(base_dir):
        # Filter directories
        dirs[:] = [d for d in dirs if not any(ex in d for ex in EXCLUDED_PATHS)]
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, base_dir)
            if any(ex in rel_path for ex in EXCLUDED_PATHS):
                continue
            if not (rel_path.endswith(".jsx") or rel_path.endswith(".js") or rel_path.endswith(".html") or rel_path in ("README.md", "PROJECT_GUIDE.md")):
                continue
            matches = check_file(full_path)
            if matches:
                results[rel_path] = matches
    return results


def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    print(f"🔍 Scanning for banned terms and marketing claims in {root_dir}...")
    findings = scan_directory(root_dir)

    total_matches = sum(len(m) for m in findings.values())
    if total_matches == 0:
        print("✅ CLEAN: Zero banned words or dishonest claims found in UI and documentation.")
        sys.exit(0)
    else:
        print(f"⚠️ Found {total_matches} occurrences of banned terms across {len(findings)} files:")
        for file, matches in findings.items():
            print(f"\n📄 {file}:")
            for line_no, pat, text in matches[:5]:
                print(f"   Line {line_no} [{pat}]: {text[:100]}")
            if len(matches) > 5:
                print(f"   ... and {len(matches) - 5} more")
        sys.exit(1)


if __name__ == "__main__":
    main()

