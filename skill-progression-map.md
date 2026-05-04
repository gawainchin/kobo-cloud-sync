# Kobo Cloud Sync Skill Progression Map

This map keeps the project-facing Codex skill small today while showing where it
can grow as the repo gains more workflows.

## Current Skill

- `skills/kobo-cloud-sync/SKILL.md` is the entrypoint for agent workflow
  guidance.
- It should stay focused on repeatable local work: setup, smoke checks,
  authentication caveats, and safe sync commands.
- Repository-specific behavior belongs in source and tests first, then gets
  summarized in the skill only when it becomes a durable workflow.

## Next Useful Additions

- Add a web UI smoke-check section that covers `kobo-cloud serve`, the local
  dashboard route, and the job-status polling route.
- Add a cookie import troubleshooting section once the common browser export
  path is stable.
- Add a release checklist after packaging and publishing steps settle.
- Add a contribution/testing matrix if the repo starts supporting multiple
  Python versions in CI.

## Keep Out

- Generated artifacts such as local output, screenshots that are not docs
  assets, browser profiles, cookies, and temporary pet or sprite assets.
- One-off debugging notes whose commands are not expected to be reused.
- Secrets, session data, or machine-specific paths beyond documented defaults.

## Promotion Rule

Promote a note into the skill only after it has been used successfully more than
once or protects against a real recurring failure. Otherwise keep it in issue,
PR, or local session context.
