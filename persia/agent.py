import subprocess
import os
from typing import Callable
from google.genai import types

from persia.llm import get_client, MODEL
from persia.db import add_task, update_task_status, delete_task

def execute_shell(command: str) -> str:
    """Execute a shell command and return the output. Use this for running terminal commands."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout
        if result.stderr:
            output += "\nERROR:\n" + result.stderr
        return output if output else "Command executed successfully with no output."
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return f"Error executing command: {e}"

def list_files(directory_path: str) -> str:
    """List files and directories in the specified path."""
    try:
        files = os.listdir(directory_path)
        return "\n".join(files) if files else "Directory is empty."
    except Exception as e:
        return f"Error listing directory: {e}"

def read_file(filepath: str) -> str:
    """Read contents of a file."""
    try:
        with open(filepath, 'r') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(filepath: str, content: str) -> str:
    """Write contents to a file."""
    try:
        with open(filepath, 'w') as f:
            f.write(content)
        return f"File {filepath} written successfully."
    except Exception as e:
        return f"Error writing file: {e}"

def create_task(title: str, description: str = "") -> str:
    """Create a new task in the user's task manager list. Use this when the user asks to remember a task, or to break down your own work into subtasks."""
    task_id = add_task(title, description)
    return f"Created task ID {task_id}: {title}"

def mark_task_done(task_id: int) -> str:
    """Mark a task as done using its ID."""
    update_task_status(task_id, 'done')
    return f"Task {task_id} marked as done."

def delete_task_by_id(task_id: int) -> str:
    """Delete a task from the list using its ID."""
    delete_task(task_id)
    return f"Task {task_id} deleted."

def list_tasks() -> str:
    """Get a list of all current tasks and their IDs. Use this to find the ID of a task before marking it done or deleting it."""
    from persia.db import get_tasks
    tasks = get_tasks()
    if not tasks:
        return "No tasks found."
    return "\n".join([f"ID: {t['id']} | Title: {t['title']} | Status: {t['status']}" for t in tasks])

AVAILABLE_TOOLS = {
    'execute_shell': execute_shell,
    'list_files': list_files,
    'read_file': read_file,
    'write_file': write_file,
    'create_task': create_task,
    'mark_task_done': mark_task_done,
    'delete_task_by_id': delete_task_by_id,
    'list_tasks': list_tasks
}

def run_agent(task_description: str, ui_callback: Callable[[str], None] = None):
    """Run the agent loop for a given task using Gemini API."""
    try:
        client = get_client()
    except Exception as e:
        if ui_callback:
            ui_callback(f"Error initializing Gemini client: {e}")
        return

    sys_instr = (
        "You are Persia, a helpful AI terminal agent and task manager. "
        "You have access to tools to interact with the system and manage tasks. "
        "When the user asks you to add a task, use create_task to save it. "
        "When given a complex objective, you can use execute_shell to run commands and create_task to track your sub-steps. "
        "Keep your text responses concise and informative."
    )

    tools_list = [execute_shell, list_files, read_file, write_file, create_task, mark_task_done, delete_task_by_id, list_tasks]

    chat = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=sys_instr,
            tools=tools_list,
            temperature=0.2
        )
    )

    if ui_callback:
        ui_callback("Agent started. Thinking...")

    try:
        response = chat.send_message(task_description)
    except Exception as e:
        if ui_callback:
            ui_callback(f"Error from Gemini API: {e}")
        return

    for _ in range(15): # Max steps
        if response.text and ui_callback:
            ui_callback(f"Agent: {response.text}")

        if not response.function_calls:
            break # Done

        tool_responses = []
        for tool_call in response.function_calls:
            func_name = tool_call.name
            args = tool_call.args or {}
            
            if ui_callback:
                ui_callback(f"Running tool: {func_name} with args {args}")

            if func_name in AVAILABLE_TOOLS:
                tool_func = AVAILABLE_TOOLS[func_name]
                try:
                    if hasattr(args, "model_dump"):
                        args_dict = args.model_dump()
                    elif isinstance(args, dict):
                        args_dict = args
                    else:
                        args_dict = dict(args)
                        
                    # Pass the dict of args to the function
                    result = tool_func(**args_dict)
                except Exception as e:
                    result = f"Error calling tool: {e}"
            else:
                result = f"Unknown tool {func_name}"

            if ui_callback:
                ui_callback(f"Tool Result: {result}")
            
            tool_responses.append(
                types.Part.from_function_response(
                    name=func_name,
                    response={"result": str(result)}
                )
            )
        
        if tool_responses:
            try:
                response = chat.send_message(tool_responses)
            except Exception as e:
                if ui_callback:
                    ui_callback(f"Error sending tool result: {e}")
                break

    if ui_callback:
        ui_callback("Agent execution completed.")
