
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.user import UserRegister, UserLogin, UserResponse
from services import auth_service


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: UserRegister,
    db: Session = Depends(get_db),
):
    return auth_service.register_user(payload, db)


@router.post("/login")
def login(
    payload: UserLogin,
    db: Session = Depends(get_db),
):
    return auth_service.login_user(payload, db)
