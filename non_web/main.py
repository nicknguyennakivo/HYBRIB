from non_web.agent.llm_client import LLMClient
from non_web.agent.planner import Planner
from non_web.agent.action_planner import ActionPlanner
from non_web.agent.step_reasoner import StepReasoner
from non_web.agent.action_healer import ActionHealer
from non_web.executor.local_executor import LocalExecutor
from non_web.executor.ssh_executor import SSHExecutor
from non_web.executor.powershell_executor import PowerShellExecutor
from non_web.executor.command_router import CommandRouter
from non_web.coordinator.orchestrator import Orchestrator
from stage_hand.result import TestResult

from config.config import api_key


async def non_web_main(testcase: str = ""):
    llm = LLMClient(api_key)

    # AI Components
    planner = Planner(llm)
    action_planner = ActionPlanner(llm)
    reasoner = StepReasoner(llm)
    healer = ActionHealer(llm, max_heal_attempts=3)

    # Executors
    local = LocalExecutor()
    # Create SSH executor without credentials - they'll be provided via ssh_connect action
    ssh = SSHExecutor()
    # Create PowerShell executor for Windows remote management
    powershell = PowerShellExecutor()

    router = CommandRouter(local, ssh, powershell)

    # Orchestrator configuration options:
    # interactive_mode=False - Auto-stop on connection failures, continue on non-critical failures
    # interactive_mode=True - Ask user what to do when any action fails
    orchestrator = Orchestrator(
        planner, 
        reasoner, 
        router, 
        action_planner, 
        healer,
        interactive_mode=False  # Set to True to enable user prompts on failures
    )

    result = orchestrator.run(testcase)
    
    if result:
        print("\n✅ Test completed successfully")
        return TestResult(passed=True)
        
    else:
        print("\n❌ Test failed")
        return TestResult(passed=False)