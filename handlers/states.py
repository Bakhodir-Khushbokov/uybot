from aiogram.fsm.state import State, StatesGroup


class RegStates(StatesGroup):
    language = State()
    phone    = State()
    role     = State()


class SellerStates(StatesGroup):
    transaction    = State()   # sotish / arenda
    property_type  = State()
    dom_type       = State()
    # Lokatsiya
    viloyat        = State()
    tuman          = State()
    loc_type       = State()   # mahalla yoki kvartal (faqat Toshkent shahri)
    mahalla_search = State()
    mahalla_page   = State()
    kvartal_manual = State()   # Toshkent kvartal qo'lda kiritish
    # Dom
    dom_number     = State()
    loc_found      = State()
    loc_manual     = State()
    loc_save       = State()
    # Video
    video          = State()
    # Ma'lumotlar
    xonalar        = State()
    floor          = State()
    total_floors   = State()
    area           = State()
    renovation     = State()
    balkon         = State()   # balkon o'lchami
    landmark       = State()
    # Qo'shimcha (arenda / makler)
    rent_for       = State()   # faqat arenda uchun: oila/chet_ellik/yigitlar/qizlar/farqi_yoq
    jihoz          = State()   # faqat arenda uchun: jihoz tanlash (multi-select)
    commission     = State()   # faqat makler uchun
    # Narx
    price_currency = State()
    price_amount   = State()
    # Tasdiqlash
    review         = State()


class BuyerStates(StatesGroup):
    transaction     = State()   # sotish / arenda
    property_type   = State()
    location_choice = State()
    viloyat         = State()
    tuman           = State()
    mahalla_search  = State()
    mahalla_page    = State()
    # Filtrlar
    xonalar         = State()
    dom_type        = State()
    renovation      = State()
    # Natijalar
    results         = State()
    report_text     = State()   # "Boshqa sabab" uchun erkin matn


class AdminStates(StatesGroup):
    menu            = State()
    # Hudud
    add_viloyat     = State()
    add_tuman       = State()
    add_mahalla     = State()
    add_postal      = State()
    # Bino
    select_loc      = State()
    search_loc      = State()
    add_kvartal     = State()
    add_dom         = State()
    add_coords      = State()
    # O'chirish
    del_loc_search  = State()
    del_bld_search  = State()
