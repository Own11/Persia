import sys

with open("api/index.py", "r") as f:
    lines = f.readlines()

new_lines = []
in_webhook = False

for line in lines:
    if line.startswith("    # ─── /start "):
        in_webhook = True
        new_lines.append("    try:\n")
    
    if in_webhook:
        if line.startswith("    "):
            new_lines.append("    " + line)
        else:
            new_lines.append(line)
        if line.startswith("    return Response(status_code=200)"):
            if "def tg_callback" not in line and "return Response" in line and "status_code=200" in line:
                pass # we will add except block at the end
    else:
        new_lines.append(line)

# Actually, it's easier to just use standard python ast/replace.
