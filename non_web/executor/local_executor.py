import subprocess

class LocalExecutor:
    def run(self, command):
        try:
            p = subprocess.run(command, shell=True, capture_output=True, text=True)
            return {
                "success": p.returncode == 0,
                "stdout": p.stdout,
                "stderr": p.stderr,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
