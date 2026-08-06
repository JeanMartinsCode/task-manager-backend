"""
Test suite for Task 1.4: Create Core Models (User, Task, Notification).

This module validates that SQLAlchemy models are correctly defined with proper
fields, types, constraints, and relationships.
"""

from task_manager.database import Base
from task_manager.models import Notification, Task, User


class TestModelImports:
    """Test 1: Verify models can be imported and are defined."""

    def test_models_can_be_imported(self) -> None:
        """Verify that all core models exist and are importable."""
        # Assert that each model class exists and is not None
        assert User is not None, "User model should be importable"
        assert Task is not None, "Task model should be importable"
        assert Notification is not None, "Notification model should be importable"

        # Assert that each model inherits from Base (SQLAlchemy declarative base)
        assert issubclass(User, Base), "User should inherit from Base"
        assert issubclass(Task, Base), "Task should inherit from Base"
        assert issubclass(Notification, Base), "Notification should inherit from Base"


class TestUserModel:
    """Test 2: Verify User model has correct fields and types."""

    def test_user_model_has_required_fields(self) -> None:
        """Verify User model has all required fields: id, name, email, created_at."""
        # Check that User has __table__ attribute (SQLAlchemy mapped table)
        assert hasattr(User, "__table__"), "User should be a SQLAlchemy model"

        # Get all column names from the User table
        column_names = [col.name for col in User.__table__.columns]

        # Assert each required field exists
        assert "id" in column_names, "User should have 'id' field"
        assert "name" in column_names, "User should have 'name' field"
        assert "email" in column_names, "User should have 'email' field"
        assert "created_at" in column_names, "User should have 'created_at' field"

    def test_user_model_field_types(self) -> None:
        """Verify User model fields have correct types."""
        # Get columns by name for type checking
        columns = {col.name: col for col in User.__table__.columns}

        # Assert id is Integer and primary key
        assert columns["id"].type.__class__.__name__ in (
            "Integer",
            "BIGINT",
        ), "id should be Integer type"
        assert columns["id"].primary_key, "id should be primary key"

        # Assert name is String
        assert columns["name"].type.__class__.__name__ in (
            "String",
            "VARCHAR",
        ), "name should be String type"
        assert not columns["name"].nullable, "name should be NOT NULL"

        # Assert email is String
        assert columns["email"].type.__class__.__name__ in (
            "String",
            "VARCHAR",
        ), "email should be String type"
        assert not columns["email"].nullable, "email should be NOT NULL"

        # Assert created_at is DateTime
        assert columns["created_at"].type.__class__.__name__ in (
            "DateTime",
            "DATETIME",
        ), "created_at should be DateTime type"


class TestTaskModel:
    """Test 3: Verify Task model has correct fields, types, and enums."""

    def test_task_model_has_required_fields(self) -> None:
        """Verify Task model has all required fields."""
        # Check that Task has __table__ attribute
        assert hasattr(Task, "__table__"), "Task should be a SQLAlchemy model"

        # Get all column names
        column_names = [col.name for col in Task.__table__.columns]

        # Assert each required field exists
        assert "id" in column_names, "Task should have 'id' field"
        assert "title" in column_names, "Task should have 'title' field"
        assert "description" in column_names, "Task should have 'description' field"
        assert "priority" in column_names, "Task should have 'priority' field"
        assert "status" in column_names, "Task should have 'status' field"
        assert "deadline" in column_names, "Task should have 'deadline' field"
        assert "assigned_to" in column_names, "Task should have 'assigned_to' field (FK)"
        assert "created_at" in column_names, "Task should have 'created_at' field"
        assert "updated_at" in column_names, "Task should have 'updated_at' field"

    def test_task_model_priority_and_status_are_enums(self) -> None:
        """Verify Task model priority and status fields use Enum type."""
        columns = {col.name: col for col in Task.__table__.columns}

        # Assert priority is Enum type
        assert columns["priority"].type.__class__.__name__ in (
            "Enum",
            "ENUM",
            "VARCHAR",
        ), "priority should be Enum or Enum-like type"

        # Assert status is Enum type
        assert columns["status"].type.__class__.__name__ in (
            "Enum",
            "ENUM",
            "VARCHAR",
        ), "status should be Enum or Enum-like type"

    def test_task_model_assigned_to_is_foreign_key(self) -> None:
        """Verify Task model assigned_to is a foreign key pointing to User."""
        columns = {col.name: col for col in Task.__table__.columns}

        # Assert assigned_to has a foreign key constraint
        assert (
            len(columns["assigned_to"].foreign_keys) > 0
        ), "assigned_to should have foreign key constraint"

        # Get the foreign key
        fk = list(columns["assigned_to"].foreign_keys)[0]

        # Assert it points to user.id
        assert (
            "user" in fk.column.table.name.lower()
        ), "assigned_to foreign key should reference users table"
        assert fk.column.name == "id", "assigned_to should reference user id"


class TestNotificationModel:
    """Test 4: Verify Notification model has correct fields and FK."""

    def test_notification_model_has_required_fields(self) -> None:
        """Verify Notification model has all required fields."""
        # Check that Notification has __table__ attribute
        assert hasattr(
            Notification, "__table__"
        ), "Notification should be a SQLAlchemy model"

        # Get all column names
        column_names = [col.name for col in Notification.__table__.columns]

        # Assert each required field exists
        assert "id" in column_names, "Notification should have 'id' field"
        assert "task_id" in column_names, "Notification should have 'task_id' field (FK)"
        assert (
            "notification_type" in column_names or "type" in column_names
        ), "Notification should have 'type' field (notification_type or type)"
        assert "message" in column_names, "Notification should have 'message' field"
        assert "created_at" in column_names, "Notification should have 'created_at' field"

    def test_notification_task_id_is_foreign_key(self) -> None:
        """Verify Notification model task_id is a foreign key pointing to Task."""
        columns = {col.name: col for col in Notification.__table__.columns}

        # Assert task_id has a foreign key constraint
        assert (
            len(columns["task_id"].foreign_keys) > 0
        ), "task_id should have foreign key constraint"

        # Get the foreign key
        fk = list(columns["task_id"].foreign_keys)[0]

        # Assert it points to task.id
        assert (
            "task" in fk.column.table.name.lower()
        ), "task_id foreign key should reference tasks table"
        assert fk.column.name == "id", "task_id should reference task id"

        # Assert task_id is NOT NULL
        assert (
            not columns["task_id"].nullable
        ), "task_id should be NOT NULL (required)"


class TestModelRelationships:
    """Test 5: Verify relationships work correctly."""

    def test_user_has_tasks_relationship(self) -> None:
        """Verify User model has a relationship to Task."""
        # Assert that User has a 'tasks' relationship attribute
        assert hasattr(
            User, "tasks"
        ), "User should have 'tasks' relationship attribute"

        # Get the relationship property
        tasks_relation = getattr(User, "tasks")

        # Assert it's a relationship (InstrumentedAttribute from SQLAlchemy)
        assert (
            hasattr(tasks_relation, "property")
            and tasks_relation.property.__class__.__name__ in (
                "RelationshipProperty",
                "_RelationshipDeclared",
            )
        ), "tasks should be a SQLAlchemy relationship"

    def test_task_has_notifications_relationship(self) -> None:
        """Verify Task model has a relationship to Notification."""
        # Assert that Task has a 'notifications' relationship attribute
        assert hasattr(
            Task, "notifications"
        ), "Task should have 'notifications' relationship attribute"

        # Get the relationship property
        notifications_relation = getattr(Task, "notifications")

        # Assert it's a relationship
        assert (
            hasattr(notifications_relation, "property")
            and notifications_relation.property.__class__.__name__ in (
                "RelationshipProperty",
                "_RelationshipDeclared",
            )
        ), "notifications should be a SQLAlchemy relationship"

    def test_task_has_assigned_user_relationship(self) -> None:
        """Verify Task model has a relationship to User (assigned_user)."""
        # Assert that Task has a relationship to User (usually named 'assigned_user')
        has_user_relation = (
            hasattr(Task, "assigned_user")
            or hasattr(Task, "user")
            or hasattr(Task, "owner")
        )
        assert (
            has_user_relation
        ), "Task should have a relationship to User (assigned_user, user, or owner)"

        # Get the relationship property (try different names)
        user_relation = (
            getattr(Task, "assigned_user")
            if hasattr(Task, "assigned_user")
            else (
                getattr(Task, "user")
                if hasattr(Task, "user")
                else getattr(Task, "owner")
            )
        )

        # Assert it's a relationship
        assert (
            hasattr(user_relation, "property")
            and user_relation.property.__class__.__name__ in (
                "RelationshipProperty",
                "_RelationshipDeclared",
            )
        ), "User relationship should be a SQLAlchemy relationship"

    def test_notification_has_task_relationship(self) -> None:
        """Verify Notification model has a relationship to Task."""
        # Assert that Notification has a 'task' relationship attribute
        assert hasattr(
            Notification, "task"
        ), "Notification should have 'task' relationship attribute"

        # Get the relationship property
        task_relation = getattr(Notification, "task")

        # Assert it's a relationship
        assert (
            hasattr(task_relation, "property")
            and task_relation.property.__class__.__name__ in (
                "RelationshipProperty",
                "_RelationshipDeclared",
            )
        ), "task should be a SQLAlchemy relationship"
