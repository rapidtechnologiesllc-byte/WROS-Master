#!/usr/bin/env python3
"""
Test the /hr/users/all endpoint directly
import logging
"""

import sys
sys.path.insert(0, '.')

import asyncio
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.dependencies import get_current_hr_or_admin
from app.models.user import Users
from app.schemas.user import UserResponse, AllUsersResponse

async def test_endpoint():
    """Simulate calling the endpoint"""
    db = SessionLocal()

    try:
        print("Testing endpoint logic...")

        # Simulate the endpoint code
        users = db.query(Users).all()
        print(f"[OK] Queried {len(users)} users from database")

        users_data = []
        for i, u in enumerate(users):
            try:
                user_resp = UserResponse(
                    user_id=u.UserID,
                    user_name=u.UserName or "",
                    user_email=u.UserEmail,
                    user_role=u.UserRole,
                    created_at=u.CreatedAt,
                    permission_role=u.role.name if u.role else None,
                    department_id=u.department_id,
                    department_name=u.department.name if u.department else None,
                    business_unit_id=u.business_unit_id,
                    business_unit_name=u.bu_context.business_unit.name if u.bu_context and u.bu_context.business_unit else None,
                )
                users_data.append(user_resp)
                if i == 0:
                    print(f"[OK] Successfully created UserResponse for user {u.UserEmail}")
            except Exception as e:
               logger.error(f"Error: {str(e)}", exc_info=True)
                logger.error(f"Error: {str(e)}", exc_info=True)
                print(f"[ERROR] Failed to create UserResponse for user {u.UserEmail}: {e}")
                raise

        print(f"[OK] Successfully processed all {len(users_data)} users")

        response = AllUsersResponse(
            total_users=len(users_data),
            users=users_data
        )
        print(f"[SUCCESS] Created response with {response.total_users} users")

    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error: {str(e)}", exc_info=True)
        print(f"[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

# Run the test
asyncio.run(test_endpoint())
