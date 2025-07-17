import os
import io
import zipfile
import rarfile
import platform
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Список админов
ADMINS = {1063257439}  # начальный админ

# В памяти
databases = []
users = {}  # user_id: username


def is_admin(user_id):
    return user_id in ADMINS


async def add_database(file_bytes: bytes, filename: str):
    name = filename
    size = len(file_bytes)
    data_lines = []

    ext = filename.lower().split('.')[-1]

    try:
        if ext == 'zip':
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                for fname in zf.namelist():
                    if fname.lower().endswith(('.txt', '.csv')):
                        with zf.open(fname) as f:
                            content = f.read().decode(errors='ignore')
                            data_lines = content.splitlines()
                        name = fname
                        break
                else:
                    return False, "В ZIP нет txt или csv"

        elif ext == 'rar':
            try:
                with rarfile.RarFile(io.BytesIO(file_bytes)) as rf:
                    for fname in rf.namelist():
                        if fname.lower().endswith(('.txt', '.csv')):
                            with rf.open(fname) as f:
                                content = f.read().decode(errors='ignore')
                                data_lines = content.splitlines()
                            name = fname
                            break
                    else:
                        return False, "В RAR нет txt или csv"
            except Exception:
                return False, "Ошибка RAR: отсутствует unrar или неправильный архив"

        elif ext in ('txt', 'csv'):
            content = file_bytes.decode(errors='ignore')
            data_lines = content.splitlines()
        else:
            return False, "Неподдерживаемый формат файла"

        databases.append({
            'name': name,
            'data': data_lines,
            'size': size,
            'lines_count': len(data_lines),
        })
        return True, f"✅ База '{name}' загружена.\nСтрок: {len(data_lines)}\nРазмер: {size} байт"
    except Exception as e:
        return False, f"Ошибка: {str(e)}"


async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users[user.id] = user.username or user.full_name
    text = (
        "📁 *Бот-поисковик по базам данных*\n\n"
        "🔍 /search <запрос> — поиск по базам\n"
        "➕ /add — добавить базу\n"
        "🆘 /support — поддержка: @gpsblue\n"
        "ℹ️ /info — это сообщение\n"
    )
    if is_admin(user.id):
        text += (
            "\n👑 Команды для админа:\n"
            "/bdinfo — информация по базам\n"
            "/adm — статус бота\n"
            "/setadmin <user_id> — добавить админа"
        )
    await update.message.reply_text(text, parse_mode='Markdown')


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🆘 Поддержка: @gpsblue")


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document:
        await update.message.reply_text("Пожалуйста, отправьте файл базы данных после команды /add.")
        return

    doc = update.message.document
    file_name = doc.file_name
    if not file_name.lower().endswith(('.csv', '.txt', '.zip', '.rar')):
        await update.message.reply_text("❌ Поддерживаются только форматы: .csv, .txt, .zip, .rar")
        return

    file = await doc.get_file()
    file_bytes = await file.download_as_bytearray()

    success, msg = await add_database(file_bytes, file_name)
    await update.message.reply_text(msg)


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("🔍 Использование: /search Иванов")
        return

    query = ' '.join(args).lower()
    results = []

    for db in databases:
        for line in db['data']:
            if query in line.lower():
                results.append(f"[{db['name']}] {line}")
                if len(results) >= 20:
                    break
        if len(results) >= 20:
            break

    if results:
        await update.message.reply_text("\n".join(results[:20]))
    else:
        await update.message.reply_text("Ничего не найдено.")


async def bdinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для админа.")
        return

    if not databases:
        await update.message.reply_text("Базы не загружены.")
        return

    lines = []
    total_size = 0
    total_lines = 0

    for db in databases:
        lines.append(f"📄 {db['name']} — {db['size']} байт — {db['lines_count']} строк")
        total_size += db['size']
        total_lines += db['lines_count']

    lines.append(f"\n📊 Общий объём: {total_size} байт\n📈 Всего строк: {total_lines}")
    await update.message.reply_text('\n'.join(lines))


async def adm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для админа.")
        return

    lines = [
        f"👥 Пользователей: {len(users)}",
        "👤 Список пользователей:\n" + '\n'.join([f"{k} — {v}" for k, v in users.items()]),
        f"📦 Баз данных: {len(databases)}"
    ]

    for db in databases:
        lines.append(f"• {db['name']} — {db['size']} байт — {db['lines_count']} строк")

    sysinfo = (
        f"\n💻 Сервер: {platform.system()} {platform.release()}\n"
        f"🐍 Python: {platform.python_version()}"
    )

    lines.append(sysinfo)

    await update.message.reply_text('\n'.join(lines))


async def setadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только админ может назначить другого админа.")
        return

    if not context.args:
        await update.message.reply_text("🛠 Использование: /setadmin <user_id>")
        return

    try:
        new_id = int(context.args[0])
        ADMINS.add(new_id)
        await update.message.reply_text(f"✅ Пользователь {new_id} теперь администратор.")
    except ValueError:
        await update.message.reply_text("❌ Неверный формат ID. Используйте целое число.")


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Неизвестная команда. Введите /info для справки.")


def main():
    TOKEN = os.getenv("BOT_TOKEN") or "ВАШ_ТОКЕН_ТУТ"

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler(["start", "info"], info))
    app.add_handler(CommandHandler("support", support))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("bdinfo", bdinfo))
    app.add_handler(CommandHandler("adm", adm))
    app.add_handler(CommandHandler("setadmin", setadmin))

    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    print("✅ Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
