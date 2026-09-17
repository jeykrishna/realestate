from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import (
    UserCreate, UserUpdate, UserOut,
    UserListResponse, UserCreateResponse, UserDeleteResponse,
)
from app.dependencies.auth import require_admin
from app.utils.id_gen import make_id

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=UserListResponse)
def list_users(db: Session = Depends(get_db), _: object = Depends(require_admin)):
    users = db.query(User).all()
    return UserListResponse(users=[UserOut.model_validate(u) for u in users])


@router.post("", response_model=UserCreateResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        id=make_id("usr"),
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        role=payload.role,
        property_ids=payload.property_ids,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserCreateResponse(user=UserOut.model_validate(user))


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.delete("/{user_id}", response_model=UserDeleteResponse)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role == UserRole.admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete admin accounts")

    db.delete(user)
    db.commit()
    return UserDeleteResponse(success=True)
