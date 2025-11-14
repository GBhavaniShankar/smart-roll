# backend/app/utils/image_processing.py

from supabase import Client
import uuid
from typing import Optional

async def upload_image_to_supabase(
    db: Client, 
    file_bytes: bytes, 
    bucket_name: str, 
    file_name: Optional[str] = None
) -> str:
    """
    Uploads a file (as bytes) to a specified Supabase Storage bucket.
    Returns the public URL of the uploaded file.
    """
    if not file_name:
        file_name = f"{uuid.uuid4()}.jpg"
        
    try:
        # CORRECTION 1:
        # The syntax for 'supabase' v2 is .from_()
        # not .bucket()
        db.storage.from_(bucket_name).upload(
            path=file_name,
            file=file_bytes,
            file_options={"content-type": "image/jpeg"}
        )
        
        # CORRECTION 2:
        # This syntax also changed
        public_url = db.storage.from_(bucket_name).get_public_url(file_name)
        return public_url
        
    except Exception as e:
        print(f"Error uploading to Supabase Storage: {e}")
        # Re-raise as a specific HTTP exception in the router
        raise