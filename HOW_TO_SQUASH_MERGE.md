# How to Use Squash Merge on GitHub

## What is Squash Merge?

Squash merge combines all commits from a pull request into a single commit before merging into the main branch. This keeps your main branch history clean.

## How to Access Squash Merge Button

### Step 1: Open Your Pull Request
Go to your PR page (e.g., https://github.com/mshahabas94/rag/pull/5)

### Step 2: Find the Merge Button
At the bottom of the PR page, you'll see a green **"Merge pull request"** button.

### Step 3: Click the Dropdown Arrow
**IMPORTANT**: Don't click the button itself! Click the **small dropdown arrow** on the right side of the button.

```
┌─────────────────────────────────────────┐
│  Merge pull request              ▼      │  ← Click this arrow!
└─────────────────────────────────────────┘
```

### Step 4: Select Merge Method
You'll see three options:
- **Create a merge commit** (default)
- **Squash and merge** ← Select this one!
- **Rebase and merge**

### Step 5: Confirm Squash Merge
1. Click **"Squash and merge"**
2. Edit the commit message if needed
3. Click **"Confirm squash and merge"**

## Visual Guide

```
Pull Request Page
└── Scroll to bottom
    └── Merge section
        └── [Merge pull request ▼]  ← Click the ▼
            ├── Create a merge commit
            ├── Squash and merge      ← Choose this
            └── Rebase and merge
```

## Why Use Squash Merge?

### Before (Multiple Commits):
```
* Fix typo in comment
* Update formatting
* Add feature X
* Fix bug in feature X
* Refactor code
```

### After (Single Commit):
```
* Add feature X with fixes and improvements (#PR)
```

## For Your Current Branch

Your branch has these commits that need to be merged:
1. `Fix SQL formatting, intent classification, and Vanna training`
2. `feat: Enhance Vanna's SQL understanding and output formatting`
3. `Refactor _format_single_order to handle aggregate results`

With squash merge, these will become **one clean commit** in main.

## Important Notes

- ✅ Your repository **already has squash merge enabled**
- ✅ You just need to click the dropdown arrow to access it
- ⚠️ If you don't see the option, you may need repository admin access
- 💡 GitHub hides the dropdown if there's only one commit in the PR
