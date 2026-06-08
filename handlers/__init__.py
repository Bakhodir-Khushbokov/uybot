from aiogram import Router

from .common import router as common_router
from .seller import router as seller_router
from .buyer  import router as buyer_router
from .admin    import router as admin_router
from .feedback    import router as feedback_router
from .superadmin  import router as superadmin_router
from .notary         import router as notary_router
from .organizations  import router as org_router

# Asosiy router — barcha sub-routerlarni birlashtiradi
main_router = Router()
main_router.include_router(superadmin_router)
main_router.include_router(common_router)
main_router.include_router(seller_router)
main_router.include_router(buyer_router)
main_router.include_router(admin_router)
main_router.include_router(notary_router)
main_router.include_router(org_router)
main_router.include_router(feedback_router)
