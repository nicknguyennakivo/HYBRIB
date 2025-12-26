# runner/testcase_executor.py
import json

from matplotlib.pyplot import step
from parser.test import TestStatus
from parser.dsl_models import TestCase
from stage_hand.stagehand_runner import process
import logging
from non_web.main import non_web_main

logger = logging.getLogger(__name__)

class TestCaseExecutor:

    async def execute(self, testcase: TestCase) -> TestStatus:
        logger.info(f"Running PRE for {testcase.name}")
        try:
            await self.run_pre(testcase.pre)
            await self.run_stagehand(testcase.run)
            run_passed = True
        except Exception as e:
            logger.error(f"RUN failed: {e}")
            run_passed = False
        finally:
            finally_ok = await self.run_finally(testcase.finally_)

        if run_passed and finally_ok:
            logger.info(f"✅ PASSED: {testcase.name}")
            return TestStatus.PASSED

        logger.error(f"❌ FAILED: {testcase.name}")
        return TestStatus.FAILED

    async def run_pre(self, steps):
        print("Running PRE steps...")
        try:
            result = await non_web_main(steps)
            return result
        except Exception as e:
            logger.error(f"PRE steps failed: {e}")

        # real PRE logic here

    async def run_stagehand(self, steps):
        # page.act / observe here
        print("Running STAGEHAND steps...")
        try:
            result = await process(steps, "ai")
            return result.passed  # True if all steps passed
        except Exception as e:
            logger.error(f"Stagehand steps failed: {e}")
            return False

    async def run_finally(self, steps):
        print("Running FINALLY steps...")
        return True

