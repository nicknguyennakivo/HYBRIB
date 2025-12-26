import json
import re

class ActionHealer:
    """
    AI-powered self-healing for failed actions.
    Analyzes failures and generates corrected actions.
    """
    def __init__(self, llm: "LLMClient", max_heal_attempts=3):
        self.llm = llm
        self.max_heal_attempts = max_heal_attempts
    
    def heal_action(self, 
                    failed_action: dict, 
                    error_info: dict, 
                    goal: str, 
                    history: list,
                    attempt_number: int = 1) -> dict:
        """
        Analyze a failed action and generate a corrected version.
        
        Args:
            failed_action: The action that failed
            error_info: Error details (stdout, stderr, error message)
            goal: The overall goal we're trying to achieve
            history: Previous actions and results
            attempt_number: Which healing attempt this is
            
        Returns:
            dict with:
                - should_retry: bool - whether to retry
                - corrected_action: dict - the fixed action (if should_retry=True)
                - reason: str - explanation of the fix
                - give_up: bool - whether to abandon this action
        """
        
        # Build context for the AI
        history_summary = self._summarize_history(history[-5:])  # Last 5 actions
        
        prompt = f"""
You are an AI automation healer. An action just FAILED and you need to fix it.

GOAL:
{goal}

RECENT HISTORY:
{history_summary}

FAILED ACTION:
{json.dumps(failed_action, indent=2)}

ERROR DETAILS:
- stdout: {error_info.get('stdout', 'N/A')}
- stderr: {error_info.get('stderr', 'N/A')}
- error: {error_info.get('error', 'N/A')}
- exit_code: {error_info.get('exit_code', 'N/A')}

HEALING ATTEMPT: {attempt_number} of {self.max_heal_attempts}

Analyze the failure and decide:

1. Is this a REAL action failure (command error, syntax error, connection issue)?
2. OR is this an EXPECTED test failure (verification failed because condition not met)?

IMPORTANT:
- If this is a VERIFICATION action that failed because the expected condition wasn't met,
  you should NOT try to fix it! This is the TEST RESULT, not an error.
- Only heal TECHNICAL failures (wrong syntax, wrong path, connection issues, etc.)

Common TECHNICAL failures to fix:
- Wrong PowerShell command syntax → Fix the command
- SSH connection failed → Try alternative connection method
- File path wrong → Use correct path
- Permission denied → Use sudo or different user
- Command not found → Use full path or install package
- Timeout → Increase timeout or simplify command
- Network unreachable → Check host/port/firewall

DO NOT FIX:
- Verification failures (test assertions that didn't pass)
- Expected business logic failures
- Missing resources that are supposed to be checked

Return ONLY valid JSON (no markdown, no explanation):
{{
    "should_retry": true/false,
    "give_up": false,
    "root_cause": "brief explanation of what went wrong",
    "corrected_action": {{
        "type": "...",
        "command": "...",
        "machine": "...",
        "params": {{...}}
    }},
    "reason": "what was changed and why"
}}

OR if the action cannot be fixed:
{{
    "should_retry": false,
    "give_up": true,
    "root_cause": "explanation",
    "reason": "why this cannot be fixed"
}}
"""
        
        result = self.llm.ask(prompt)
        print(f"\n[HEAL] AI Healer analyzing failure (attempt {attempt_number})...")
        print(f"[HEAL] Raw response:\n{result}\n")
        
        # Extract JSON from markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result, re.DOTALL)
        if json_match:
            result = json_match.group(1)
        
        # Clean up the result
        result = result.strip()
        
        try:
            healing_decision = json.loads(result)
            
            print(f"[HEAL] Root cause: {healing_decision.get('root_cause', 'Unknown')}")
            print(f"[HEAL] Should retry: {healing_decision.get('should_retry', False)}")
            print(f"[HEAL] Reason: {healing_decision.get('reason', 'N/A')}")
            
            if healing_decision.get('should_retry') and healing_decision.get('corrected_action'):
                print(f"[HEAL] Corrected action: {healing_decision['corrected_action']}")
            
            return healing_decision
            
        except json.JSONDecodeError as e:
            print(f"[HEAL ERROR] Failed to parse healing decision: {e}")
            print(f"[HEAL ERROR] Raw response was: {result}")
            # Return a safe fallback
            return {
                "should_retry": False,
                "give_up": True,
                "root_cause": "AI healer failed to parse response",
                "reason": "Could not generate corrected action"
            }
    
    def _summarize_history(self, history: list) -> str:
        """Create a concise summary of recent actions"""
        if not history:
            return "No previous actions"
        
        summary = []
        for i, entry in enumerate(history, 1):
            action = entry.get("action", {})
            result = entry.get("result", {})
            success = "✓" if result.get("success") else "✗"
            
            action_desc = f"{action.get('type', 'unknown')} on {action.get('machine', 'unknown')}"
            if action.get('command'):
                action_desc += f": {action['command'][:50]}"
            
            summary.append(f"{i}. {success} {action_desc}")
        
        return "\n".join(summary)
