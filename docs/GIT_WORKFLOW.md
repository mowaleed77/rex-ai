# Git & GitHub Workflow

## One-time (team lead)
```bash
cd rex-ai
git init -b main
git add . && git commit -m "Initial REX AI project structure and Sprint 1 prototype"
# create an empty repo on GitHub, then:
git remote add origin https://github.com/<org-or-user>/rex-ai.git
git push -u origin main
git checkout -b develop && git push -u origin develop
```
GitHub → Settings → Collaborators → **add the instructor** (required). Add all teammates.

## Everyone, every task
```bash
git checkout develop && git pull
git checkout -b feature/<agent>-<task>      # e.g. feature/rfp-country-filter
# ...work, with your OWN account configured:
git config user.name "Your Name"; git config user.email "your@email"
git add <files> && git commit -m "Describe what changed and why"
git push -u origin feature/<agent>-<task>   # open a Pull Request into develop
```
A teammate reviews, then merge. `develop` → `main` at each sprint milestone.

## Do not
Commit secrets (`.env`), copy-paste someone else's commits, or let one person push everything — the instructor reviews actual changes per student.
