"""
import logging
Agent Config Service - Manages agent configuration and pipeline orchestration.

Provides CRUD operations for agent configs and auto-syncs permissions
to ensure proper access control across the system.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
import uuid

from app.models.agent_config import AgentConfig
from app.models.role_template import RoleTemplate, RoleTemplatePermission
from app.models.resource import Resource
from app.core.logging import logger

logger = logging.getLogger(__name__)

class AgentConfigService:
    """Service for managing agent configurations and permissions."""

    @staticmethod
    def get_all_agents(db: Session, tenant_id: str) -> List[AgentConfig]:
        """Get all agents for a tenant, ordered by pipeline sequence."""
        try:
            agents = db.query(AgentConfig).filter(
                and_(
                    AgentConfig.tenant_id == tenant_id,
                    AgentConfig.enabled == True
                )
            ).order_by(AgentConfig.order).all()
            return agents
        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error fetching agents for tenant {tenant_id}: {str(e)}")
            raise

    @staticmethod
    def create_agent(
        db: Session,
        name: str,
        display_name: str,
        queue_name: str,
        next_queue_name: Optional[str],
        tenant_id: str,
        description: Optional[str] = None,
        order: Optional[int] = None
    ) -> AgentConfig:
        """Create a new agent config and auto-sync permissions."""
        try:
            # Find next order if not specified
            if order is None:
                max_order = db.query(AgentConfig).filter(
                    AgentConfig.tenant_id == tenant_id
                ).order_by(AgentConfig.order.desc()).first()
                order = (max_order.order + 1) if max_order else 1

            agent = AgentConfig(
                id=uuid.uuid4(),
                name=name,
                display_name=display_name,
                description=description,
                queue_name=queue_name,
                next_queue_name=next_queue_name,
                tenant_id=tenant_id,
                enabled=True,
                order=order
            )
            db.add(agent)
            db.flush()

            # Auto-sync permissions
            AgentConfigService.auto_sync_permissions(db, agent)
            db.commit()

            logger.info(f"Created agent config: {name} (order={order})")
            return agent

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Error creating agent config {name}: {str(e)}")
            raise

    @staticmethod
    def update_agent(
        db: Session,
        agent_id: str,
        **kwargs
    ) -> AgentConfig:
        """Update an agent config and auto-sync permissions."""
        try:
            agent = db.query(AgentConfig).filter(AgentConfig.id == agent_id).first()
            if not agent:
                raise ValueError(f"Agent {agent_id} not found")

            for key, value in kwargs.items():
                if hasattr(agent, key) and key not in ['id', 'created_at']:
                    setattr(agent, key, value)

            db.flush()

            # Auto-sync permissions
            AgentConfigService.auto_sync_permissions(db, agent)
            db.commit()

            logger.info(f"Updated agent config: {agent.name}")
            return agent

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Error updating agent config {agent_id}: {str(e)}")
            raise

    @staticmethod
    def delete_agent(db: Session, agent_id: str) -> bool:
        """Delete an agent config (soft or hard delete)."""
        try:
            agent = db.query(AgentConfig).filter(AgentConfig.id == agent_id).first()
            if not agent:
                raise ValueError(f"Agent {agent_id} not found")

            db.delete(agent)
            db.commit()

            logger.info(f"Deleted agent config: {agent.name}")
            return True

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Error deleting agent config {agent_id}: {str(e)}")
            raise

    @staticmethod
    def get_pipeline_order(db: Session, tenant_id: str) -> List[Dict[str, Any]]:
        """Get agents in pipeline order (sequence they execute)."""
        try:
            agents = db.query(AgentConfig).filter(
                and_(
                    AgentConfig.tenant_id == tenant_id,
                    AgentConfig.enabled == True
                )
            ).order_by(AgentConfig.order).all()

            return [
                {
                    "id": str(agent.id),
                    "name": agent.name,
                    "display_name": agent.display_name,
                    "queue_name": agent.queue_name,
                    "next_queue_name": agent.next_queue_name,
                    "order": agent.order
                }
                for agent in agents
            ]

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error fetching pipeline order for tenant {tenant_id}: {str(e)}")
            raise

    @staticmethod
    def auto_sync_permissions(db: Session, agent_config: AgentConfig) -> None:
        """
        Auto-sync permissions when agent config is created or updated.

        Ensures that the "agents" resource exists and SuperUser roles have
        appropriate permissions for managing agents.
        """
        try:
            # 1. Check if "agents" resource exists
            resource = db.query(Resource).filter(
                and_(
                    Resource.name == "agents",
                    Resource.tenant_id == agent_config.tenant_id
                )
            ).first()

            if not resource:
                logger.warning(f"Agents resource not found for tenant {agent_config.tenant_id}")
                return

            # 2. Find all SuperUser role templates for this tenant
            super_user_roles = db.query(RoleTemplate).filter(
                and_(
                    RoleTemplate.name == "Super User",
                    RoleTemplate.tenant_id == agent_config.tenant_id
                )
            ).all()

            if not super_user_roles:
                logger.warning(f"No SuperUser roles found for tenant {agent_config.tenant_id}")
                return

            # 3. For each SuperUser role, ensure it has permissions for agents resource
            for role in super_user_roles:
                # Check if permission already exists
                existing_perm = db.query(RoleTemplatePermission).filter(
                    and_(
                        RoleTemplatePermission.role_id == role.id,
                        RoleTemplatePermission.resource_id == resource.id
                    )
                ).first()

                if not existing_perm:
                    # Create permission with full access
                    perm = RoleTemplatePermission(
                        id=uuid.uuid4(),
                        role_id=role.id,
                        resource_id=resource.id,
                        action="manage",  # Full access
                        tenant_id=agent_config.tenant_id
                    )
                    db.add(perm)
                    logger.info(f"Created agents.manage permission for role {role.name}")

            db.commit()

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Error auto-syncing permissions for agent {agent_config.name}: {str(e)}")
            raise
