import paramiko

class SSHExecutor:
    def __init__(self, host=None, user=None, password=None):
        self.host = host
        self.user = user
        self.password = password
        self.ssh_client = None
        self.is_connected = False

    def connect(self, host=None, user=None, password=None):
        """Establish SSH connection"""
        # Use provided credentials or fall back to instance defaults
        host = host or self.host
        user = user or self.user
        password = password or self.password
        
        if not all([host, user, password]):
            return {"success": False, "error": "Missing SSH credentials"}
        
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(host, username=user, password=password, timeout=10)
            
            self.host = host
            self.user = user
            self.password = password
            self.is_connected = True
            
            return {
                "success": True,
                "stdout": f"Connected to {host}",
                "output": f"Connected to {host}"
            }
        except Exception as e:
            self.is_connected = False
            return {"success": False, "error": f"SSH connection failed: {str(e)}"}

    def disconnect(self):
        """Close SSH connection"""
        if self.ssh_client:
            try:
                self.ssh_client.close()
                self.is_connected = False
                return {
                    "success": True,
                    "stdout": "Disconnected from SSH",
                    "output": "Disconnected from SSH"
                }
            except Exception as e:
                return {"success": False, "error": f"Disconnect error: {str(e)}"}
        return {"success": True, "stdout": "Already disconnected"}

    def run(self, command):
        """Execute command on SSH server"""
        # If not connected, try to connect with instance credentials
        if not self.is_connected:
            if self.host and self.user and self.password:
                connect_result = self.connect()
                if not connect_result.get("success"):
                    return connect_result
            else:
                return {"success": False, "error": "Not connected to SSH server"}
        
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            
            stdout_text = stdout.read().decode().strip()
            stderr_text = stderr.read().decode().strip()
            
            return {
                "success": exit_status == 0,
                "stdout": stdout_text,
                "stderr": stderr_text,
                "exit_code": exit_status
            }
        except Exception as e:
            return {"success": False, "error": f"Command execution failed: {str(e)}"}
