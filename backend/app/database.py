from supabase import create_client, Client
from app.config import settings

def get_supabase_client() -> Client:
    """
    Creates and returns a Supabase client configured with the service role key.
    This client has admin privileges and bypasses RLS.
    """
    try:
        supabase: Client = create_client(
            settings.SUPABASE_URL, 
            settings.SUPABASE_SERVICE_ROLE_KEY
        )
        return supabase
    except Exception as e:
        # In a real app, you'd have more robust logging here
        print(f"Error creating Supabase client: {e}")
        raise

# You can also create a request-scoped client if needed,
# but for backend services, the service client is common.

# Dependency for routers
def get_db():
    """FastAPI dependency to get a Supabase client instance."""
    return get_supabase_client()