import os


__all__ = ["CONFIG_FILE_PATH", "MACHINE_KEYS", "DATE_FORMAT"]


DATE_FORMAT = "%Y%m%d%H%M%S"
CONFIG_FILE_PATH = os.path.expanduser("~/.autoslurmconfig")
MACHINE_KEYS = [
    "hostname",
    "hosturl",
    "username",
    "key_path",
    "path",
    "env_command",
    "slurm_account",
]
