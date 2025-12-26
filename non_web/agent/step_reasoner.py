import json
import re
from datetime import datetime

class StepReasoner:
    def __init__(self, llm: "LLMClient", action_list: list = None):
        self.llm = llm
        self.action_list = action_list or []
        self.current_action_index = 0

    def next_action(self, goal: str, history: list, last_result: dict):
        # If we have a predefined action list, use it
        if self.action_list and self.current_action_index < len(self.action_list):
            action_cmd = self.action_list[self.current_action_index]
            print(f"[DEBUG] [{datetime.now().strftime('%H:%M:%S')}] Executing planned action [{self.current_action_index + 1}/{len(self.action_list)}]: {action_cmd}")
            
            # Check if done
            if action_cmd.strip().lower() == "done":
                return {"status": "goal_achieved"}
            
            # Parse the action command and convert to action dict
            action_dict = self._parse_action_command(action_cmd)
            
            self.current_action_index += 1
            
            return {
                "status": "continue",
                "action": action_dict
            }
        
        # Fall back to AI reasoning if no action list or we've exhausted it
        prompt = f"""
You are an autonomous agent.

GOAL:
{goal}

HISTORY OF ACTIONS:
{json.dumps(history, indent=2)}

LAST EXECUTION RESULT:
{json.dumps(last_result, indent=2)}

DECIDE THE NEXT ACTION.

Rules:
- Return ONLY valid JSON (no markdown, no explanation).
- If the GOAL is achieved → return {{"status":"goal_achieved"}}
- Otherwise propose the next action:
  {{
      "status": "continue",
      "action": {{
          "type": "...",
          "command": "...",
          "machine": "local|ssh",
          "params": {{}}
      }}
  }}
"""

        result = self.llm.ask(prompt)
        print(f"[DEBUG] StepReasoner raw response:\n{result}\n")
        
        # Extract JSON from markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result, re.DOTALL)
        if json_match:
            result = json_match.group(1)
        
        # Clean up the result
        result = result.strip()
        
        try:
            return json.loads(result)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse JSON: {e}")
            print(f"[ERROR] Raw response was: {result}")
            raise
    
    def _parse_action_command(self, action_cmd: str) -> dict:
        """
        Parse action commands like:
        - ssh_connect("10.10.26.255", "root", "P@ssword123")
        - ssh_run("test -f /opt/data/report.txt")
        - local_run("echo test")
        - ssh_disconnect()
        """
        action_cmd = action_cmd.strip()
        
        # Extract function name and arguments
        match = re.match(r'(\w+)\((.*)\)', action_cmd)
        if not match:
            raise ValueError(f"Invalid action command format: {action_cmd}")
        
        func_name = match.group(1)
        args_str = match.group(2)
        
        # Parse arguments (simple string extraction)
        args = []
        if args_str:
            # Split by comma but respect quoted strings
            args = re.findall(r'"([^"]*)"', args_str)
        
        # Convert to action dictionary
        if func_name == "ssh_connect":
            return {
                "type": "ssh_connect",
                "machine": "ssh",
                "params": {
                    "host": args[0] if len(args) > 0 else "",
                    "username": args[1] if len(args) > 1 else "",
                    "password": args[2] if len(args) > 2 else ""
                }
            }
        elif func_name == "powershell_connect":
            return {
                "type": "powershell_connect",
                "machine": "powershell",
                "params": {
                    "host": args[0] if len(args) > 0 else "",
                    "username": args[1] if len(args) > 1 else "",
                    "password": args[2] if len(args) > 2 else ""
                }
            }
        elif func_name == "powershell_run":
            return {
                "type": "command",
                "command": args[0] if args else "",
                "machine": "powershell",
                "remote": True,
                "params": {}
            }
        elif func_name == "powershell_disconnect":
            return {
                "type": "powershell_disconnect",
                "machine": "powershell",
                "params": {}
            }
        elif func_name == "ssh_run":
            return {
                "type": "command",
                "command": args[0] if args else "",
                "machine": "ssh",
                "params": {}
            }
        elif func_name == "local_run":
            return {
                "type": "command",
                "command": args[0] if args else "",
                "machine": "local",
                "params": {}
            }
        elif func_name == "ssh_disconnect":
            return {
                "type": "ssh_disconnect",
                "machine": "ssh",
                "params": {}
            }
        elif func_name == "verify_output":
            return {
                "type": "verify_output",
                "machine": "local",
                "params": {
                    "expected": args[0] if args else ""
                }
            }
        elif func_name == "powershell_command":
            return {
                "type": "powershell_command",
                "machine": "powershell",
                "command": args[0] if args else "",
                "remote": True,
                "params": {}
            }
        elif func_name == "powershell_capability":
            return {
                "type": "powershell_capability",
                "machine": "powershell",
                "command": args[0],
                "params": {
                    "fail_fast": True
                }
            }
        else:
            # Generic fallback
            return {
                "type": func_name,
                "machine": "local",
                "params": {"args": args}
            }
