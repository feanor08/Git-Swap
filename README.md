# 🔀 Git-Swap

> Stop committing to work repos with your personal email. Stop committing to personal repos with your work email.

Git-Swap lets you manage two completely separate Git identities on one Mac — different SSH keys, different emails, different hosts — and switch between them with a single command.

---

## The problem

You have two lives:

| | Personal | Work |
|---|---|---|
| **Platform** | GitHub | GitLab (or self-hosted) |
| **Email** | you@gmail.com | you@company.com |
| **SSH key** | your personal key | your work key |

macOS only has one global `~/.gitconfig`. Every time you switch contexts you either forget to change it or break something. Git-Swap fixes this by keeping everything **per-repo** and giving you a one-word command to swap.

---

## What it does

```
gitSwap              ← detects which identity you're on and flips to the other
gitSwap work         ← forces work identity
gitSwap personal     ← forces personal identity
gitSwap status       ← shows current identity without making any change
```

Each swap does three things atomically, in the current repo only:

1. Rewrites `origin` to use the right SSH key alias
2. Sets `git config user.email` locally
3. Sets `git config user.name` locally

Your global `~/.gitconfig` is **never touched**. Other repos are **never affected**.

---

## Setup (one time)

Double-click **`Git Identity Switcher.command`** from Finder — or run:

```bash
python3 git_identity_ui.py
```

You'll see this:

```
┌─────────────────────────────────────────────────────────┐
│  Git Identity Switcher                                  │
│  One-time setup — configure your two identities         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Personal Identity                                      │
│  Platform  [ GitHub ] [ GitLab ] [ Bitbucket ] [Other]  │
│  Host      github.com                                   │
│  Name      ________________________________             │
│  Email     ________________________________             │
│  Path      ________________________________             │
│                                                         │
│  Work Identity                                          │
│  Platform  [ GitHub ] [ GitLab ] [ Bitbucket ] [Other]  │
│  Host      ________________________________  (editable) │
│  Name      ________________________________             │
│  Email     ________________________________             │
│  Path      ________________________________             │
│                                                         │
│  Global Command                                         │
│  Command   gitSwap                                      │
│                                                         │
│ ─────────────────────────────────────────────────────── │
│                               [ Run Setup ]             │
└─────────────────────────────────────────────────────────┘
```

Hit **Run Setup** and it:

- Generates two SSH keys (`~/.ssh/id_ed25519_personal` and `~/.ssh/id_ed25519_work`)
- Writes the host aliases to `~/.ssh/config`
- Loads the keys into macOS Keychain via `ssh-agent`
- Installs `gitSwap` to `/usr/local/bin`

---

## After setup

The UI flips to a dashboard:

```
┌─────────────────────────────────────────────────────────┐
│  Git Identity Switcher                                  │
│  ✓ Setup complete                                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Add SSH keys to each platform                          │
│  (key is copied silently — never shown on screen)       │
│                                                         │
│  ┌─ Personal · GitHub ───────────────────────────────┐  │
│  │  github.com → Settings → SSH and GPG keys         │  │
│  │  [ Copy Personal SSH Key ]                        │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─ Work · GitLab ────────────────────────────────────┐  │
│  │  gitlab.company.com → Preferences → SSH Keys      │  │
│  │  [ Copy Work SSH Key ]                            │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  'gitSwap' is ready — run it inside any git repo        │
│      $ gitSwap                                          │
│      $ gitSwap work                                     │
│      $ gitSwap personal                                 │
│                                                         │
│  [ Test Personal SSH ]  [ Test Work SSH ]  Reconfigure  │
└─────────────────────────────────────────────────────────┘
```

Copy each key, paste it into the platform, hit **Test** to confirm it works.

---

## Daily use

```bash
# You just cloned a work repo and need to set it up
cd ~/code/new-work-project
gitSwap work
# → email  : you@company.com
# → remote : git@git-work:myteam/new-work-project.git

# You're in a personal repo and accidentally ran gitSwap work
gitSwap personal
# → email  : you@gmail.com
# → remote : git@git-personal:yourusername/new-work-project.git

# You don't remember which identity this repo is on — just toggle
gitSwap
# → Detected work → switching to personal
```

---

## How identity detection works (for bare `gitSwap`)

When you don't pass an argument, Git-Swap figures out which identity is active using three checks in order:

```
1.  Is "git-personal" or "git-work" in the remote URL?
       → most reliable after the first swap

2.  Does git config user.email match a stored email?
       → catches repos where identity was set manually

3.  Is the raw hostname (e.g. github.com) in the remote URL?
       → catches freshly cloned repos before the first swap
```

If all three fail, it asks you to be explicit: `gitSwap work` or `gitSwap personal`.

---

## Works with any Git host

Pick your platform in the setup UI. Self-hosted instances work too — just select **Other** and type the hostname.

| Platform | Example host |
|---|---|
| GitHub | `github.com` |
| GitLab | `gitlab.com` |
| Bitbucket | `bitbucket.org` |
| Self-hosted GitLab | `gitlab.yourcompany.com` |
| Gitea / Forgejo | `git.yourcompany.com` |
| Anything with SSH | any hostname |

---

## What's in the box

```
Git-Swap/
├── git_identity_switcher.py   CLI entry point
├── git_identity_ui.py         UI entry point
├── Git Identity Switcher.command   double-click launcher for Finder
└── gitswap/
    ├── constants.py           all paths and alias names
    ├── utils.py               subprocess wrapper + output helpers
    ├── config.py              read/write ~/.git_identity_switcher.json
    ├── ssh.py                 key generation, ~/.ssh/config, ssh-agent
    ├── git_ops.py             repo detection, remotes, local identity
    ├── swap.py                detection logic + apply_profile (core)
    ├── cli.py                 all CLI subcommands
    └── ui/
        ├── theme.py           colors + fonts
        ├── widgets.py         reusable tkinter components
        ├── installer.py       gitSwap shell script + PATH setup
        └── app.py             the UI app
```

---

## CLI reference

```bash
# Setup
python3 git_identity_switcher.py setup
python3 git_identity_switcher.py setup --personal-host github.com --work-host gitlab.co.com

# Swap
gitSwap                    # toggle
gitSwap work               # force work
gitSwap personal           # force personal
gitSwap status             # show current identity (read-only)

# Inspect / debug
python3 git_identity_switcher.py show-remote
python3 git_identity_switcher.py test-personal
python3 git_identity_switcher.py test-work

# Manual overrides
python3 git_identity_switcher.py set-identity --name "Ada" --email "ada@co.com"
python3 git_identity_switcher.py use-personal --path myusername
python3 git_identity_switcher.py use-work     --path myteam/backend

# Remove all Git-Swap artifacts (keeps SSH keys)
python3 git_identity_switcher.py uninstall
```

---

## Requirements

- macOS (uses `UseKeychain`, `--apple-use-keychain`, `pbcopy`)
- Python 3.10+ (stdlib only — no pip installs)
- SSH access to your Git host(s)
