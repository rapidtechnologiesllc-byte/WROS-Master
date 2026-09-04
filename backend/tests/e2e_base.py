"""
End-to-End test base class and utilities.

E2E tests validate complete workflows across multiple components:
- API endpoints
- Database operations
- Service layer logic
- Business logic flows

Usage:
    class TestCompleteWorkflow(E2ETestCase):
        def test_candidate_to_hire_workflow(self, client: TestClient, db: Session):
            # E2E test that validates complete workflow
            pass
"""

import json
from typing import Dict, Any, Optional
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class E2ETestCase:
    """Base class for end-to-end tests.

    E2E tests should:
    1. Use a real test client (not mocked)
    2. Use real database operations
    3. Test complete workflows, not individual functions
    4. Verify state changes at each step
    5. Assert on final outcomes
    """

    def make_request(self, client: TestClient, method: str, path: str,
                    json: Optional[Dict[str, Any]] = None,
                    headers: Optional[Dict[str, str]] = None,
                    expect_status: int = 200) -> Dict[str, Any]:
        """Make an HTTP request and verify status code.

        Args:
            client: FastAPI TestClient
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            path: API path
            json: Optional JSON payload
            headers: Optional headers
            expect_status: Expected HTTP status code

        Returns:
            Parsed JSON response

        Raises:
            AssertionError: If status code doesn't match expected
        """
        response = client.request(method, path, json=json, headers=headers)

        assert response.status_code == expect_status, (
            f"Expected status {expect_status} but got {response.status_code}.\n"
            f"Response: {response.text}"
        )

        if response.text:
            return response.json()
        return {}

    def get(self, client: TestClient, path: str, expect_status: int = 200,
           headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Convenience method for GET requests."""
        return self.make_request(client, "GET", path, expect_status=expect_status, headers=headers)

    def post(self, client: TestClient, path: str, json: Dict[str, Any] = None,
            expect_status: int = 200, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Convenience method for POST requests."""
        return self.make_request(client, "POST", path, json=json,
                               expect_status=expect_status, headers=headers)

    def put(self, client: TestClient, path: str, json: Dict[str, Any] = None,
           expect_status: int = 200, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Convenience method for PUT requests."""
        return self.make_request(client, "PUT", path, json=json,
                               expect_status=expect_status, headers=headers)

    def delete(self, client: TestClient, path: str, expect_status: int = 200,
              headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Convenience method for DELETE requests."""
        return self.make_request(client, "DELETE", path, expect_status=expect_status, headers=headers)

    def assert_response_field(self, response: Dict[str, Any], field_path: str, value: Any):
        """Assert that a response has a specific field with a specific value.

        Supports nested paths like "data.user.email" format.

        Args:
            response: JSON response dict
            field_path: Dot-separated path to field
            value: Expected value
        """
        if response is None:
            raise AssertionError(f"Response is None, cannot access field {field_path}")

        current = response
        path_parts = field_path.split('.')

        for part in path_parts[:-1]:
            if current is None:
                raise AssertionError(
                    f"Cannot access field {part} in {field_path} - parent is None"
                )
            if not isinstance(current, dict):
                raise AssertionError(
                    f"Cannot access field {part} in {field_path} - "
                    f"parent is {type(current).__name__}"
                )
            if part not in current:
                raise AssertionError(f"Field {part} not found in {field_path}")
            current = current[part]

        final_field = path_parts[-1]
        if current is None:
            raise AssertionError(
                f"Cannot access field {final_field} in {field_path} - parent is None"
            )
        if not isinstance(current, dict):
            raise AssertionError(
                f"Cannot access field {final_field} in {field_path} - "
                f"parent is {type(current).__name__}"
            )
        if final_field not in current:
            raise AssertionError(f"Field {final_field} not found in {field_path}")

        actual_value = current[final_field]

        assert actual_value == value, (
            f"Expected {field_path}={value} but got {actual_value}"
        )

    def assert_response_has_fields(self, response: Dict[str, Any], *fields):
        """Assert that response contains all specified fields.

        Args:
            response: JSON response dict
            *fields: Field names to check
        """
        for field in fields:
            assert field in response, f"Expected field '{field}' in response"

    def assert_response_contains(self, response: Dict[str, Any], substring: str):
        """Assert that response contains a substring (useful for error messages)."""
        response_str = json.dumps(response)
        assert substring in response_str, (
            f"Expected '{substring}' in response:\n{response_str}"
        )


class WorkflowTestScenario:
    """Helper class for defining multi-step workflow test scenarios."""

    def __init__(self, name: str):
        """Initialize workflow scenario.

        Args:
            name: Name of the workflow scenario
        """
        self.name = name
        self.steps = []

    def add_step(self, name: str, action, assertions=None):
        """Add a step to the workflow.

        Args:
            name: Step name for logging
            action: Callable that performs the step
            assertions: Optional list of assertions to validate after step
        """
        self.steps.append({
            'name': name,
            'action': action,
            'assertions': assertions or []
        })

    def execute(self, test_case: E2ETestCase) -> Dict[str, Any]:
        """Execute the workflow scenario.

        Args:
            test_case: E2ETestCase instance with test client

        Returns:
            Context dict with results from each step
        """
        context = {}
        print(f"\nExecuting workflow: {self.name}")

        for i, step in enumerate(self.steps, 1):
            print(f"  Step {i}: {step['name']}")
            result = step['action'](context)
            context[step['name']] = result

            for assertion in step['assertions']:
                assertion(result, context)

        return context
