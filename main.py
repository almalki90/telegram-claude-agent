import os, sys, logging
sys.path.insert(0, '/home/user/tgbot')

from dotenv import load_dotenv
load_dotenv('/home/user/tgbot/.env')

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ChatAction

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("/home/user/tgbot/bot.log", encoding="utf-8")])
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

import storage
from agent import Agent
from providers import PROVIDER_INFO

TOKEN = os.getenv("TELEGRAM_TOKEN","")
if not TOKEN:
    logger.error("TELEGRAM_TOKEN missing"); sys.exit(1)

storage.init_db()
bot_agent = Agent()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    p = storage.get_active_provider(u.id)
    if p:
        info = PROVIDER_INFO.get(p, {})
        m = storage.get_active_model(u.id) or info.get("default_model","")
        text = f"مرحبا {u.first_name}!\n\nالمزود: {info.get('emoji','')} {info.get('name',p)}\nالموديل: {m}\n\nابدأ الكتابة!"
        kb = [[InlineKeyboardButton("تغيير المزود", callback_data="menu_providers")],
              [InlineKeyboardButton("مسح المحادثة", callback_data="menu_clear")]]
    else:
        text = f"اهلا {u.first_name}!\n\nانا الوكيل الذكي — SSH، HTTP، قواعد البيانات، الملفات.\n\nابدأ بإضافة مفتاح AI:"
        kb = [[InlineKeyboardButton("➕ إضافة مفتاح AI", callback_data="menu_providers")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.clear_context(update.effective_user.id)
    await update.message.reply_text("✅ تم مسح المحادثة!")

async def cmd_addkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _show_providers(update.message)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    p = storage.get_active_provider(u.id)
    if p:
        info = PROVIDER_INFO.get(p,{})
        m = storage.get_active_model(u.id) or info.get("default_model","")
        ctx = len(storage.get_context(u.id))
        await update.message.reply_text(f"المزود: {info.get('emoji','')} {info.get('name',p)}\nالموديل: {m}\nرسائل: {ctx}")
    else:
        await update.message.reply_text("لا يوجد مزود.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ مفتاح", callback_data="menu_providers")]]))

async def _show_providers(msg, edit=False):
    kb = [[InlineKeyboardButton(f"{i['emoji']} {i['name']}{' (مجاني)' if i.get('free') else ''}", callback_data=f"addkey_{k}")] for k,i in PROVIDER_INFO.items()]
    kb.append([InlineKeyboardButton("❌ الغاء", callback_data="cancel")])
    markup = InlineKeyboardMarkup(kb)
    if edit: await msg.edit_text("اختر مزود AI:", reply_markup=markup)
    else: await msg.reply_text("اختر مزود AI:", reply_markup=markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    u = q.from_user
    d = q.data

    if d == "menu_providers":
        await _show_providers(q.message, edit=True)
    elif d == "menu_clear":
        storage.clear_context(u.id)
        await q.edit_message_text("✅ تم مسح المحادثة!")
    elif d == "cancel":
        storage.clear_waiting_for_key(u.id)
        await q.edit_message_text("الغاء.")
    elif d.startswith("addkey_"):
        pname = d[7:]
        info = PROVIDER_INFO.get(pname,{})
        storage.set_waiting_for_key(u.id, pname)
        await q.edit_message_text(
            f"ارسل مفتاح {info.get('emoji','')} {info.get('name',pname)}:\n\n"
            f"رابط المفتاح: {info.get('test_url','')}\n\nارسله كرسالة عادية",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ الغاء", callback_data="cancel")]]))
    elif d.startswith("model_"):
        parts = d.split("_",2)
        if len(parts)==3:
            pname, mname = parts[1], parts[2]
            info = PROVIDER_INFO.get(pname,{})
            storage.set_active_provider(u.id, pname, mname)
            await q.edit_message_text(f"✅ {info.get('emoji','')} {info.get('name',pname)}\nالموديل: {mname}\n\nابدأ الكتابة!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    u = update.effective_user
    txt = update.message.text.strip()

    waiting = storage.get_waiting_for_key(u.id)
    if waiting:
        await _receive_key(update, context, waiting, txt); return

    if not storage.get_active_provider(u.id):
        await update.message.reply_text("لا يوجد مزود AI.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ مفتاح", callback_data="menu_providers")]])); return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    resp = bot_agent.generate(u.id, txt)

    if resp is None:
        await update.message.reply_text("المزود غير متاح.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ مفتاح", callback_data="menu_providers")]])); return

    if len(resp) <= 4000:
        await update.message.reply_text(resp)
    else:
        parts = [resp[i:i+4000] for i in range(0,len(resp),4000)]
        for i,part in enumerate(parts):
            await update.message.reply_text(f"[{i+1}/{len(parts)}] {part}" if len(parts)>1 else part)

async def _receive_key(update, context, pname, raw):
    u = update.effective_user
    info = PROVIDER_INFO.get(pname,{})
    if raw.startswith("http"):
        await update.message.reply_text("ارسل المفتاح النصي مباشرة"); return
    api_key = raw.strip()
    try: await update.message.delete()
    except: pass
    wait_msg = await context.bot.send_message(chat_id=update.effective_chat.id,
        text=f"⏳ جاري التحقق من {info.get('emoji','')} {info.get('name',pname)}...")
    storage.clear_waiting_for_key(u.id)
    try:
        ok, msg = bot_agent.test_key(u.id, pname, api_key, info.get("default_model",""))
    except Exception as e:
        ok, msg = False, str(e)[:200]
    if ok:
        storage.save_api_key(u.id, pname, api_key, info.get("default_model",""))
        models = info.get("models",[info.get("default_model","")])
        kb = []; row = []
        for i,m in enumerate(models):
            row.append(InlineKeyboardButton(m+(" ✓" if m==info.get("default_model") else ""), callback_data=f"model_{pname}_{m}"))
            if len(row)==2 or i==len(models)-1: kb.append(row); row=[]
        await wait_msg.edit_text(f"✅ المفتاح يعمل!\n\nالرد: {msg[:80]}\n\nاختر الموديل:", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await wait_msg.edit_text(f"❌ المفتاح لا يعمل\n\n{msg}\n\nتاكد من نسخ المفتاح كاملا",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("اعد المحاولة", callback_data=f"addkey_{pname}"), InlineKeyboardButton("مزودون اخرون", callback_data="menu_providers")]]))

async def post_init(app):
    await app.bot.set_my_commands([BotCommand("start","الرئيسية"),BotCommand("addkey","+ مفتاح AI"),BotCommand("status","حالتي"),BotCommand("clear","مسح المحادثة")])

def main():
    logger.info("🚀 تشغيل البوت...")
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("addkey", cmd_addkey))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("✅ البوت جاهز!")
    app.run_polling(drop_pending_updates=True, allowed_updates=["message","callback_query"])

if __name__ == "__main__":
    main()
