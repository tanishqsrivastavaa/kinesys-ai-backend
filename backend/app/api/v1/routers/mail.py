# from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Query
# from sqlmodel.ext.asyncio.session import AsyncSession

# # Imports from your project structure
# from app.api.deps import get_db, get_current_user
# from app.services.r2_service import R2Service
# from app.controllers.r2 import genarate_upload_url
# from app.controllers.mail import initialize_mail, process_mail_task, get_all_mails, get_mail_by_id
# from app.models.user_model import User
# from uuid import UUID

# router = APIRouter()

# # Endpoint 1: The Handshake
# @router.post("/generate_upload_url")
# async def genreate_upload_url(current_user = Depends(get_current_user)):
#     return await genarate_upload_url(user_id=current_user.id)

# # Endpoint 2: The Trigger
# @router.post("/process")
# async def process_mail(
#     file_key: str,
#     background_tasks: BackgroundTasks,
#     db: AsyncSession = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     new_mail = await initialize_mail(user_id=current_user.id, file_key=file_key, db=db)
    
#     background_tasks.add_task(
#         process_mail_task, 
#         new_mail.id, 
#         file_key, 
#         db
#     )
    
#     return new_mail

# # # Endpoint 3: The History (With Dynamic Image Links)
# @router.get("/")
# async def get_mails(
#     limit: int = Query(default=20, ge=1, le=100),
#     offset: int = Query(default=0, ge=0),
#     db: AsyncSession = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     return await get_all_mails(
#         user_id=current_user.id,
#         db=db,
#         limit=limit,
#         offset=offset
#     )


# # Endpoint 4: Get specific mail by ID
# @router.get("/{mail_id}")
# async def get_mail(
#     mail_id: UUID,
#     db: AsyncSession = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     mail = await get_mail_by_id(mail_id=mail_id, user_id=current_user.id, db=db)
    
#     if not mail:
#         raise HTTPException(status_code=404, detail="Mail not found")
    
#     return mail