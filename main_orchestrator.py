# runner/main.py
from parser.testcase_loader import TestCaseLoader
from runner.orchestrator import TestOrchestrator
from runner.testcase_executor import TestCaseExecutor
from parser.test import TestStatus



loader = TestCaseLoader(testcase_dir="./testcase")
executor = TestCaseExecutor()

orchestrator = TestOrchestrator(loader, executor)

import asyncio
import argparse

def _parse_args():
    parser = argparse.ArgumentParser(description="Run a DSL testcase")
    parser.add_argument(
        "--testcase", "-t",
        help="Testcase name (without .txt)",
        default="backup_vm_incremental",
    )
    return parser.parse_args()

async def main():
    args = _parse_args()
    testcase = args.testcase
    
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    status = await orchestrator.run_testcase(testcase)

    print("\n================ TEST RESULT ================")
    print(f"Testcase : {testcase}")

    if status == TestStatus.PASSED:
        print(f"Status   : {GREEN}{status.value.upper()}{RESET}")
    elif status == TestStatus.SKIPPED:
        print(f"Status   : {YELLOW}{status.value.upper()}{RESET}")
    else:
        print(f"Status   : {RED}{status.value.upper()}{RESET}")
    print("============================================\n")

    if status != TestStatus.PASSED:
        raise SystemExit(1)

asyncio.run(main())
