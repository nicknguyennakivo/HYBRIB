from matplotlib.pyplot import step
from stage_hand.result import EngineActResult
from stage_hand.snapshot_store import SnapshotStore
from stage_hand.selector_snapshot import SelectorSnapshot
from stagehand import  ObserveResult
from config.config import api_key

import string
import logging

logger = logging.getLogger(__name__)

class TwoPhaseEngine:
    def __init__(self, store: SnapshotStore):
        self.store = store

    async def press(self, stagehand, page, step: str):
        # For simplicity, assume step is something like "Press Enter"
        key = step.replace("Press ", "").strip()
        key = key.strip(string.punctuation)
        print(f"Press key: '{key}'")
        # Build snapshot
        snapshot = SelectorSnapshot(
            step=step,
            selector=None,               # no DOM selector for keyboard press
            method="press",
            arguments=[key],
            description=f"Keyboard action: {step}"
        )
        # Store snapshot for future replay
        self.store.put(snapshot)

        # Execute keyboard press
        await page.keyboard.press(key)

        return EngineActResult(
            success=True,
            used_agent=False,
            raw=key
        )


    async def act(self, stagehand, page, step: str):
        # 1️⃣ Replay (no LLM)
        snapshot = self.store.get(step)
        # if snapshot:
        #     try:
        #         await self.replay_snapshot(page, snapshot)
        #         return "replay"
        #     except Exception:
        #         pass  # selector drift → heal

        # 2️⃣ Observe (LLM)
        result: ObserveResult = await page.observe(step)
        print(f"ObserveResult: {result}")
        if not result:
            agent_act_result = await self.agent_act(page, step, stagehand)
            if not agent_act_result.success:
                return EngineActResult(
                    success=False,
                    used_agent=True,
                    error="Agent recovery failed",
                    raw=agent_act_result
                )
             # `used_agent` contains the actions log
            agent_actions = agent_act_result.used_agent
            # Find the first 'click' action with x and y coordinates
            click_action = next(
                (a for a in agent_actions if a.get('type') == 'click' and 'x' in a and 'y' in a),
                None
            )
            if not click_action:
                raise AssertionError(f"No click action found in agent_act_result for step: {step}")
            
            snapshot = SelectorSnapshot(
                step=step,
                selector=None,
                method='click',
                arguments=[click_action['x'], click_action['y']],
                description="Recovered by agent_act"
            )
            self.store.put(snapshot)
            return EngineActResult(
                success=True,
                used_agent=True,
                raw=agent_act_result
            )

        # 3️⃣ Snapshot
        snapshot = self.snapshot_from_observe(step, result)
        print(f"Snapshot: {snapshot}")
        self.store.put(snapshot)

        # 4️⃣ Act using ObserveResult (exact node)
        observe_results = self.normalize_act_result(result)  # returns a list
        if not observe_results:
            raise RuntimeError(f"No observe results found for step: {step}")
        observe_result = observe_results[0]  # single ObserveResult
        print(f"ObserveResult for act: {observe_result}")
        
        result = await page.act(observe_result)
        return EngineActResult(
            success=True,
            used_agent=False,
            raw=result
        )

    async def observe(self, page, step: str):
        """
        Observe step with cache-first behavior.
        Returns:
        - ObserveResult (fresh, AI)
        - or SelectorSnapshot (cached, no AI)
        """

        # # 1️⃣ Replay observe (NO AI)
        # snapshot = self.store.get(step)
        # if snapshot:
        #     el = await page.query_selector(snapshot.selector)
        #     if el:
        #         return snapshot, "replay"

        # 2️⃣ Fresh observe (AI)
        try:
            raw_result = await page.observe(step)
            observe_result = self.normalize_observe_result(raw_result, step)

            snapshot = self.snapshot_from_observe(step, observe_result)
            self.store.put(snapshot)
            return EngineActResult(
                success=True,
                used_agent=True,
                raw=observe_result
            )
        except Exception as e:
             return EngineActResult(
                success=False,
                used_agent=True,
                error=str(e)
            )
    async def replay_snapshot(self, page, snapshot: SelectorSnapshot):
        el = await page.query_selector(snapshot.selector)
        if not el:
            raise RuntimeError(
                f"Replay failed – selector not found: {snapshot.selector}"
            )

        method = snapshot.method
        args = snapshot.arguments

        if not hasattr(el, method):
            raise RuntimeError(f"Unsupported method: {method}")

        await getattr(el, method)(*args)

    def snapshot_from_observe(self, step: str, result: ObserveResult) -> SelectorSnapshot:
        result = self.normalize_observe_result(result, step)

        print(f"ObserveResult inside snapshot_from_observe: {result}")
        print(f"Method inside snapshot_from_observe: {result.method}")

        if not result.method:
            raise AssertionError(
                f"No method inferred by observe for step: {step}"
            )

        return SelectorSnapshot(
            step=step,
            selector=result.selector,
            method=result.method,
            arguments=result.arguments or [],
            description=result.description,
        )
    def normalize_observe_result(self, result, step: str) -> ObserveResult:
        """
        Normalize Stagehand observe output to a single ObserveResult
        """
        if not result:
            raise AssertionError(f"Observe failed: {step}")

        if isinstance(result, list):
            if len(result) == 0:
                raise AssertionError(f"Observe returned empty list: {step}")
            return result[0]

        return result

    async def agent_act(self, page, step: str, stagehand):
        """
        Execute the step via agent.execute(), then create and store a snapshot
        so the two-phase engine can reuse it later.
        """
        print(f"Fallback agent executing step: {step}")

        # Build a context-aware instruction for the agent
        agent_instruction = f"""
    You are a QA automation recovery agent.

    The following UI action just failed:

    Action: {step}

    Your task is to recover and complete ONLY the failed action above.

    Rules (must follow strictly):
    - Treat the action as complete as soon as the immediate intent of the action is satisfied.
    - Do NOT infer, chain, or continue to follow-up steps.
    - Do NOT perform any action that represents a logical "next step" beyond the original action.
    - If the action opens a menu, dialog, dropdown, or wizard, STOP once it is visible.
    - If the action is ambiguous, choose the minimal interaction that best matches the action text.

    Recovery strategies (try in order, up to max_steps):
    1. Locate equivalent elements (text, icon, role, aria-label, tooltip, proximity)
    2. Check for alternative UI representations (icon vs text, toolbar vs menu)
    3. Check state issues (hidden, disabled, loading, collapsed, modal)
    4. Scroll to reveal the target
    5. Try a different interaction method (keyboard, focus + Enter, click by coordinates)
    6. Interact with required parent or wrapper elements ONLY if necessary to perform the action

    STOP IMMEDIATELY after the single action is completed.

    If the action cannot be completed, provide diagnostics ONLY (do not act further):
    - What elements ARE visible
    - What the page state appears to be
    - Why the target action cannot be completed
    - What minimal alternative action might enable it

    Do not proceed to any other steps.
    """
        # Initialize agent with computer use model for advanced reasoning
        agent = stagehand.agent(
            model="gemini-2.5-computer-use-preview-10-2025",
            instructions="You are an intelligent QA recovery agent. Use advanced reasoning to complete failed UI actions.",
            options={"apiKey": api_key}
        )
        
        # Use agent.execute for multi-step reasoning and recovery
        logger.debug(f"Agent instruction: {agent_instruction}")
        # 1️⃣ Execute the step with agent
        agent_result = await agent.execute(
            instruction=agent_instruction,
            max_steps=10,  # Allow up to 10 reasoning steps
            auto_screenshot=True,
            highlightCursor=False
        )
        print(f"Agent execute result for step '{step}': {agent_result}")
        # Check if agent succeeded
        # agent.execute() returns an ExecuteResult object with actions list
        agent_actions_log = []
        agent_succeeded = False
        agent_diagnostics = None
        
        if hasattr(agent_result, 'actions'):
            # ExecuteResult object from agent.execute()
            actions_count = len(agent_result.actions)
            logger.info(f"Agent executed {actions_count} actions during recovery")
            
            # Check if agent performed any actions
            if actions_count > 0:
                # Log the actions taken
                for idx, action in enumerate(agent_result.actions, 1):
                    action_info = str(action)
                    logger.debug(f"  Agent action {idx}: {action_info}")
                
                # Check the last action for success
                last_action = agent_result.actions[-1]
                print(f"Last agent action: {last_action}")
                
                # Check for success indicators in the action
                if hasattr(last_action, 'success'):
                    agent_succeeded = last_action.success
                elif hasattr(last_action, 'status'):
                    agent_succeeded = last_action.status == 'success'
                else:
                    # If no explicit success indicator, consider it successful if actions were taken
                    agent_succeeded = True
                
                logger.info(f"Agent recovery result: {'Success' if agent_succeeded else 'Failed'}")
            else:
                logger.warning("Agent executed 0 actions - no recovery attempted")
                agent_diagnostics = "Agent could not find any way to complete the action"
        else:
            # Fallback for unexpected result format
            logger.warning(f"Unexpected agent result format: {type(agent_result)}")
            agent_result_str = str(agent_result)
            
            # Check for explicit failure indicators
            if "success=False" in agent_result_str or "No observe results found" in agent_result_str:
                logger.error(f"❌ Agent fallback failed - detected failure in result: {agent_result_str}")
                agent_succeeded = False
            elif agent_result:
                # Non-null result without clear failure indicator - consider partial success
                agent_succeeded = True
        
        if agent_succeeded:
            logger.info(f"✓ Agent.execute() fallback succeeded!")
            
            # Serialize agent actions for logging
           
            if hasattr(agent_result, 'actions'):
                for action in agent_result.actions:
                    if hasattr(action, "model_dump"):
                        agent_actions_log.append(action.model_dump())
                    elif hasattr(action, "__dict__"):
                        agent_actions_log.append(action.__dict__)
                    else:
                        agent_actions_log.append(str(action))
            return EngineActResult(success=True, used_agent=agent_actions_log)

        else:
            logger.error(f"❌ Agent.execute() fallback failed")
            return EngineActResult(success=False, used_agent=agent_diagnostics)
        
    def normalize_act_result(self,result):
        """
        Always return a list of ObserveResult objects, even if result is EngineActResult
        """
        if isinstance(result, EngineActResult):
            if hasattr(result.raw, '__iter__') and not isinstance(result.raw, str):
                return list(result.raw)
            return [result.raw] if result.raw else []
        elif isinstance(result, list):
            return result
        return [result]