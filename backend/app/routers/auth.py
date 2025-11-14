from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from supabase import Client, AuthApiError
from postgrest import APIError  # <-- ADD THIS IMPORT
from uuid import UUID

from app.database import get_db
from app.services.auth_service import AuthService
from app.models.token import Token, RefreshRequest, AccessTokenResponse, TokenData
from app.dependencies import oauth2_scheme, credentials_exception

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)

@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Client = Depends(get_db)
):
    """
    Login endpoint. Uses Supabase Auth to verify credentials
    and then generates our own custom JWTs (access and refresh).
    """
    try:
        # Step 1: Validate credentials with Supabase Auth
        auth_response = db.auth.sign_in_with_password({
            "email": form_data.username,
            "password": form_data.password
        })
        
        user = auth_response.user
        if not user:
            # This should be caught by AuthApiError, but as a fallback
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )
        
        # --- [NEW ERROR HANDLING] ---
        # Step 2: Get user role, with specific error handling for missing profiles
        user_role = None
        try:
            user_role = user.user_metadata.get("role")
            if not user_role:
                # Fallback to public table
                user_profile_response = db.table("users").select("role").eq("user_id", user.id).single().execute()
                # .single() will raise APIError if 0 rows, which is caught below
                user_role = user_profile_response.data['role']
        
        except APIError as e:
            if e.code == "PGRST116": # "0 rows found"
                # This is the error you are seeing.
                # We are now catching it and sending a clean message.
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Cedentials",
                )
            else:
                # Re-raise other database errors
                raise e

        # Step 3: User is valid, profile is found. Create tokens.
        auth_service = AuthService(db)
        access_token, refresh_token = auth_service.create_tokens(
            user_id=user.id,
            email=user.email,
            role=user_role
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_role": user_role
        }

    except AuthApiError:
        # This catches "Invalid login credentials" from Supabase Auth
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    except HTTPException as e:
        # Re-raise the specific HTTPExceptions we threw (like the profile one)
        raise e
    except Exception as e:
        # Catch-all for other unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_access_token(
    refresh_request: RefreshRequest,
    db: Client = Depends(get_db)
):
    """
    Refreshes an access token using a valid refresh token.
    """
    auth_service = AuthService(db)
    token_data = auth_service.decode_token(refresh_request.refresh_token)
    
    if not token_data or not token_data.user_id or token_data.type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    try:
        user_resp = db.table("users").select("email, role").eq("user_id", token_data.user_id).single().execute()
        if not user_resp.data:
            raise credentials_exception
        
        user_data = user_resp.data
        
        new_access_token = auth_service.create_access_token(
            data={"sub": token_data.user_id, "email": user_data['email'], "role": user_data['role'], "type": "access"},
            expires_delta=auth_service.access_token_expires
        )
        
        return AccessTokenResponse(access_token=new_access_token)
        
    except Exception:
        raise credentials_exception


@router.post("/logout")
async def logout_user(token: str = Depends(oauth2_scheme)):
    """
    Client-side logout. In a stateless JWT system, the server can't
    do much. The client is responsible for deleting the token.
    """
    return {"message": "Logout successful. Client must delete tokens."}