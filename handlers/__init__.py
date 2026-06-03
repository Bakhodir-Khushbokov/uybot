from aiogram import Router

from .common import router as common_router
from .seller import router as seller_router
from .buyer  import router as buyer_router
from .admin  import router as admin_router

# Asosiy router — barcha sub-routerlarni birlashtiradi
main_router = Router()
main_router.include_router(common_router)
main_router.include_router(seller_router)
main_router.include_router(buyer_router)
main_router.include_router(admin_router)
