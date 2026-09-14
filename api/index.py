import os
import httpx
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, Request, Response
from dotenv import load_dotenv

load_dotenv()

from persia.db import init_db, add_task, get_tasks, update_task_status, delete_task
from persia.agent import run_agent

app = FastAPI(title="Persia Bot")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def send_message(chat_id: int, text: str) -> None:
    """Send a text message to a Telegram chat."""
    if not text:
        return
    # Telegram has a 4096 char limit per message
    for chunk in [text[i:i + 4000] for i in range(0, len(text), 4000)]:
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
    """Handle incoming Telegram updates."""
    try:
        update = await request.json()
    except Exception:
        return Response(status_code=400)

    # Handle only regular text messages
    message = update.get("message") or update.get("edited_message")
    if not message:
        return Response(status_code=200)

    chat_id: int = message["chat"]["id"]
    text: str = message.get("text", "").strip()

    if not text:
        return Response(status_code=200)

    # --- Built-in commands ---
    if text == "/start":
        send_message(
            chat_id,
            "👋 *Привет! Я Persia AI Agent.*\n\n"
            "Я могу управлять задачами и общаться с AI.\n\n"
            "*Команды:*\n"
            "`/addtask <название>` — добавить задачу\n"
            "`/list` — список задач\n"
            "`/deltask <id>` — удалить задачу\n"
            "`/donetask <id>` — отметить выполненной\n"
            "`/help` — показать помощь\n\n"
            "Или просто напишите мне что-нибудь — я отвечу как AI.",
        )
        return Response(status_code=200)

    if text == "/help":
        send_message(
            chat_id,
            "*Доступные команды:*\n"
            "`/addtask <название>` — добавить задачу\n"
            "`/list` — список всех задач\n"
            "`/deltask <id>` — удалить задачу по ID\n"
            "`/donetask <id>` — отметить задачу выполненной\n\n"
            "Любой другой текст будет передан AI-агенту.",
        )
        return Response(status_code=200)

    if text.startswith("/addtask"):
        task_name = text[8:].strip().strip('"\'')
        if task_name:
            task_id = add_task(title=task_name)
            send_message(chat_id, f"✅ Задача добавлена (ID: {task_id}): *{task_name}*")
        else:
            send_message(chat_id, "⚠️ Укажи название: `/addtask моя задача`")
        return Response(status_code=200)

    if text == "/list":
        tasks = get_tasks()
        if not tasks:
            send_message(chat_id, "📋 Задач пока нет.")
        else:
            lines = ["📋 *Список задач:*\n"]
            for t in tasks:
                icon = "✅" if t["status"] == "done" else "🔲"
                lines.append(f"{icon} `ID:{t['id']}` {t['title']}")
            send_message(chat_id, "\n".join(lines))
        return Response(status_code=200)

    if text.startswith("/deltask"):
        parts = text.split()
        if len(parts) == 2 and parts[1].isdigit():
            delete_task(int(parts[1]))
            send_message(chat_id, f"🗑 Задача `{parts[1]}` удалена.")
        else:
            send_message(chat_id, "⚠️ Использование: `/deltask <id>`")
        return Response(status_code=200)

    if text.startswith("/donetask"):
        parts = text.split()
        if len(parts) == 2 and parts[1].isdigit():
            update_task_status(int(parts[1]), "done")
            send_message(chat_id, f"✅ Задача `{parts[1]}` отмечена выполненной.")
        else:
            send_message(chat_id, "⚠️ Использование: `/donetask <id>`")
        return Response(status_code=200)

    # --- AI Agent fallback ---
    send_message(chat_id, "🤔 *Думаю...*")

    collected: list[str] = []

    def tg_callback(msg: str):
        collected.append(msg)

    try:
        run_agent(text, tg_callback)
    except Exception as e:
        send_message(chat_id, f"❌ Ошибка агента: {e}")
        return Response(status_code=200)

    # Filter out internal/tool messages, keep only final Agent text
    final_lines = [m for m in collected if m.startswith("Agent:")]
    if final_lines:
        final_text = "\n".join(final_lines).replace("Agent: Agent: ", "Agent: ")
    else:
        final_text = "\n".join(collected)

    if final_text:
        send_message(chat_id, final_text)
    else:
        send_message(chat_id, "✅ Готово.")

    return Response(status_code=200)
