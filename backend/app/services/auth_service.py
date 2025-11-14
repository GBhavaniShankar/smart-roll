from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import EmailStr
from supabase import Client

from app.config import settings
from app.models.token import TokenData

# Password hashing
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

class AuthService:
    def __init__(self, db: Client):
        self.db = db

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verifies a plain password against a hashed one."""
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Hashes a plain password."""
        return pwd_context.hash(password)

    def create_access_token(self, data: dict, expires_delta: timedelta) -> str:
        """Creates a JWT access token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + expires_delta
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM
        )
        return encoded_jwt

    def create_refresh_token(self, data: dict, expires_delta: timedelta) -> str:
        """Creates a JWT refresh token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + expires_delta
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM
        )
        return encoded_jwt

    def create_tokens(self, user_id: UUID, email: EmailStr, role: str) -> (str, str):
        """Generates both access and refresh tokens for a user."""
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = self.create_access_token(
            data={"sub": str(user_id), "email": email, "role": role, "type": "access"},
            expires_delta=access_token_expires,
        )

        refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        refresh_token = self.create_refresh_token(
            data={"sub": str(user_id), "type": "refresh"},
            expires_delta=refresh_token_expires,
        )
        return access_token, refresh_token

    def decode_token(self, token: str) -> Optional[TokenData]:
        """Decodes a JWT token and returns its payload."""
        try:
            payload = jwt.decode(
                token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            user_id: str = payload.get("sub")
            email: str = payload.get("email")
            role: str = payload.get("role")

            if user_id is None:
                return None
            return TokenData(user_id=user_id, email=email, role=role)
        except JWTError:
            return None

    async def create_supabase_user(self, email: EmailStr, password: str, full_name: str, role: str):
        """
        Creates a user in Supabase Auth (using admin privileges)
        and inserts metadata into the public 'users' table.
        """
        try:
            # 1. Create user in auth.users using the ADMIN function
            #    This is the key fix.
            auth_response = self.db.auth.admin.create_user(
                {
                    "email": email,
                    "password": password,
                    "email_confirm": True,  # We can confirm it since we are an admin
                    "user_metadata": {
                        "full_name": full_name,
                        "role": role
                    }
                }
            )

            if auth_response.user is None:
                raise Exception("Failed to create user in Supabase Auth.")

            new_user = auth_response.user
            
            # 2. Insert into public.users table
            #    This call will now succeed because it's running
            #    with the service_role key, which bypasses RLS.
            user_data = {
                "user_id": new_user.id,
                "email": new_user.email,
                "full_name": full_name,
                "role": role,
                "password_hash": self.get_password_hash(password) 
            }
            
            insert_response = self.db.table("users").insert(user_data).execute()

            if not insert_response.data:
                 raise Exception("Auth user created, but public user insert failed.")
            
            return new_user

        except Exception as e:
            print(f"Error creating user: {e}")
            # Cleanup: If we created an auth user but failed to insert
            # into public.users, we must delete the auth user to prevent
            # "ghost" users.
            if 'new_user' in locals() and new_user:
                admin_auth_client = self.db.auth.admin
                admin_auth_client.delete_user(new_user.id)
                print(f"Cleanup: Deleted auth user {new_user.id} after insert failure.")
            raise e