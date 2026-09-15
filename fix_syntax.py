import sys

with open("api/index.py", "r") as f:
    content = f.read()

content = content.replace("""    try:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return Response(status_code=200)

        chat_id: int = message["chat"]["id"]
        text: str = message.get("text", "")
        if text is None:
            text = ""
        text = text.strip()

        if not text:
            return Response(status_code=200)""", """    message = update.get("message") or update.get("edited_message")
    if not message:
        return Response(status_code=200)

    chat_id: int = message["chat"]["id"]
    text: str = message.get("text", "")
    if text is None:
        text = ""
    text = text.strip()

    if not text:
        return Response(status_code=200)""")

with open("api/index.py", "w") as f:
    f.write(content)

