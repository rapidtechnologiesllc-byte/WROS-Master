"""
RBAC Service — permission checking, role management, and seed data.
"""
from typing import Dict, List, Optional, Set
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.rbac import Role, RoleAttribute, Permission, RolePermission
from app.models.user import Users
from app.schemas.rbac import (
    RoleCreate, PermissionCreate, RoleAttributeCreate,
    UserPermissionSummary
)
from app.core.logging import logger


# ---------------------------------------------------------------------------
# Seed Data — roles, attributes, and permissions from RBAC.md
# ---------------------------------------------------------------------------

ROLES_SEED = [
    {"name": "Super User",            "description": "Full system access across all Business Units"},
    {"name": "BU Head",               "description": "Full access within a single Business Unit"},
    {"name": "Hiring Manager",        "description": "Access to jobs they opened; interview feedback"},
    {"name": "HR Manager",            "description": "Full HR control within BU"},
    {"name": "HR Operations",         "description": "Read-only HR data; edit own candidates"},
    {"name": "HRBP",                  "description": "Manage only candidates they own"},
    {"name": "Recruitment Manager",   "description": "Full recruitment control for assigned roles"},
    {"name": "Recruitment Team Lead", "description": "Manage pipelines for assigned roles"},
    {"name": "Recruiter",             "description": "Manage candidates; cannot approve offers"},
    {"name": "Employee",              "description": "Access own data; apply for internal jobs"},
    {"name": "Consultant",            "description": "Limited employee access"},
    {"name": "Candidate",             "description": "Access open jobs; candidate portal only"},
]

# role_name → {attribute_name: bool}
ROLE_ATTRIBUTES_SEED: Dict[str, Dict[str, bool]] = {
    "Super User": {
        "global_access": True, "bu_restricted": False,
        "candidate_owner_only": False, "job_owner_only": False,
        "pipeline_control": True, "interview_control": True,
        "offer_control": True, "employee_data_access": True,
        "timesheet_access": True, "payroll_access": True,
    },
    "BU Head": {
        "global_access": False, "bu_restricted": True,
        "candidate_owner_only": False, "job_owner_only": False,
        "pipeline_control": True, "interview_control": True,
        "offer_control": True, "employee_data_access": True,
        "timesheet_access": False, "payroll_access": False,
    },
    "Hiring Manager": {
        "global_access": False, "bu_restricted": True,
        "candidate_owner_only": False, "job_owner_only": True,
        "pipeline_control": False, "interview_control": True,
        "offer_control": False, "employee_data_access": False,
        "timesheet_access": False, "payroll_access": False,
    },
    "HR Manager": {
        "global_access": False, "bu_restricted": True,
        "candidate_owner_only": False, "job_owner_only": False,
        "pipeline_control": False, "interview_control": False,
        "offer_control": False, "employee_data_access": True,
        "timesheet_access": True, "payroll_access": True,
    },
    "HR Operations": {
        "global_access": False, "bu_restricted": True,
        "candidate_owner_only": True, "job_owner_only": False,
        "pipeline_control": False, "interview_control": False,
        "offer_control": False, "employee_data_access": True,
        "timesheet_access": False, "payroll_access": False,
    },
    "HRBP": {
        "global_access": False, "bu_restricted": True,
        "candidate_owner_only": True, "job_owner_only": False,
        "pipeline_control": False, "interview_control": False,
        "offer_control": False, "employee_data_access": False,
        "timesheet_access": False, "payroll_access": False,
    },
    "Recruitment Manager": {
        "global_access": False, "bu_restricted": True,
        "candidate_owner_only": False, "job_owner_only": False,
        "pipeline_control": True, "interview_control": True,
        "offer_control": True, "employee_data_access": False,
        "timesheet_access": False, "payroll_access": False,
    },
    "Recruitment Team Lead": {
        "global_access": False, "bu_restricted": True,
        "candidate_owner_only": False, "job_owner_only": False,
        "pipeline_control": True, "interview_control": True,
        "offer_control": False, "employee_data_access": False,
        "timesheet_access": False, "payroll_access": False,
    },
    "Recruiter": {
        "global_access": False, "bu_restricted": True,
        "candidate_owner_only": False, "job_owner_only": False,
        "pipeline_control": True, "interview_control": True,
        "offer_control": False, "employee_data_access": False,
        "timesheet_access": False, "payroll_access": False,
    },
    "Employee": {
        "global_access": False, "bu_restricted": True,
        "candidate_owner_only": False, "job_owner_only": False,
        "pipeline_control": False, "interview_control": False,
        "offer_control": False, "employee_data_access": False,
        "timesheet_access": True, "payroll_access": True,
    },
    "Consultant": {
        "global_access": False, "bu_restricted": True,
        "candidate_owner_only": False, "job_owner_only": False,
        "pipeline_control": False, "interview_control": False,
        "offer_control": False, "employee_data_access": False,
        "timesheet_access": True, "payroll_access": True,
    },
    "Candidate": {
        "global_access": False, "bu_restricted": False,
        "candidate_owner_only": False, "job_owner_only": False,
        "pipeline_control": False, "interview_control": False,
        "offer_control": False, "employee_data_access": False,
        "timesheet_access": False, "payroll_access": False,
        "candidate_portal_access": True,
    },
}

PERMISSIONS_SEED = [
    {"name": "candidate.view",       "description": "View candidate profiles"},
    {"name": "candidate.create",     "description": "Create a new candidate"},
    {"name": "candidate.edit",       "description": "Edit candidate details"},
    {"name": "candidate.delete",     "description": "Delete a candidate"},
    {"name": "job.view",             "description": "View job postings"},
    {"name": "job.create",           "description": "Create a job posting"},
    {"name": "job.edit",             "description": "Edit a job posting"},
    {"name": "job.delete",           "description": "Delete a job posting"},
    {"name": "job.approve",          "description": "Approve a pending job posting"},
    {"name": "pipeline.move",        "description": "Move candidate through pipeline stages"},
    {"name": "interview.view",       "description": "View interview details"},
    {"name": "interview.manage",     "description": "Manage interviews"},
    {"name": "interview.feedback",   "description": "Submit interview feedback"},
    {"name": "offer.view",           "description": "View offer letters"},
    {"name": "offer.manage",        "description": "Create, edit, approve or reject an offer"},
    {"name": "employee.view",        "description": "View employee records"},
    {"name": "employee.edit",        "description": "Edit employee records"},
    {"name": "newsletter.manage",    "description": "Create and send newsletters"},
    {"name": "user.manage",          "description": "Create, edit, and deactivate users"},
    {"name": "rbac.manage",          "description": "Manage RBAC roles and permissions"},
    {"name":"newsletter.view",       "description":"View newsletters"},
    {"name": "thunder.test",         "description": "Access the internal Test Thunder QA chat harness"},
    {"name": "tenant.ai_config",     "description": "View and update Thunder's per-tenant name and persona (S-011/HRMS-0411)"},
    {"name": "template.manage",      "description": "Activate a message template version (S-014/HRMS-0414)"},
    {"name": "offer.readiness_check", "description": "View a candidate's offer readiness gate before generating an offer (S-053/HRMS-0453) -- deliberately narrower than offer.manage/offer.view; excludes Recruiter per that story's own explicit AC/TC, unlike the two broader offer permissions which (a pre-existing inconsistency, not introduced by this story) currently include Recruiter despite its own role description/offer_control=False attribute saying otherwise."},
]

# role_name → list of permission names it should have
ROLE_PERMISSIONS_SEED: Dict[str, List[str]] = {
    "Super User": [p["name"] for p in PERMISSIONS_SEED],   # all permissions
    "BU Head": [
        "candidate.view", "candidate.edit", "job.view", "job.create", "job.edit",
        "job.approve", "pipeline.move", "interview.feedback",
        "offer.manage", "offer.readiness_check", "employee.view", "employee.edit","document.verify",
        "interview.manage","interview.view","newsletter.view","document.view","history.create","rbac.manage",
    ],
    "Hiring Manager": [
        "candidate.view", "job.view", "interview.feedback","offer.manage","offer.view","offer.readiness_check","candidate.edit",
        "interview.manage","interview.view","newsletter.view","document.view","document.verify","history.create"
    ],
    "HR Manager": [
        "candidate.view", "candidate.edit", "employee.view", "employee.edit",
        "user.manage", "newsletter.manage","newsletter.view","document.view","document.verify",
        "history.create","interview.feedback","offer.manage","offer.view","offer.readiness_check","interview.manage","interview.view"

    ],
    "HR Operations": [
        "candidate.view", "candidate.edit", "employee.view",
        "newsletter.view","document.view","document.verify","history.create",
        "interview.feedback","offer.manage","offer.view","offer.readiness_check","interview.manage","interview.view"
    ],
    "HRBP": [
        "candidate.view", "candidate.edit","newsletter.view",
        "document.view","document.verify","history.create","rbac.manage",
        "interview.feedback","offer.manage","offer.view","offer.readiness_check","interview.manage","interview.view"
    ],
    "Recruitment Manager": [
        "candidate.view", "candidate.create", "candidate.edit",
        "job.view", "job.create", "job.edit",
        "pipeline.move", "interview.feedback",
        "offer.manage", "offer.view", "offer.readiness_check",
        "interview.manage","interview.view","newsletter.view",
        "document.view","document.verify","history.create"
    ],
    "Recruitment Team Lead": [
        "candidate.view", "candidate.create", "candidate.edit",
        "job.view", "pipeline.move", "interview.feedback",
        "offer.manage", "offer.view", "offer.readiness_check",
        "interview.manage","interview.view","newsletter.view","document.view",
        "document.verify","history.create"
    ],
    "Recruiter": [
        "candidate.view", "candidate.create", "candidate.edit",
        "job.view", "pipeline.move", "interview.feedback",
        "offer.manage", "offer.view",
        "interview.manage","interview.view","newsletter.view","document.view",
        "document.verify","history.create"
    ],
    "Employee": [
        "job.view","newsletter.view","candidate.view","interview.view",
        "interview.feedback","document.view",
    ],
    "Consultant": [
        "job.view","newsletter.view","document.view","history.create",
        "interview.feedback"
    ],
    "Candidate": ["history.create"],
}


# ---------------------------------------------------------------------------
# RBAC Service
# ---------------------------------------------------------------------------

class RBACService:

    # ------------------------------------------------------------------
    # Seed
    # ------------------------------------------------------------------

    @staticmethod
    def seed_roles_and_permissions(db: Session) -> None:
        """
        Idempotently seed all 12 roles, their attributes, all permissions,
        and the role-permission mappings into the database.
        Called once at application startup.
        """
        try:
            # 1. Seed permissions
            perm_map: Dict[str, Permission] = {}
            for p_data in PERMISSIONS_SEED:
                existing = db.query(Permission).filter(Permission.name == p_data["name"]).first()
                if not existing:
                    perm = Permission(name=p_data["name"], description=p_data["description"])
                    db.add(perm)
                    db.flush()
                    perm_map[perm.name] = perm
                else:
                    perm_map[existing.name] = existing

            # 2. Seed roles + attributes + role-permissions
            for r_data in ROLES_SEED:
                role = db.query(Role).filter(Role.name == r_data["name"]).first()
                if not role:
                    role = Role(name=r_data["name"], description=r_data["description"])
                    db.add(role)
                    db.flush()

                # Seed attributes for this role
                attrs = ROLE_ATTRIBUTES_SEED.get(r_data["name"], {})
                for attr_name, attr_value in attrs.items():
                    existing_attr = (
                        db.query(RoleAttribute)
                        .filter(RoleAttribute.role_id == role.id, RoleAttribute.attribute_name == attr_name)
                        .first()
                    )
                    if not existing_attr:
                        db.add(RoleAttribute(role_id=role.id, attribute_name=attr_name, attribute_value=attr_value))

                # Seed role-permissions
                perm_names = ROLE_PERMISSIONS_SEED.get(r_data["name"], [])
                for perm_name in perm_names:
                    perm = perm_map.get(perm_name)
                    if perm:
                        existing_rp = (
                            db.query(RolePermission)
                            .filter(RolePermission.role_id == role.id, RolePermission.permission_id == perm.id)
                            .first()
                        )
                        if not existing_rp:
                            db.add(RolePermission(role_id=role.id, permission_id=perm.id))

            db.commit()
            logger.info("[OK] RBAC roles, attributes, and permissions seeded")

        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to seed RBAC data: {exc}")
            raise

    # ------------------------------------------------------------------
    # Roles
    # ------------------------------------------------------------------

    @staticmethod
    def list_roles(db: Session) -> List[Role]:
        return db.query(Role).order_by(Role.id).all()

    @staticmethod
    def get_role(db: Session, role_id: int) -> Optional[Role]:
        return db.query(Role).filter(Role.id == role_id).first()

    @staticmethod
    def get_role_or_404(db: Session, role_id: int) -> Role:
        role = RBACService.get_role(db, role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Role {role_id} not found")
        return role

    @staticmethod
    def create_role(db: Session, data: RoleCreate) -> Role:
        if db.query(Role).filter(Role.name == data.name).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Role '{data.name}' already exists")
        role = Role(name=data.name, description=data.description)
        db.add(role)
        db.commit()
        db.refresh(role)
        return role

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------

    @staticmethod
    def list_permissions(db: Session) -> List[Permission]:
        return db.query(Permission).order_by(Permission.id).all()

    @staticmethod
    def get_permission_or_404(db: Session, perm_id: int) -> Permission:
        perm = db.query(Permission).filter(Permission.id == perm_id).first()
        if not perm:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Permission {perm_id} not found")
        return perm

    @staticmethod
    def create_permission(db: Session, data: PermissionCreate) -> Permission:
        if db.query(Permission).filter(Permission.name == data.name).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Permission '{data.name}' already exists")
        perm = Permission(name=data.name, description=data.description)
        db.add(perm)
        db.commit()
        db.refresh(perm)
        return perm

    # ------------------------------------------------------------------
    # Role ↔ Permission management
    # ------------------------------------------------------------------

    @staticmethod
    def assign_permission_to_role(db: Session, role_id: int, permission_id: int) -> RolePermission:
        RBACService.get_role_or_404(db, role_id)
        RBACService.get_permission_or_404(db, permission_id)
        existing = (
            db.query(RolePermission)
            .filter(RolePermission.role_id == role_id, RolePermission.permission_id == permission_id)
            .first()
        )
        if existing:
            return existing
        rp = RolePermission(role_id=role_id, permission_id=permission_id)
        db.add(rp)
        db.commit()
        db.refresh(rp)
        return rp

    @staticmethod
    def remove_permission_from_role(db: Session, role_id: int, permission_id: int) -> None:
        rp = (
            db.query(RolePermission)
            .filter(RolePermission.role_id == role_id, RolePermission.permission_id == permission_id)
            .first()
        )
        if not rp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not assigned to this role")
        db.delete(rp)
        db.commit()

    # ------------------------------------------------------------------
    # Assign role to user
    # ------------------------------------------------------------------

    @staticmethod
    def assign_role_to_user(db: Session, user_id: str, role_id: int) -> Users:
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
        RBACService.get_role_or_404(db, role_id)
        user.role_id = role_id
        db.commit()
        db.refresh(user)
        logger.info(f"Assigned role {role_id} to user {user_id}")
        return user

    # ------------------------------------------------------------------
    # Permission / Attribute resolution
    # ------------------------------------------------------------------

    @staticmethod
    def get_user_role(db: Session, user_id: str) -> Optional[Role]:
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user or not user.role_id:
            return None
        return db.query(Role).filter(Role.id == user.role_id).first()

    @staticmethod
    def get_user_permissions(db: Session, user_id: str) -> Set[str]:
        role = RBACService.get_user_role(db, user_id)
        if not role:
            return set()
        return {
            rp.permission.name
            for rp in role.role_permissions
            if rp.permission
        }

    @staticmethod
    def get_user_attributes(db: Session, user_id: str) -> Dict[str, bool]:
        role = RBACService.get_user_role(db, user_id)
        if not role:
            return {}
        return {attr.attribute_name: attr.attribute_value for attr in role.attributes}

    @staticmethod
    def has_permission(db: Session, user_id: str, permission: str) -> bool:
        return permission in RBACService.get_user_permissions(db, user_id)

    @staticmethod
    def has_attribute(db: Session, user_id: str, attribute: str, expected: bool = True) -> bool:
        attrs = RBACService.get_user_attributes(db, user_id)
        return attrs.get(attribute, False) == expected

    @staticmethod
    def get_user_permission_summary(db: Session, user_id: str) -> UserPermissionSummary:
        role = RBACService.get_user_role(db, user_id)
        permissions = list(RBACService.get_user_permissions(db, user_id))
        attributes = RBACService.get_user_attributes(db, user_id)
        return UserPermissionSummary(
            user_id=user_id,
            role_id=role.id if role else None,
            role_name=role.name if role else None,
            permissions=sorted(permissions),
            attributes=attributes,
        )
