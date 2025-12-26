import subprocess
import json

class PowerShellExecutor:
    """
    Executor for Windows PowerShell commands and remote PowerShell sessions (WinRM)
    """
    def __init__(self, remote_host=None, username=None, password=None):
        self.remote_host = remote_host
        self.username = username
        self.password = password
        self.is_connected = False
        self.credential_created = False

    def connect(self, remote_host=None, username=None, password=None):
        """
        Prepare PowerShell credential for remote connection
        This doesn't actually connect, but prepares the credential object
        """
        self.remote_host = remote_host or self.remote_host
        self.username = username or self.username
        self.password = password or self.password
        
        if not all([self.remote_host, self.username, self.password]):
            return {"success": False, "error": "Missing PowerShell remote credentials"}
        
        try:
            # Test if we can reach the remote host
            test_cmd = f'Test-WSMan -ComputerName {self.remote_host} -ErrorAction Stop'
            result = self._run_local_powershell(test_cmd)
            
            if result.get("success"):
                self.is_connected = True
                self.credential_created = True
                return {
                    "success": True,
                    "stdout": f"PowerShell remoting available on {self.remote_host}",
                    "output": f"Connected to {self.remote_host} via WinRM"
                }
            else:
                return {
                    "success": False,
                    "error": f"Cannot connect to {self.remote_host} via WinRM. Error: {result.get('error')}"
                }
        except Exception as e:
            return {"success": False, "error": f"PowerShell connection failed: {str(e)}"}

    def disconnect(self):
        """Disconnect from remote PowerShell session"""
        self.is_connected = False
        self.credential_created = False
        return {
            "success": True,
            "stdout": "Disconnected from PowerShell remote session",
            "output": "Disconnected from PowerShell remote session"
        }

    def run(self, command, remote=False):
        """
        Execute PowerShell command locally or remotely
        
        Args:
            command: PowerShell command to execute
            remote: If True, execute on remote host via Invoke-Command
        """
        if remote:
            if not self.is_connected or not all([self.remote_host, self.username, self.password]):
                return {"success": False, "error": "Not connected to remote PowerShell host"}
            
            return self._run_remote_powershell(command)
        else:
            return self._run_local_powershell(command)

    def _run_local_powershell(self, command):
        """Run PowerShell command locally"""
        try:
            # Escape double quotes in the command
            ps_command = [
                'powershell.exe',
                '-NoProfile',
                '-NonInteractive',
                '-Command',
                command
            ]
            
            result = subprocess.run(
                ps_command,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "PowerShell command timed out"}
        except Exception as e:
            return {"success": False, "error": f"PowerShell execution failed: {str(e)}"}

    def _run_remote_powershell(self, command):
        """Run PowerShell command on remote host via Invoke-Command"""
        try:
            # Build the Invoke-Command with credential
            # We need to pass the password securely
            ps_script = f'''
$Username = "{self.username}"
$Password = ConvertTo-SecureString "{self.password}" -AsPlainText -Force
$Cred = New-Object System.Management.Automation.PSCredential ($Username, $Password)

Invoke-Command -ComputerName {self.remote_host} -Credential $Cred -ScriptBlock {{
    {command}
}} -ErrorAction Stop
'''
            
            result = subprocess.run(
                ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', ps_script],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Remote PowerShell command timed out"}
        except Exception as e:
            return {"success": False, "error": f"Remote PowerShell execution failed: {str(e)}"}
