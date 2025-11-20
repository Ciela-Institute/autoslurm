[
  {
    "name": "inspect_experiments",
    "description": "Return the agent-focused snapshot for a bundle (bundle JSON + generated SLURM scripts + .out logs).",
    "parameters": {
      "bundle": "Required. The logical bundle name (e.g., the value passed to autoslurm-schedule).",
      "date": "Optional. ISO-8601 or autoslurm DATE_FORMAT to pick a specific bundle instance."
    },
    "context_sections": ["09_task_inspect.md", "12_task_acp_reference.md"],
    "keywords": ["inspect", "experiment"]
  },
  {
    "name": "list_experiments",
    "description": "Enumerate all bundle files for a given name so the agent can pick the desired timestamp.",
    "parameters": {
      "bundle": "Required. The bundle base name to scan (will match jobs/<bundle>_*.json)."
    },
    "context_sections": ["09_task_inspect.md", "12_task_acp_reference.md"],
    "keywords": ["list", "inspect"]
  },
  {
    "name": "schedule",
    "description": "Persist a fully formed job dict into the bundle directory (append or new bundle).",
    "parameters": {
      "bundle": "Required unless the job dict already contains a bundle entry.",
      "job": "Required. A dict containing at least 'script' and 'slurm'; optional 'name', 'dependencies', 'pre_commands', etc.",
      "append": "Optional boolean. When true, appends to the latest bundle instead of creating a new timestamped file."
    },
    "context_sections": ["10_task_schedule.md", "12_task_acp_reference.md"],
    "keywords": ["schedule", "plan"]
  }
  ,
  {
    "name": "gather_context",
    "description": "Return the agent folder context (documentation, examples, schema) as a single concatenated string.",
    "parameters": {
      "sections": "Optional list of filenames or substrings to filter the agent files that are included.",
      "task": "Optional keyword or action name that automatically selects relevant sections."
    },
    "context_sections": [
      "01_context_overview.md",
      "02_llm_interface.md",
      "12_task_acp_reference.md"
    ],
    "keywords": ["context", "gather"]
  }
]
