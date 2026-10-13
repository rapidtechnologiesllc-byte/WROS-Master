#!/usr/bin/env python3
"""
Automated refactoring script to replace hardcoded tenant_id=1 with RequestContext.tenant_id
Processes all 39 identified files systematically.
"""

import re
import sys
from pathlib import Path

files_to_refactor = [
    'backend/app/api/v1/endpoints/agent_standups_dashboard.py',
    'backend/app/api/v1/endpoints/agent_state_dashboard.py',
    'backend/app/api/v1/endpoints/agents.py',
    'backend/app/api/v1/endpoints/business_metrics.py',
    'backend/app/api/v1/endpoints/candidate_ranking.py',
    'backend/app/api/v1/endpoints/candidates.py',
    'backend/app/api/v1/endpoints/candidates/create_queue_first.py',
    'backend/app/api/v1/endpoints/config.py',
    'backend/app/api/v1/endpoints/navigation.py',
    'backend/app/api/v1/endpoints/role_based_dashboard.py',
    'backend/app/api/v1/endpoints/users.py',
    'backend/app/core/permission_enforcement.py',
    'backend/app/core/revenue_visibility_scope.py',
    'backend/app/main.py',
    'backend/app/models/role_template.py',
    'backend/app/schemas/candidate_rejection.py',
    'backend/app/seeds/init_resources.py',
    'backend/app/services/activity_timeline_service.py',
    'backend/app/services/candidate_isolation_service.py',
    'backend/app/services/candidate_memory_service.py',
    'backend/app/services/candidate_query_helpers.py',
    'backend/app/services/candidate_rejection_service.py',
    'backend/app/services/employee_conversion_service.py',
    'backend/app/services/error_log_service.py',
    'backend/app/services/flash_service.py',
    'backend/app/services/follow_up_scheduler_service.py',
    'backend/app/services/message_handlers/candidate_creation_handler.py',
    'backend/app/services/message_queue_service.py',
    'backend/app/services/no_response_detection_service.py',
    'backend/app/services/organization_service.py',
    'backend/app/services/permission_helper.py',
    'backend/app/services/preference_capture_service.py',
    'backend/app/services/progressive_upload_service_production.py',
    'backend/app/services/project_allocation_service.py',
    'backend/app/services/referral_access_control.py',
    'backend/app/services/revenue_target_service.py',
    'backend/app/services/role_template_permission_service.py',
    'backend/app/services/role_template_seed.py',
    'backend/app/services/service_helpers.py',
]

def refactor_file(filepath):
    """Refactor a single file to use RequestContext instead of hardcoded tenant_id=1"""
    path = Path(filepath)

    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"  ERROR reading {filepath}: {e}")
        return False

    original_content = content

    # Pattern 1: Replace getattr(current_user, 'tenant_id', 1) or 1 with context.tenant_id
    content = re.sub(
        r"getattr\(current_user,\s*['\"]tenant_id['\"]\s*,\s*1\)\s*or\s*1",
        "context.tenant_id",
        content
    )

    # Pattern 2: Replace tenant_id = 1 with tenant_id = context.tenant_id (in dynamic context)
    # But be careful not to replace in comments or initial assignments
    content = re.sub(
        r"(\s+)tenant_id\s*=\s*1(?=\s*#|$|\n)",
        r"\1tenant_id = context.tenant_id  # Derived from request context",
        content,
        flags=re.MULTILINE
    )

    # Pattern 3: Replace Candidate.tenant_id == 1 with Candidate.tenant_id == context.tenant_id
    content = re.sub(
        r"\.tenant_id\s*==\s*1(?=[,\)]|\s+and|\s+or|\s+#)",
        ".tenant_id == context.tenant_id",
        content
    )

    # Pattern 4: Replace tenant_id == 1 in conditions
    content = re.sub(
        r"(?<![=!<>])([a-zA-Z_]\w*\.)?tenant_id\s*==\s*1",
        r"\1tenant_id == context.tenant_id",
        content
    )

    # Pattern 5: Add RequestContext import if file uses "Depends" (FastAPI endpoint)
    has_depends = "Depends(" in content
    has_request_context_import = "from app.core.request_context import" in content

    if has_depends and not has_request_context_import and "context.tenant_id" in content:
        # Find the import section and add RequestContext import
        import_pattern = r"(from app\.core\.dependencies import[^\n]+)"
        if re.search(import_pattern, content):
            content = re.sub(
                import_pattern,
                r"\1\nfrom app.core.request_context import RequestContext, get_request_context",
                content
            )

    # Only write if changes were made
    if content != original_content:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  [FIXED] {filepath}")
            return True
        except Exception as e:
            print(f"  ERROR writing {filepath}: {e}")
            return False
    else:
        print(f"  [SKIP] No patterns matched in {filepath}")
        return False

def main():
    print(f"Refactoring {len(files_to_refactor)} files to eliminate hardcoded tenant_id=1\n")

    fixed_count = 0
    for filepath in files_to_refactor:
        if refactor_file(filepath):
            fixed_count += 1

    print(f"\nRefactoring complete: {fixed_count}/{len(files_to_refactor)} files updated")
    return 0

if __name__ == '__main__':
    sys.exit(main())
