# Force UTF-8 encoding before any other imports (critical for Cyrillic on Vercel)
import os
import sys
import io

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("LANG", "en_US.UTF-8")
os.environ.setdefault("LC_ALL", "en_US.UTF-8")

# Rewrap stdout/stderr if they are ASCII-only
if hasattr(sys.stdout, "buffer") and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer") and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import httpx
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, Request, Response
from dotenv import load_dotenv

load_dotenv()

from persia.db import init_db, add_task, get_tasks, update_task_status, delete_task, get_memories, delete_memory, clear_chat_history, get_stats
from persia.gateway import process_message, MessageContext

app = FastAPI(title="Persia Bot")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def send_message(chat_id: int, text: str) -> None:
    """Send a text message to a Telegram chat."""
    if not text:
        return
    for chunk in [text[i:i + 4000] for i in range(0, len(text), 4000)]:
        try:
            with httpx.Client() as client:
                client.post(
                    f"{TELEGRAM_API}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": chunk,
                        "parse_mode": "Markdown",
                    },
                    timeout=10,
                )
        except Exception as e:
            print(f"send_message error: {e}")


@app.on_event("startup")
def startup():
    try:
        init_db()
    except Exception as e:
        print(f"DB init error: {e}")


@app.get("/")
def health():
    return {"status": "Persia Bot is running 🐱"}



@app.post("/api/webhook")
async def webhook(request: Request):
    try:
        return await _webhook_impl(request)
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Still return 200 so Telegram stops retrying
        return Response(status_code=200)

async def _webhook_impl(request: Request):

    """Handle incoming Telegram updates."""
    try:
        update = await request.json()
        if not isinstance(update, dict):
            return Response(status_code=400)
    except Exception:
        return Response(status_code=400)

    message = update.get("message") or update.get("edited_message")
    if not message:
        return Response(status_code=200)

    chat_id: int = message["chat"]["id"]
    from_user = message.get("from", {})
    user_id = str(from_user.get("id", chat_id))
    username = from_user.get("username", from_user.get("first_name", "User"))
    
    text: str = message.get("text", "")
    if text is None:
        text = ""
    text = text.strip()

    if not text:
        return Response(status_code=200)


    # ─── /start ────────────────────────────────────────────────────────────────
    if text == "/start":
        send_message(
            chat_id,
            "👋 *Привет! Я Persia AI Agent.*\n\n"
            "Я могу управлять задачами, искать в интернете и общаться с AI.\n\n"
            "*📋 Команды задач:*\n"
            "`/addtask <название>` — добавить задачу\n"
            "`/addtask <название> | <дедлайн>` — с дедлайном\n"
            "`/list` — список задач\n"
            "`/deltask <id>` — удалить задачу\n"
            "`/donetask <id>` — отметить выполненной\n\n"
            "*🌐 AI + Интернет:*\n"
            "Просто напишите что угодно — агент ответит, а если нужно, найдёт в интернете.\n\n"
            "Попробуй: _Что сегодня в новостях?_ или _Добавь задачу купить молоко до пятницы_",
        )
        return Response(status_code=200)

    # ─── /help ─────────────────────────────────────────────────────────────────
    if text == "/help":
        send_message(
            chat_id,
            "*Доступные команды:*\n\n"
            "📋 *Задачи:*\n"
            "`/addtask <название>` — добавить задачу\n"
            "`/addtask <название> | <дедлайн>` — с дедлайном (например: `купить молоко | пятница`)\n"
            "`/list` — список всех задач с дедлайнами\n"
            "`/deltask <id>` — удалить задачу по ID\n"
            "`/donetask <id>` — отметить задачу выполненной\n\n"
            "🧠 *Память и контекст:*\n"
            "`/memories` — посмотреть факты, которые агент знает о вас\n"
            "`/forget <id>` — удалить воспоминание\n"
            "`/clear_history` — очистить историю текущего чата\n"
            "`/stats` — статистика базы данных\n\n"
            "🤖 *AI Агент:*\n"
            "Любой другой текст передаётся AI-агенту.\n"
            "Агент умеет искать в интернете, читать страницы, искать музыку, смотреть видео и управлять задачами.\n\n"
            "*Примеры:*\n"
            "• _Найди песню Linkin Park Numb в Яндекс Музыке_\n"
            "• _Что такое квантовые компьютеры?_\n"
            "• _Сделай саммари этого ютуб видео: [ссылка]_",
        )
        return Response(status_code=200)

    # ─── /addtask ──────────────────────────────────────────────────────────────
    if text.startswith("/addtask"):
        raw = text[8:].strip()
        if raw:
            # Support "название | дедлайн" format
            if "|" in raw:
                parts = raw.split("|", 1)
                task_name = parts[0].strip()
                deadline = parts[1].strip()
            else:
                task_name = raw
                deadline = None

            task_id = add_task(title=task_name, deadline=deadline)
            deadline_str = f"\n📅 Дедлайн: *{deadline}*" if deadline else ""
            send_message(chat_id, f"✅ Задача добавлена (ID: {task_id}): *{task_name}*{deadline_str}")
        else:
            send_message(
                chat_id,
                "⚠️ Укажи название:\n"
                "`/addtask моя задача`\n"
                "`/addtask купить молоко | пятница`"
            )
        return Response(status_code=200)

    # ─── /list ─────────────────────────────────────────────────────────────────
    if text == "/list":
        tasks = get_tasks()
        if not tasks:
            send_message(chat_id, "📋 Задач пока нет.")
        else:
            lines = ["📋 *Список задач:*\n"]
            for t in tasks:
                icon = "✅" if t["status"] == "done" else "🔲"
                deadline_str = f"\n      📅 до: _{t['deadline']}_" if t.get("deadline") else ""
                lines.append(f"{icon} `ID:{t['id']}` {t['title']}{deadline_str}")
            send_message(chat_id, "\n".join(lines))
        return Response(status_code=200)

    # ─── /deltask ──────────────────────────────────────────────────────────────
    if text.startswith("/deltask"):
        parts = text.split()
        if len(parts) == 2 and parts[1].isdigit():
            delete_task(int(parts[1]))
            send_message(chat_id, f"🗑 Задача `{parts[1]}` удалена.")
        else:
            send_message(chat_id, "⚠️ Использование: `/deltask <id>`")
        return Response(status_code=200)

    # ─── /donetask ─────────────────────────────────────────────────────────────
    if text.startswith("/donetask"):
        parts = text.split()
        if len(parts) == 2 and parts[1].isdigit():
            update_task_status(int(parts[1]), "done")
            send_message(chat_id, f"✅ Задача `{parts[1]}` отмечена выполненной.")
        else:
            send_message(chat_id, "⚠️ Использование: `/donetask <id>`")
        return Response(status_code=200)

    # ─── /memories ─────────────────────────────────────────────────────────────
    if text == "/memories":
        memories = get_memories(user_id)
        if not memories:
            send_message(chat_id, "🧠 Я пока ничего о вас не помню.")
        else:
            lines = ["🧠 *Мои воспоминания о вас:*\n"]
            for m in memories:
                lines.append(f"`ID:{m['id']}` — {m['fact']}")
            send_message(chat_id, "\n".join(lines))
        return Response(status_code=200)

    # ─── /forget ───────────────────────────────────────────────────────────────
    if text.startswith("/forget"):
        parts = text.split()
        if len(parts) == 2 and parts[1].isdigit():
            delete_memory(int(parts[1]))
            send_message(chat_id, f"🗑 Воспоминание `{parts[1]}` удалено.")
        else:
            send_message(chat_id, "⚠️ Использование: `/forget <id>`")
        return Response(status_code=200)

    # ─── /clear_history ────────────────────────────────────────────────────────
    if text == "/clear_history":
        clear_chat_history(str(chat_id))
        send_message(chat_id, "🧹 История этого чата очищена. Начинаем с чистого листа!")
        return Response(status_code=200)

    # ─── /stats ────────────────────────────────────────────────────────────────
    if text == "/stats":
        stats = get_stats()
        send_message(
            chat_id,
            f"📊 *Статистика бота:*\n\n"
            f"Задач: {stats['tasks']}\n"
            f"Воспоминаний: {stats['memories']}\n"
            f"Сообщений в истории: {stats['messages']}"
        )
        return Response(status_code=200)


    # ─── AI Agent fallback ─────────────────────────────────────────────────────
    send_message(chat_id, "🤔 *Думаю...*")

    collected: list[str] = []

    def tg_callback(msg: str):
        collected.append(msg)

    try:
        ctx = MessageContext(
            chat_id=str(chat_id),
            user_id=user_id,
            text=text,
            platform="telegram",
            username=username
        )
        process_message(ctx, tg_callback)
    except Exception as e:
        send_message(chat_id, f"❌ Ошибка агента: {e}")
        return Response(status_code=200)

    # Send only the final Agent text responses (filter tool noise)
    # process_message might not always prefix with "Agent:" if it's already stripped, 
    # but the run_agent still prefixes it. Let's just collect everything that isn't tool noise.
    clean_lines = []
    for m in collected:
        if any(m.startswith(x) for x in ["Running tool:", "Tool result:", "Agent started.", "Agent execution"]):
            continue
        if m.startswith("Agent:"):
            clean_lines.append(m[6:].strip())
        else:
            clean_lines.append(m)
            
    final_text = "\n".join(clean_lines) if clean_lines else ""

    if final_text:
        send_message(chat_id, final_text)
    else:
        send_message(chat_id, "✅ Готово.")

    return Response(status_code=200)
