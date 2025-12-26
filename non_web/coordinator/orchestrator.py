class Orchestrator:
    def __init__(self, planner, reasoner, executor, action_planner=None, action_healer=None, interactive_mode=False):
        self.planner = planner
        self.reasoner = reasoner
        self.executor = executor
        self.action_planner = action_planner
        self.action_healer = action_healer
        self.interactive_mode = interactive_mode  # Ask user on failures

    def run(self, testcase_text: str):
        # 1) Build plan
        plan = self.planner.create_plan(testcase_text)
        
        goal = plan["goal"]
        steps = plan["steps"]
        
        # 2) Generate action list if action_planner is available
        if self.action_planner:
            action_list = self.action_planner.create_action_list(goal, testcase_text)
            self.reasoner.action_list = action_list
            self.reasoner.current_action_index = 0
        
        history = []
        last_result = {"info": "start"}

        while True:
            # 2) AI decides next action
            decision = self.reasoner.next_action(goal, history, last_result)

            if decision.get("status") == "goal_achieved":
                print("🎉 GOAL ACHIEVED!")
                return True

            action = decision["action"]
            print(f"\n▶ Executing action: {action}")

            # 3) Execute with self-healing loop
            result = self._execute_with_healing(action, goal, history)
            
            # Print result details
            if result.get("success"):
                output = result.get('output') or result.get('stdout') or 'OK'
                print(f"✓ Success: {output}")
            else:
                error = result.get('error') or result.get('output') or 'Unknown error'
                print(f"✗ Failed: {error}")
                # Also print stderr if available
                if result.get('stderr'):
                    print(f"  stderr: {result.get('stderr')}")

            # 4) Save history
            history.append({
                "action": action,
                "result": result
            })

            last_result = result

            # Handle failures based on action type and mode
            if not result.get("success"):
                should_continue = self._handle_failure(action, result, history)
                if not should_continue:
                    return False
            
            # Special handling for verification failures (always stop)
            if action.get("type") == "verify_output" and not result.get("success"):
                print("\n❌ VERIFICATION FAILED - Test Failed!")
                print(f"   {result.get('error', 'Unknown error')}")
                return False
    
    def _execute_with_healing(self, action: dict, goal: str, history: list) -> dict:
        """
        Execute an action with self-healing capability.
        If it fails, try to heal and retry.
        
        NOTE: Verification actions (verify_output, verify_*) should NOT be healed,
        as they are checking expected conditions, not performing actions.
        """
        # First attempt
        result = self.executor.execute(action)
        
        # If successful or no healer available, return immediately
        if result.get("success") or not self.action_healer:
            return result
        
        # IMPORTANT: Do NOT heal verification actions!
        # Verification failures mean the test condition was not met,
        # not that the action itself was broken
        action_type = action.get("type", "")
        if action_type in ["verify_output", "verify"]:
            print(f"\n⚠️ Verification action failed - this is a test failure, not an action error")
            return result
        
        # If failed and healer is available, try to heal
        max_attempts = self.action_healer.max_heal_attempts
        
        for attempt in range(1, max_attempts + 1):
            print(f"\n🔧 SELF-HEALING: Action failed, attempting to heal (attempt {attempt}/{max_attempts})...")
            
            # Ask the healer to analyze and fix
            healing_decision = self.action_healer.heal_action(
                failed_action=action,
                error_info=result,
                goal=goal,
                history=history,
                attempt_number=attempt
            )
            
            # Check if we should give up
            if healing_decision.get("give_up") or not healing_decision.get("should_retry"):
                print(f"🔧 HEALING: Cannot fix this action. Reason: {healing_decision.get('reason', 'Unknown')}")
                return result  # Return the original failure
            
            # Get the corrected action
            corrected_action = healing_decision.get("corrected_action")
            if not corrected_action:
                print(f"🔧 HEALING: No corrected action provided")
                return result
            
            # Try the corrected action
            print(f"🔧 HEALING: Trying corrected action: {corrected_action}")
            result = self.executor.execute(corrected_action)
            
            # If it succeeded, we're done!
            if result.get("success"):
                print(f"✅ HEALING SUCCESS: Corrected action worked!")
                return result
            
            # Otherwise, continue to next healing attempt
            print(f"🔧 HEALING: Corrected action still failed, will try again...")
        
        # If we've exhausted all healing attempts
        print(f"❌ HEALING EXHAUSTED: Could not fix action after {max_attempts} attempts")
        return result  # Return the last failure
    
    def _handle_failure(self, action: dict, result: dict, history: list) -> bool:
        """
        Handle action failures - use AI to decide whether to continue or stop.

        Returns:
            True - Continue with next action
            False - Stop the test
        """
        action_type = action.get("type", "unknown")
        error = result.get('error') or result.get('output') or 'Unknown error'

        # Print failure details
        print(f"\n⚠️ ACTION FAILED: {action_type}")
        print(f"   Error: {error}")
        if result.get('stderr'):
            print(f"   Stderr: {result.get('stderr')}")

        # If interactive mode, ask user
        if self.interactive_mode:
            print(f"\n❓ What would you like to do?")
            print(f"   1. Continue with next action (skip this failure)")
            print(f"   2. Stop the test")

            try:
                choice = input("Enter choice (1 or 2): ").strip()
                if choice == "1":
                    print("⏭️  Continuing with next action...")
                    return True
                else:
                    print("🛑 Stopping test as requested")
                    return False
            except (KeyboardInterrupt, EOFError):
                print("\n🛑 Stopping test (interrupted)")
                return False
        else:
            # Use AI to decide whether to continue or stop
            return self._ai_decide_on_failure(action, result, history)
    
    def _ai_decide_on_failure(self, action: dict, result: dict, history: list) -> bool:
        """
        Use AI to intelligently decide whether to continue or stop after a failure.
        
        Returns:
            True - Continue with next action
            False - Stop the test
        """
        if not self.planner or not hasattr(self.planner, 'llm'):
            # Fallback: Stop on critical failures, continue on others
            is_critical = action.get("type") in ["ssh_connect", "powershell_connect"]
            return not is_critical
        
        print(f"\n🤔 AI analyzing failure to decide next step...")
        
        # Get remaining actions from reasoner
        remaining_actions = []
        if hasattr(self.reasoner, 'action_list') and hasattr(self.reasoner, 'current_action_index'):
            remaining_count = len(self.reasoner.action_list) - self.reasoner.current_action_index
            remaining_actions = self.reasoner.action_list[self.reasoner.current_action_index:self.reasoner.current_action_index + 3]
        
        import json
        prompt = f"""
You are an AI test execution advisor. An action just FAILED and you need to decide whether to continue the test or stop.

FAILED ACTION:
{json.dumps(action, indent=2)}

ERROR DETAILS:
- Error: {result.get('error', 'N/A')}
- Stdout: {result.get('stdout', 'N/A')}
- Stderr: {result.get('stderr', 'N/A')}
- Exit Code: {result.get('exit_code', 'N/A')}

REMAINING ACTIONS ({remaining_count if 'remaining_count' in locals() else 'unknown'} left):
{json.dumps(remaining_actions[:3] if remaining_actions else ['No more actions'], indent=2)}

RECENT HISTORY:
{self._summarize_recent_history(history[-3:])}

DECISION CRITERIA:
1. If this is a CONNECTION failure (ssh_connect, powershell_connect):
   - STOP: The connection is required for all subsequent actions
   - Exception: If remaining actions don't need this connection, can continue

2. If this is a COMMAND execution failure:
   - CONTINUE: If remaining actions are independent
   - STOP: If remaining actions depend on this action's result

3. If remaining actions are all disconnect/cleanup:
   - CONTINUE: To properly clean up

4. If no remaining actions:
   - STOP: Nothing left to do

Return ONLY valid JSON (no markdown):
{{
    "should_continue": true/false,
    "reason": "brief explanation of why continue or stop",
    "suggestion": "what the user should do to fix this issue"
}}
"""
        
        try:
            import re
            response = self.planner.llm.ask(prompt)
            print(f"[AI DECISION] Raw response:\n{response}\n")
            
            # Extract JSON
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                response = json_match.group(1)
            response = response.strip()
            
            decision = json.loads(response)
            
            should_continue = decision.get("should_continue", False)
            reason = decision.get("reason", "No reason provided")
            suggestion = decision.get("suggestion", "Check logs for details")
            
            print(f"[AI DECISION] Should continue: {should_continue}")
            print(f"[AI DECISION] Reason: {reason}")
            print(f"[AI DECISION] Suggestion: {suggestion}")
            
            if should_continue:
                print(f"\n⏭️  AI decided to CONTINUE with next action")
                print(f"   Reason: {reason}")
            else:
                print(f"\n🛑 AI decided to STOP the test")
                print(f"   Reason: {reason}")
                print(f"\n💡 Suggestion: {suggestion}")
            
            return should_continue
            
        except Exception as e:
            print(f"[AI DECISION ERROR] Failed to get AI decision: {e}")
            # Fallback: Stop on critical failures
            is_critical = action.get("type") in ["ssh_connect", "powershell_connect"]
            if is_critical:
                print(f"🛑 Fallback decision: STOP (critical failure)")
                return False
            else:
                print(f"⏭️  Fallback decision: CONTINUE (non-critical failure)")
                return True
    
    def _summarize_recent_history(self, history: list) -> str:
        """Summarize recent history for AI decision making"""
        if not history:
            return "No previous actions"
        
        summary = []
        for i, entry in enumerate(history, 1):
            action = entry.get("action", {})
            result = entry.get("result", {})
            success = "✓" if result.get("success") else "✗"
            action_type = action.get("type", "unknown")
            summary.append(f"{i}. {success} {action_type}")
        
        return "\n".join(summary)
