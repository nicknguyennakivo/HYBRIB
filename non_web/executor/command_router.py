class CommandRouter:
    def __init__(self, local_executor, ssh_executor=None, powershell_executor=None):
        self.local = local_executor
        self.ssh = ssh_executor
        self.powershell = powershell_executor
        self.ssh_connected = False
        self.powershell_connected = False
        self.last_output = None  # Track last command output

    def execute(self, action):
        action_type = action.get("type", "command")
        machine = action.get("machine")
        
        # Handle SSH actions
        if action_type == "ssh_connect":
            params = action.get("params", {})
            if self.ssh:
                result = self.ssh.connect(
                    host=params.get("host"),
                    user=params.get("username"),
                    password=params.get("password")
                )
                if result.get("success"):
                    self.ssh_connected = True
                self.last_output = result
                return result
            return {"success": False, "error": "SSH executor not configured"}
        
        elif action_type == "ssh_disconnect":
            if self.ssh:
                result = self.ssh.disconnect()
                self.ssh_connected = False
                self.last_output = result
                return result
            return {"success": True, "stdout": "No SSH connection to disconnect"}
        
        # Handle PowerShell actions
        elif action_type == "powershell_connect":
            params = action.get("params", {})
            if self.powershell:
                result = self.powershell.connect(
                    remote_host=params.get("host"),
                    username=params.get("username"),
                    password=params.get("password")
                )
                if result.get("success"):
                    self.powershell_connected = True
                self.last_output = result
                return result
            return {"success": False, "error": "PowerShell executor not configured"}
        
        elif action_type == "powershell_disconnect":
            if self.powershell:
                result = self.powershell.disconnect()
                self.powershell_connected = False
                self.last_output = result
                return result
            return {"success": True, "stdout": "No PowerShell connection to disconnect"}
        
        elif action_type == "verify_output":
            # Verify the last command's output against expected value
            expected = action.get("params", {}).get("expected", "")
            
            if self.last_output is None:
                return {
                    "success": False,
                    "error": "No previous output to verify",
                    "output": "No previous output"
                }
            
            # Get the actual output from last command
            actual_output = self.last_output.get("stdout", "").strip()
            
            # Check if expected value is in the output
            if expected in actual_output:
                return {
                    "success": True,
                    "output": f"✓ Output verification passed: Expected '{expected}' found in '{actual_output}'",
                    "stdout": f"Verified: {expected}",
                    "info": "output_verified"
                }
            else:
                return {
                    "success": False,
                    "error": f"Output verification failed: Expected '{expected}', but got '{actual_output}'",
                    "output": f"✗ Expected '{expected}' not found in '{actual_output}'",
                    "stdout": actual_output
                }

        # Default command execution
        if machine == "local":
            command = action.get("command", "")
            result = self.local.run(command)
            self.last_output = result
            return result

        elif machine == "ssh":
            if not self.ssh:
                return {"success": False, "error": "SSH not configured"}
            command = action.get("command", "")
            result = self.ssh.run(command)
            self.last_output = result
            return result
        
        elif machine == "powershell" or machine == "windows":
            if not self.powershell:
                return {"success": False, "error": "PowerShell executor not configured"}
            command = action.get("command", "")
            # Check if this should be run remotely
            remote = self.powershell_connected and action.get("remote", True)
            result = self.powershell.run(command, remote=remote)
            self.last_output = result
            return result
        elif action_type == "powershell_command":
            if not self.powershell:
                return {"success": False, "error": "PowerShell executor not configured"}

            command = action.get("command", "")
            remote = self.powershell_connected

            result = self.powershell.run(command, remote=remote)
            self.last_output = result
            return result
        elif action_type == "powershell_capability":
            result = self.powershell.run(command, remote=False)
            self.last_output = result

            if not result.get("stdout"):
                return {
                    "success": False,
                    "error": "Required PowerShell capability missing",
                    "fatal": True
                }

            return result
        else:
            return {"success": False, "error": f"Unknown action type or machine: {action_type}/{machine}"}
