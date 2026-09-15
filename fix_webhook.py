import sys

with open("api/index.py", "r") as f:
    content = f.read()

# Replace the webhook function to catch all exceptions and log them
new_code = """
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
"""

content = content.replace('@app.post("/api/webhook")\nasync def webhook(request: Request):', new_code)

with open("api/index.py", "w") as f:
    f.write(content)

