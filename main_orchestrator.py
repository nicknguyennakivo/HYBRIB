# runner/main.py
from parser.testcase_loader import TestCaseLoader
from runner.orchestrator import TestOrchestrator
from runner.testcase_executor import TestCaseExecutor
from parser.test import TestStatus



loader = TestCaseLoader(testcase_dir="./testcase")
executor = TestCaseExecutor()

orchestrator = TestOrchestrator(loader, executor)

import asyncio

async def main():
    status = await orchestrator.run_testcase("backup_vm_incremental.txt")

    if status != TestStatus.PASSED:
        raise SystemExit(1)

asyncio.run(main())
