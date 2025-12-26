import asyncio
from typing import List

import json
import logging
import time
import re

from parser.dsl_models import Step
from stagehand import StagehandConfig, Stagehand
from stage_hand.result import TestResult, StepResult
from stage_hand.two_pharse_engine import TwoPhaseEngine  # Fixed import to match file name
from stage_hand.snapshot_store import SnapshotStore
from config.config import api_key


logger = logging.getLogger(__name__)

async def process(
    steps: List[Step],
    mode: str = "ai",
) -> TestResult:
    logger.info("🚀 Start Stagehand execution")

    test_failed = False
    failure_reason = None
    failed_step = None
    step_results: List[StepResult] = []

    stagehand = None

    try:
        # ─────────── SETUP ───────────
        with open("./storage/data.json", encoding="utf-8") as f:
            data_vars = json.load(f)
         # Init Stagehand
        config = StagehandConfig(
            env="LOCAL",
            model_name="google/gemini-2.5-flash",
            model_api_key=api_key,
            ignore_https_errors=True,
            verbose=2
        )

        stagehand = Stagehand(config)
        await stagehand.init()

        page = stagehand.page
        await page.set_viewport_size({"width": 1280, "height": 980})
        await page.goto(data_vars["url"])

        print("Loading snapshots...")

        snapshot_store = SnapshotStore("./storage/snapshots.json")
        engine = TwoPhaseEngine(snapshot_store)

        print("Snapshots loaded.")

        # ─────────── RUN (STAGEHAND ONLY) ───────────
        for idx, step in enumerate(steps, start=1):
            logger.info(f"[{idx}] {step.text}")
            print(f"Processing step {idx}: {step.text}")

            try:
                # instruction = _resolve_placeholders(step.text, data_vars)

                result = await _execute_single_step(
                    idx,
                    step.text,
                    page,
                    stagehand,
                    engine,
                    # step,          # pass Step object (important)
                )

                step_results.append(result)
                print(f"Step result: {result}")

                if result.status == "FAILED":
                    raise RuntimeError(result.error)
                # Small delay between actions
                await asyncio.sleep(2)

            except Exception as e:
                test_failed = True
                failed_step = idx
                failure_reason = str(e)
                logger.error(f"Step failed: {failure_reason}")

                step_results.append(
                    StepResult(
                        step=idx,
                        instruction=step.text,
                        status="FAILED",
                        error=failure_reason,
                    )
                )

                logger.error("❌ Stop Stagehand execution on failure")
                break

    finally:
        if stagehand:
            await stagehand.close()

    return TestResult(
        passed=not test_failed,
        failed_step=failed_step,
        reason=failure_reason,
        steps=step_results,
    )

async def _execute_single_step(
    step_no: int,
    instruction: str,
    page,
    stagehand,
    engine
) -> StepResult:

    try:
        result = None
        # Determine action type based on instruction
        is_click_action = instruction.lower().startswith('click') or 'click' in instruction.lower()
        is_expect_action = instruction.lower().startswith('expect')
        is_wait_action = instruction.lower().startswith('wait')
        is_press_action = instruction.lower().startswith('press') or 'press' in instruction.lower()

        if is_click_action: 
            result = await engine.act(stagehand, page, instruction)
        elif is_expect_action:
            result = await engine.observe(page, instruction)
        elif is_press_action:
            result = await engine.press(stagehand, page, instruction)
        elif is_wait_action:
            result = await execute_wait_step(page, instruction)
        else:
            result = await engine.act(stagehand, page, instruction)
        print(f"instruction:", instruction)
        print(f"Engine act result: {result}")

        if hasattr(result, "success") and not result.success:
            raise RuntimeError("ActResult.success = False")

        return StepResult(
            step=step_no,
            instruction=instruction,
            status="PASSED"
        )

    except Exception as primary_error:
        logger.warning(f"Primary action failed: {primary_error}")
        raise RuntimeError(f"Step failed after agent fallback: {primary_error}")
    
def parse_wait_condition(step: str) -> dict:
    match = re.search(r'not\s+"([^"]+)"', step, re.IGNORECASE)
    return {
        "forbiddenValue": match.group(1) if match else "Running"
    }

async def execute_wait_step(page, step: str):
    condition = parse_wait_condition(step)
    forbidden_value = condition["forbiddenValue"]

    # Treat @max_wait and @poll_interval as minutes
    # cfg = self.test_case.config or {}
    # max_wait_min = int(cfg.get("max_wait", 60))  # default 60 minutes
    # poll_interval_min = float(cfg.get("poll_interval", 3))  # default 3 minutes
    max_wait_min = 60  # default 60 minutes
    poll_interval_min = 3  # default 3 minutes

    timeout_ms = int(max_wait_min * 60 * 1000)  # minutes -> ms
    interval_ms = int(poll_interval_min * 60 * 1000)  # minutes -> ms

    start = time.time()
    last_status = None

    while (time.time() - start) * 1000 < timeout_ms:
        try:
            result = await page.observe(step)
        except Exception as e:
            logger.debug(f"observe failed: {e}; retrying...")
            await asyncio.sleep(interval_ms / 1000)
            continue

        if result is None or (isinstance(result, list) and len(result) == 0):
            logger.debug("No status element found, retrying...")
            await asyncio.sleep(interval_ms / 1000)
            continue

        # Extract status text from observe result (robust)
        status_text = await extract_status_text(page, result)
        if not status_text:
            logger.debug("Could not extract status text, retrying...")
            await asyncio.sleep(interval_ms / 1000)
            continue
        
        last_status = status_text
        logger.debug(f"Current status: {status_text}")
        
        # Check if status contains the forbidden value (e.g., "Running")
        is_still_forbidden = forbidden_value in status_text
        
        if not is_still_forbidden:
            # Status has changed from "Running" to something else (Success/Failed)
            logger.info(f"✓ Wait condition met. Status changed to: {status_text}")
            return

        # Status is still "Running", continue waiting
        logger.info(f"⏳ Still waiting... Current status: {status_text}")
        await asyncio.sleep(interval_ms / 1000)

    raise TimeoutError(
        f"Timeout waiting for backup job. Last status: {last_status}"
    )

async def extract_status_text(page, result):
    """Robustly extract visible status text from observe results.
    - Supports list/dict/single result
    - Tries direct text fields first, then uses selector to read inner text
    """
    if result is None:
        return None

    # Normalize to a list of items to inspect
    items = []
    if isinstance(result, dict) and 'elements' in result:
        items = result.get('elements') or []
    elif isinstance(result, list):
        items = result
    else:
        items = [result]

    # First pass: use any direct text fields provided by Stagehand
    for item in items:
        text = getattr(item, 'text', None) or getattr(item, 'statusText', None)
        if isinstance(text, str) and text.strip():
            return text.strip()

    # Second pass: if a selector is available, read the element text now (avoids stale node ids)
    for item in items:
        selector = getattr(item, 'selector', None)
        if not selector:
            continue
        try:
            elem = await page.query_selector(selector)
            if elem:
                text = await elem.inner_text()
                if text and text.strip():
                    return text.strip()
        except Exception as e:
            logger.debug(f"extract_status_text: failed to read selector '{selector}': {e}")
            continue
    return None




