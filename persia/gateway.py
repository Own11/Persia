from dataclasses import dataclass
from typing import Callable, Optional
from persia.db import get_memories, get_conversation_history, add_conversation_message
from persia.agent import run_agent

@dataclass
class MessageContext:
    chat_id: str
    user_id: str
    text: str
    platform: str # e.g., 'telegram', 'terminal'
    username: Optional[str] = None

def process_message(context: MessageContext, ui_callback: Callable[[str], None] = None):
    """
    Gateway to process messages from multiple channels.
    Injects memory and context before sending to the agent.
    """
    # 1. Fetch memories for this user
    memories = get_memories(context.user_id)
    memory_context = ""
    if memories:
        facts = [m['fact'] for m in memories]
        memory_context = f"\n[System Context: You know the following facts about the user '{context.username or context.user_id}': {', '.join(facts)}]\n"

    # 2. Fetch conversation history for this chat
    history = get_conversation_history(context.chat_id, limit=10)
    history_context = ""
    if history:
        history_lines = [f"{h['role']}: {h['content']}" for h in history]
        history_context = f"\n[System Context: Recent conversation history in this chat:\n" + "\n".join(history_lines) + "]\n"
    
    # 3. Construct the enriched task description
    enriched_prompt = f"{memory_context}{history_context}\nUser ({context.username or context.user_id}): {context.text}"

    # 4. Save user message to history
    add_conversation_message(context.chat_id, "user", context.text)
    
    # We need a callback wrapper to capture the agent's responses and save them to DB
    collected_responses = []
    
    def gateway_callback(msg: str):
        if msg.startswith("Agent:"):
            # Only save actual agent responses to history, not tool execution logs
            clean_msg = msg[6:].strip()
            add_conversation_message(context.chat_id, "agent", clean_msg)
            collected_responses.append(clean_msg)
        
        if ui_callback:
            ui_callback(msg)

    # 5. Run the agent
    run_agent(enriched_prompt, context.user_id, gateway_callback)
