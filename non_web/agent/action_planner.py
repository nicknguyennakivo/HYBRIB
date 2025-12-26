import json
import re
from datetime import datetime

class ActionPlanner:
    """
    Converts high-level plan steps into concrete action commands
    """
    def __init__(self, llm: "LLMClient"):
        self.llm = llm

    def create_action_list(self, goal: str, steps: list) -> list:
        """
        Convert plan steps into a list of concrete actions
        
        Returns list of action commands like:
        - ssh_connect("10.10.26.255", "root", "P@ssword123")
        - ssh_run("test -f /opt/data/report.txt && echo EXISTS || echo NOT_FOUND")
        - ssh_disconnect()
        - done
        """
        steps_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps)])
        
       
        prompt = f"""
You are an automation action planner.

GOAL:
{goal}

STEPS:
{steps_text}

Convert these high-level steps into a concrete list of ACTION COMMANDS.

Available actions:
- ssh_connect(host, username, password) 
  Connect to SSH server (Linux)

- ssh_run(command) 
  Run shell command over SSH

- ssh_disconnect() 
  Disconnect SSH

- powershell_connect(host, username, password) 
  Connect to a WINDOWS machine via PowerShell Remoting (WinRM)

- powershell_run(command) 
  Run PowerShell command on a REMOTE WINDOWS host (via WinRM)

- powershell_command(command) 
  Run PowerShell command LOCALLY on the execution machine
  (used for PowerCLI, vCenter, local PowerShell automation)

- powershell_disconnect() 
  Disconnect PowerShell remoting session

- local_run(command) 
  Run command locally (non-PowerShell)

- verify_output(expected_value) 
  Verify last command output contains expected value

- done 
  Mark completion

────────────────────────────────────
PLATFORM RULES (MANDATORY):

- VMware vCenter is NOT accessed via WinRM.
- NEVER use powershell_connect for vCenter.
- PowerCLI (Connect-VIServer, Get-VM, Disconnect-VIServer)
  MUST be executed using powershell_command.

- powershell_connect / powershell_run are ONLY for
  Windows hosts that explicitly support WinRM
  (e.g. Hyper-V, Windows Server).

────────────────────────────────────
IDENTITY & CREDENTIAL RULES (STRICT):

- Any username explicitly provided in the GOAL or STEPS is IMMUTABLE.
- Do NOT change, shorten, normalize, or replace usernames.
- Reuse usernames EXACTLY as provided, including domain prefixes.
- Reuse the SAME password wherever that username is used.
- Never substitute usernames like "Administrator" unless explicitly stated.
- Never invent placeholder passwords.
- Never omit passwords for non-interactive commands.

────────────────────────────────────
POWERCLI RULES (MANDATORY):

- Connect-VIServer MUST be non-interactive.
- Always pass username AND password explicitly.
- Do NOT rely on cached sessions or prompts.
- Import VMware.PowerCLI if required.

────────────────────────────────────

CRITICAL PLATFORM RULE:
- vCenter servers (VCSA) are Linux-based and DO NOT support WinRM.
- NEVER generate powershell_connect() targeting a vCenter server.
- PowerCLI commands must be executed locally or on a designated PowerCLI runner host.

────────────────────────────────────

OUTPUT CONTRACT RULE:
- Any action immediately followed by `verify_output` MUST emit plain text to STDOUT.

────────────────────────────────────

POWER SHELL OUTPUT RULE:
- PowerShell cmdlets that return objects (e.g. Get-VM, Get-Process, Get-Service)
  MUST explicitly convert results to text using ONE of:
    - Select-Object -ExpandProperty <Property>
    - Write-Output <value>

Return ONLY a valid JSON array (no markdown, no explanation):

[
  "action_command_1",
  "action_command_2",
  ...
  "done"
]

────────────────────────────────────
Example for Linux / SSH:

[
  "ssh_connect(\\"10.10.26.255\\", \\"root\\", \\"P@ssword123\\")",
  "ssh_run(\\"test -f /opt/data/report.txt && echo EXISTS || echo NOT_FOUND\\")",
  "verify_output(\\"EXISTS\\")",
  "ssh_disconnect()",
  "done"
]

────────────────────────────────────
Example for Hyper-V (Windows / WinRM):

[
  "powershell_connect(\\"10.10.20.103\\", \\"Administrator\\", \\"Automation@123\\")",
  "powershell_run(\\"Get-VM -Name 'QAVN_103_Ubuntu18x64_01'\\")",
  "verify_output(\\"QAVN_103_Ubuntu18x64_01\\")",
  "powershell_disconnect()",
  "done"
]

────────────────────────────────────
Example for VMware vCenter (PowerCLI):

[
  "powershell_command(\\"Import-Module VMware.PowerCLI -ErrorAction Stop\\")",
  "powershell_command(\\"Connect-VIServer -Server '10.10.10.20' -User 'Vcenter03.local\\\\administrator' -Password 'Automation@123' -ErrorAction Stop | Out-Null\\")",
  "powershell_command(\\"Get-VM -Name '4MB-11-replica-02-recovered' -ErrorAction Stop\\")",
  "verify_output(\\"4MB-11-replica-02-recovered\\")",
  "powershell_command(\\"Disconnect-VIServer -Confirm:$false\\")",
  "done"
]
"""

        
        result = self.llm.ask(prompt)
        print(f"[DEBUG] [{datetime.now().strftime('%H:%M:%S')}] ActionPlanner raw response:\n{result}\n")
        
        # Extract JSON from markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', result, re.DOTALL)
        if json_match:
            result = json_match.group(1)
        
        # Clean up the result
        result = result.strip()
        
        try:
            actions = json.loads(result)
            print(f"[DEBUG] [{datetime.now().strftime('%H:%M:%S')}] Generated action list:")
            for i, action in enumerate(actions, 1):
                print(f"  {i}. {action}")
            print()
            return actions
        except json.JSONDecodeError as e:
            print(f"[ERROR] [{datetime.now().strftime('%H:%M:%S')}] Failed to parse action list JSON: {e}")
            print(f"[ERROR] Raw response was: {result}")
            raise
