"""
Helper utilities for test suite - provides base classes and utilities for writing tests.

This module provides:
1. BaseTestCase - Base test class with PostgreSQL database fixtures
2. Test data factories for creating model instances
3. Common assertions and matchers
4. Mock utilities for external services
"""

import pytest
from typing import Type, TypeVar, Generic, List, Optional
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

T = TypeVar('T')


class BaseTestCase(Generic[T]):
    """Base test case class that provides database fixtures and test utilities.

    Usage:
        class TestMyFeature(BaseTestCase):
            def test_something(self, db: Session):
                # Use db fixture for database access
                pass
    """

    @staticmethod
    def create_instance(session: Session, model_class: Type[T], **kwargs) -> T:
        """Helper to create and persist a model instance.

        Args:
            session: SQLAlchemy session
            model_class: The model class to instantiate
            **kwargs: Fields to set on the model

        Returns:
            The created and persisted model instance
        """
        instance = model_class(**kwargs)
        session.add(instance)
        session.commit()
        session.refresh(instance)
        return instance

    @staticmethod
    def create_instances(session: Session, model_class: Type[T], count: int, **kwargs) -> List[T]:
        """Helper to create multiple model instances.

        Args:
            session: SQLAlchemy session
            model_class: The model class to instantiate
            count: Number of instances to create
            **kwargs: Base fields to set on all instances

        Returns:
            List of created and persisted model instances
        """
        instances = []
        for i in range(count):
            # Allow kwargs to have format strings with {i}
            instance_kwargs = {
                k: v.format(i=i) if isinstance(v, str) and '{i}' in v else v
                for k, v in kwargs.items()
            }
            instance = model_class(**instance_kwargs)
            session.add(instance)
            instances.append(instance)

        session.commit()
        for instance in instances:
            session.refresh(instance)

        return instances

    @staticmethod
    def assert_model_exists(session: Session, model_class: Type[T], **filters) -> T:
        """Assert that a model instance exists with the given filters.

        Args:
            session: SQLAlchemy session
            model_class: The model class to query
            **filters: Keyword arguments for filtering (field=value)

        Returns:
            The found model instance

        Raises:
            AssertionError: If the model does not exist
        """
        query = session.query(model_class)
        for field_name, value in filters.items():
            if not hasattr(model_class, field_name):
                raise AttributeError(f"{model_class.__name__} has no field {field_name}")
            field = getattr(model_class, field_name)
            query = query.filter(field == value)

        instance = query.first()
        assert instance is not None, (
            f"Expected {model_class.__name__} instance with "
            f"filters {filters}, but found none"
        )
        return instance

    @staticmethod
    def assert_model_count(session: Session, model_class: Type[T], expected_count: int,
                          **filters) -> None:
        """Assert that a model has the expected count.

        Args:
            session: SQLAlchemy session
            model_class: The model class to query
            expected_count: Expected number of instances
            **filters: Optional keyword arguments for filtering

        Raises:
            AssertionError: If the count doesn't match
        """
        query = session.query(model_class)
        for field_name, value in filters.items():
            if not hasattr(model_class, field_name):
                raise AttributeError(f"{model_class.__name__} has no field {field_name}")
            field = getattr(model_class, field_name)
            query = query.filter(field == value)

        actual_count = query.count()
        assert actual_count == expected_count, (
            f"Expected {expected_count} {model_class.__name__} instances "
            f"but found {actual_count}"
        )


class TestDataFactory:
    """Factory for creating test data with sensible defaults."""

    @staticmethod
    def create_test_user(session: Session, user_email: str = "test@example.com",
                        user_name: str = "Test User", **kwargs) -> 'Users':
        """Create a test user with sensible defaults."""
        from app.models.user import Users

        user = Users(
            UserEmail=user_email,
            UserName=user_name,
            UserPassword="hashed_password",
            UserRole="Admin",
            **kwargs
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    @staticmethod
    def create_test_candidate(session: Session, candidate_name: str = "Test Candidate",
                             candidate_email: str = "candidate@example.com", **kwargs) -> 'Candidate':
        """Create a test candidate with sensible defaults."""
        from app.models.candidate import Candidate
        import uuid

        candidate = Candidate(
            id=str(uuid.uuid4()),
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            candidate_status="INTAKE",
            **kwargs
        )
        session.add(candidate)
        session.commit()
        session.refresh(candidate)
        return candidate


class MockExternalService:
    """Mock utilities for external services."""

    @staticmethod
    def mock_apollo_response(status: str = "success", **kwargs):
        """Create a mock Apollo API response."""
        return {
            "status": status,
            "data": {
                "email": "test@example.com",
                "phone": "+1234567890",
                "company": "Test Company",
                "title": "Software Engineer",
                "open_to_work": True,
                **kwargs
            }
        }

    @staticmethod
    def mock_thunder_response(session_id: str = "test-session-123", **kwargs):
        """Create a mock Thunder session response."""
        return {
            "session_id": session_id,
            "status": "active",
            "candidate_email": "test@example.com",
            **kwargs
        }


# Test marker constants for organizing tests
API_TEST = pytest.mark.api
SERVICE_TEST = pytest.mark.service
WORKFLOW_TEST = pytest.mark.workflow
INTEGRATION_TEST = pytest.mark.integration
CRITICAL_TEST = pytest.mark.critical
