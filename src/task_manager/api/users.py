"""API endpoints for user management."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session

try:
    from task_manager.constants import MAX_SQLITE_INTEGER
    from task_manager.database import get_db
    from task_manager.rate_limit import RATE_LIMIT_WRITE, limiter
    from task_manager.schemas import UserCreate, UserRead
    from task_manager.security import require_api_key
    from task_manager.services import UserService
except ModuleNotFoundError:  # pragma: no cover - compatibility for imports
    from src.task_manager.constants import MAX_SQLITE_INTEGER
    from src.task_manager.database import get_db
    from src.task_manager.rate_limit import RATE_LIMIT_WRITE, limiter
    from src.task_manager.schemas import UserCreate, UserRead
    from src.task_manager.security import require_api_key
    from src.task_manager.services import UserService

router = APIRouter(
    prefix="/api/users", tags=["users"], dependencies=[Depends(require_api_key)]
)


@router.post("", status_code=201, response_model=UserRead)
@limiter.limit(RATE_LIMIT_WRITE)
def create_user(request: Request, user_in: UserCreate, db: Session = Depends(get_db)):
    """Create a new user. Returns 400 if the email is already registered."""
    try:
        user = UserService.create_user(db, user_in.name, user_in.email)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[UserRead])
def get_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get all users with pagination."""
    users = UserService.get_all_users(db, skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int = Path(..., ge=1, le=MAX_SQLITE_INTEGER),
    db: Session = Depends(get_db),
):
    """Get a user by ID. Returns 404 if not found."""
    user = UserService.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
