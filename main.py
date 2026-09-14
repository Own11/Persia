import asyncio
# pyrefly: ignore [missing-import]
from textual.app import App, ComposeResult
# pyrefly: ignore [missing-import]
from textual.containers import Vertical, Horizontal
# pyrefly: ignore [missing-import]
from textual.widgets import Input, RichLog, Label, Static
# pyrefly: ignore [missing-import]
from textual.worker import Worker
# pyrefly: ignore [missing-import]
from textual import work
# pyrefly: ignore [missing-import]

from persia.db import init_db, get_tasks, add_task, delete_task, update_task_status
from persia.agent import run_agent
from persia.llm import MODEL

PERSIA_LOGO = r"""[cda529]
  ___ ___ ___ ___ ___   _     _  ___ 
 | _ \ __| _ \ __|_ _| /_\   /_\|_ _|
 |  _/ _||   /__ \| | / _ \ / _ \| | 
 |_| |___|_|_\___/___/_/ \_\_/ \_\___| v1.0
[/]"""

class PersiaApp(App):
    CSS = """
    Screen {
        background: #000000;
        color: #e0e0e0;
    }
    
    #main-container {
        padding: 1 2;
        height: 100%;
    }
    
    #logo {
        height: auto;
        text-align: center;
        margin-bottom: 1;
    }
    
    #chat-log {
        height: 1fr;
        border: solid #333333;
        background: #050505;
        padding: 0 1;
        scrollbar-color: #cda529;
    }
    
    #input-section {
        height: auto;
        layout: horizontal;
        margin-top: 1;
        border: solid #cda529;
        background: #111111;
    }
    
    #prompt-symbol {
        color: #cda529;
        text-style: bold;
        width: 3;
        padding-left: 1;
        content-align: center middle;
    }
    
    #chat-input {
        width: 1fr;
        border: none;
        background: #111111;
        color: #ffffff;
    }
    
    #chat-input:focus {
        border: none;
    }
    
    #status-bar {
        dock: bottom;
        height: 1;
        background: #0a0a0a;
        color: #666666;
        text-align: right;
        padding-right: 1;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="main-container"):
            yield Static(PERSIA_LOGO, id="logo")
            yield RichLog(id="chat-log", highlight=True, markup=True, wrap=True)
            
            with Horizontal(id="input-section"):
                yield Label("❯", id="prompt-symbol")
                yield Input(id="chat-input", placeholder="Type a command or chat with AI...")
                
        yield Label(f"Model: {MODEL} | Status: Online | Press 'q' to quit", id="status-bar")

    def on_mount(self) -> None:
        init_db()
        self.log_to_chat("[cda529]System:[/] Persia Agent Initialized.")
        self.log_to_chat("[grey50]Type /help for a list of available commands or just start chatting.[/]")

    def log_to_chat(self, text: str) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(text)

    def print_tasks_to_chat(self) -> None:
        tasks = get_tasks()
        if not tasks:
            self.log_to_chat("[grey50]No active tasks.[/]")
            return
            
        self.log_to_chat("\n[bold cda529]--- Active Tasks ---[/]")
        for task in tasks:
            status = "[green][x][/]" if task['status'] == 'done' else "[yellow][ ][/]"
            self.log_to_chat(f" {status} (ID: {task['id']}) {task['title']}")
        self.log_to_chat("[bold cda529]--------------------[/]\n")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
            
        input_box = self.query_one("#chat-input", Input)
        input_box.value = ""
        
        # Echo user input
        self.log_to_chat(f"\n[bold white]❯ {text}[/]")
        
        lower_text = text.lower()
        if lower_text.startswith("/addtask"):
            task_name = text[8:].strip().strip('"\'')
            if task_name:
                add_task(title=task_name)
                self.log_to_chat(f"[cda529]System:[/] Task added: {task_name}")
            else:
                self.log_to_chat(f"[cda529]System:[/] Please provide a task name, e.g. /addtask \"my task\"")
                
        elif lower_text.startswith("/deltask"):
            try:
                task_id = int(text.split()[1])
                delete_task(task_id)
                self.log_to_chat(f"[cda529]System:[/] Task {task_id} deleted.")
            except (IndexError, ValueError):
                self.log_to_chat(f"[cda529]System:[/] Usage: /deltask <id>")
                
        elif lower_text.startswith("/donetask"):
            try:
                task_id = int(text.split()[1])
                update_task_status(task_id, 'done')
                self.log_to_chat(f"[cda529]System:[/] Task {task_id} marked as done.")
            except (IndexError, ValueError):
                self.log_to_chat(f"[cda529]System:[/] Usage: /donetask <id>")
                
        elif lower_text == "/list":
            self.print_tasks_to_chat()
            
        elif lower_text == "/clear":
            chat_log = self.query_one("#chat-log", RichLog)
            chat_log.clear()
            self.log_to_chat("[cda529]System:[/] Log cleared.")
            
        elif lower_text == "/help":
            self.log_to_chat(
                "\n[cda529]Available Commands:[/]\n"
                "  [white]/addtask <name>[/] - Add a task manually\n"
                "  [white]/list[/]           - View all your tasks\n"
                "  [white]/deltask <id>[/]   - Delete a task by ID\n"
                "  [white]/donetask <id>[/]  - Mark a task as done by ID\n"
                "  [white]/clear[/]          - Clear this log\n"
                "  [white]/help[/]           - Show this help\n"
                "  [grey50]<any other text>[/] - Talk to the AI Agent\n"
            )
            
        else:
            # Pass to AI agent
            self.run_agent_task(text)

    @work(thread=True)
    def run_agent_task(self, task_description: str) -> None:
        def ui_callback(msg: str):
            self.call_from_thread(self.log_to_chat, f"[cda529]Agent:[/] {msg}")
                
        run_agent(task_description, ui_callback)

if __name__ == "__main__":
    app = PersiaApp()
    app.run()
