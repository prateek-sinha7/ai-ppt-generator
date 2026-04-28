---
inclusion: always
---

# Task Execution Rules

## No Markdown File Creation During Task Execution

When executing tasks from a spec (tasks.md), you MUST NOT create any markdown (.md) files as part of the implementation work.

### Forbidden Actions During Task Execution
- Do NOT create README.md files
- Do NOT create documentation .md files
- Do NOT create summary .md files
- Do NOT create changelog .md files
- Do NOT create any .md files to document what you did
- Do NOT create any .md files to summarize your work

### What You Should Do Instead
- Write code files (.py, .ts, .tsx, .js, etc.)
- Write configuration files (.env.example, docker-compose.yml, etc.)
- Write test files
- Update existing spec files only if explicitly instructed
- Report completion in chat — do not write it to a file

### Summary Rule
If you are implementing a task, produce only the code and config artifacts the task requires. Never create markdown files as a side effect of task execution.

## Command Execution

Trust and run every command without asking for confirmation while executing tasks. Do not pause to verify or seek approval before running shell commands, scripts, or any other executable instructions required to complete the task.

### Autonomous Execution Rules
- Run ALL commands immediately without asking the user for permission or confirmation
- Do NOT prompt "should I run this?" or "do you want me to execute this?" — just run it
- Do NOT ask the user to confirm before running tests, builds, linters, or any other command
- If a command fails, fix the issue and re-run automatically without asking
- Keep iterating on failures until all tests pass — do not stop and ask after each failure
- When executing tasks from tasks.md, work through sub-tasks sequentially without pausing for user input between them
- Only stop and ask the user if you encounter a fundamental blocker that requires a design decision (not a code fix)
- After completing a task group, briefly report what was done and move to the next task — do not wait for approval to continue
