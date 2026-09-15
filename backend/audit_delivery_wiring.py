#!/usr/bin/env python3
"""Comprehensive audit of delivery wiring in all message handlers."""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple

HANDLERS_DIR = Path("app/services/message_handlers")
DELIVERY_PATTERNS = {
    "delivery_call": r"(get_delivery_service|delivery\.send_whatsapp|delivery\.send_email)",
    "placeholder": r"(TODO|PLACEHOLDER|FIXME).*delivery",
    "result_return": r"return\s*\{[\s\S]*?delivery_id",
}

def analyze_handler(filepath: Path) -> Dict:
    """Analyze single handler file for delivery patterns."""
    try:
        content = filepath.read_text()
        class_match = re.search(r'class\s+(\w+)', content)
        handler_name = class_match.group(1) if class_match else filepath.stem
        
        has_delivery_call = bool(re.search(DELIVERY_PATTERNS["delivery_call"], content))
        has_placeholder = bool(re.search(DELIVERY_PATTERNS["placeholder"], content))
        has_result_return = bool(re.search(DELIVERY_PATTERNS["result_return"], content))
        
        # Check for actual send attempts
        send_whatsapp = "send_whatsapp" in content
        send_email = "send_email" in content
        delivery_import = "from app.services.delivery_factory import get_delivery_service" in content
        
        # Determine status
        if has_placeholder:
            status = "PLACEHOLDER"
        elif has_delivery_call and (send_whatsapp or send_email):
            status = "WIRED" if has_result_return else "PARTIAL"
        else:
            status = "MISSING"
        
        return {
            "file": filepath.name,
            "handler": handler_name,
            "status": status,
            "has_delivery_call": has_delivery_call,
            "has_placeholder": has_placeholder,
            "has_result_return": has_result_return,
            "send_whatsapp": send_whatsapp,
            "send_email": send_email,
            "delivery_import": delivery_import,
        }
    except Exception as e:
        return {"file": filepath.name, "error": str(e)}

# Run audit
results = []
for handler_file in sorted(HANDLERS_DIR.glob("*.py")):
    if handler_file.name.startswith("__") or handler_file.name == "base_message_handler.py":
        continue
    results.append(analyze_handler(handler_file))

# Print results
print("\n=== DELIVERY WIRING AUDIT ===\n")
print(f"{'Handler':<40} {'Status':<12} {'WhatsApp':<8} {'Email':<8} {'Import':<8}")
print("-" * 80)

wired_count = 0
partial_count = 0
placeholder_count = 0
missing_count = 0

for r in results:
    if "error" in r:
        print(f"{r['file']:<40} ERROR: {r['error']}")
        continue
    
    status = r["status"]
    wa = "✓" if r["send_whatsapp"] else "-"
    em = "✓" if r["send_email"] else "-"
    imp = "✓" if r["delivery_import"] else "-"
    
    print(f"{r['handler']:<40} {status:<12} {wa:<8} {em:<8} {imp:<8}")
    
    if status == "WIRED":
        wired_count += 1
    elif status == "PARTIAL":
        partial_count += 1
    elif status == "PLACEHOLDER":
        placeholder_count += 1
    else:
        missing_count += 1

print("\n=== SUMMARY ===")
print(f"Total handlers: {len(results)}")
print(f"  WIRED (complete): {wired_count}")
print(f"  PARTIAL (incomplete): {partial_count}")
print(f"  PLACEHOLDER (stub): {placeholder_count}")
print(f"  MISSING (no delivery): {missing_count}")

print("\n=== HANDLERS NEEDING WIRING ===")
for r in sorted(results, key=lambda x: x.get("status", "ERROR")):
    if r.get("status") in ("MISSING", "PLACEHOLDER", "PARTIAL"):
        print(f"  - {r['handler']:<35} [{r.get('status', 'ERROR')}]")
