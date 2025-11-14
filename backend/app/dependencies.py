from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from supabase import Client
from typing import List

from app.database import get_db
from app.services.auth_service import AuthService
from app.models.token import TokenData
from app.models.user import UserInDB
from uuid import UUID

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Client = Depends(get_db)
) -> UserInDB:
    """
    Dependency to get the current user from a JWT token.
    Decodes the token, fetches the user from the 'users' table,
    and returns the UserInDB model.
    """
    auth_service = AuthService(db)
    token_data = auth_service.decode_token(token)
    
    if not token_data or not token_data.user_id:
        raise credentials_exception
    
    try:
        user_id_uuid = UUID(token_data.user_id)
        response = db.table("users").select("*").eq("user_id", user_id_uuid).execute()
        
        if not response.data:
            raise credentials_exception
            
        user = UserInDB(**response.data[0])
        return user
        
    except Exception:
        raise credentials_exception

# Role-Based Access Control (RBAC) Dependency
class RBAC:
    def __init__(self, roles: List[str]):
        self.roles = roles

    def __call__(self, current_user: UserInDB = Depends(get_current_user)):
        """
        Checks if the current user's role is in the allowed roles list.
        """
        if current_user.role not in self.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. User role '{current_user.role}' is not authorized.",
            )
        return current_user

# Specific role dependencies for convenience
AdminUser = Depends(RBAC(roles=["admin"]))
TeacherUser = Depends(RBAC(roles=["teacher"]))
StudentUser = Depends(RBAC(roles=["student"]))
TAUser = Depends(RBAC(roles=["ta"]))
TeacherOrAdminUser = Depends(RBAC(roles=["teacher", "admin"]))
TAOrTeacherUser = Depends(RBAC(roles=["ta", "teacher"]))