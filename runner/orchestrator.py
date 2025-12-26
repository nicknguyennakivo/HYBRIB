from typing import Dict
from parser.test import TestCase, TestStatus
import logging

logger = logging.getLogger(__name__)
class TestOrchestrator:

    def __init__(self, loader, executor,fail_fast: bool = True):
        """
        loader   → TestCaseLoader
        executor → TestCaseExecutor (PRE/RUN/FINALLY runner)
        """
        self.loader = loader
        self.executor = executor
        self.results: Dict[str, TestStatus] = {}
        self.stack = set()  # circular dependency protection
        self.fail_fast = fail_fast

    async def run_testcase(self, testcase_name: str) -> TestStatus:
        # Already executed → reuse result
        if testcase_name in self.results:
            return self.results[testcase_name]

        # Circular dependency detection
        if testcase_name in self.stack:
            raise RuntimeError(f"Circular dependency detected: {testcase_name}")
        try:
            self.stack.add(testcase_name)

            testcase = self.loader.load(testcase_name)

            # 1️⃣ RUN DEPENDENCIES FIRST
            for dep in testcase.depends_on:
                dep_status = await self.run_testcase(dep)

                if dep_status != TestStatus.PASSED:
                    self.results[testcase_name] = TestStatus.SKIPPED
                    if self.fail_fast:
                        raise RuntimeError(f"Dependency failed: {dep}")
                    return TestStatus.SKIPPED

            # 2️⃣ RUN THIS TESTCASE
            status = await self._execute_testcase(testcase)
            if self.fail_fast and status != TestStatus.PASSED:
                raise RuntimeError(f"Testcase failed: {testcase_name}")

            self.results[testcase_name] = status
            return status
        finally:
            if testcase_name in self.stack:
                self.stack.remove(testcase_name)
    
    async def _execute_testcase(self, testcase: TestCase) -> TestStatus:
        logger.info(f"▶ Executing testcase: {testcase.name}")
        print(f"testcase : {testcase}")

        try:
            # 1️⃣ PRE steps
            if testcase.pre:
                print("Running PRE steps...")
                pre_result = await self.executor.run_pre(testcase.pre)
                if not pre_result.passed:
                    logger.error(f"PRE steps failed for testcase: {testcase.name}")
                    return TestStatus.FAILED

            # 2️⃣ STAGEHAND steps
            if testcase.run:
                print("Running STAGEHAND steps...")
                stagehand_result = await self.executor.run_stagehand(testcase.run)
                if not stagehand_result:
                    logger.error(f"STAGEHAND steps failed for testcase: {testcase.name}")
                    return TestStatus.FAILED

            # 3️⃣ FINALLY steps
            if testcase.finally_:
                print("Running FINALLY steps...")
                finally_result = await self.executor.run_finally(testcase.finally_)
                if not finally_result:
                    logger.error(f"FINALLY steps failed for testcase: {testcase.name}")
                    return TestStatus.FAILED

            return TestStatus.PASSED

        except Exception as e:
            logger.exception(f"Testcase execution error: {testcase.name} → {e}")
            return TestStatus.FAILED

