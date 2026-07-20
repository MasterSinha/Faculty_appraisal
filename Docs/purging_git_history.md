# Guide: Purging Sensitive Data from Git History

If a repository must remain public on GitHub, simply modifying files and committing the changes **does not delete the data**. The sensitive information (like your public IP `150.129.156.37`) remains fully visible in your past commit history.

To completely erase the IP from GitHub, you must rewrite your Git history. This guide details how to perform this cleanup safely.

---

## The Concept of Git History Rewriting

Git is a chronological database of snapshots. A commit points to its parent commit. 

```
[Commit A: Added IP]  <-- [Commit B: Modified other code]  <-- [Commit C: Removed IP (Latest)]
```

If an auditor or attacker looks at **Commit A** or **Commit B**, the IP address is still visible. To remove it, you must rebuild the chain of commits so that the IP address never existed in any of them:

```
[Commit A*: No IP]   <-- [Commit B*: Modified other code]  <-- [Commit C*: Removed IP (Latest)]
```

---

## Step-by-Step Cleanup Procedure

The official tool recommended by Git is `git-filter-repo` (a Python-based tool that replaces the old, slow `git filter-branch` command).

### Step 1: Install `git-filter-repo`
Run this on your local development machine:
```bash
pip install git-filter-repo
```

### Step 2: Backup Your Repository
Rewriting history is destructive. Create a fresh clone of your repository in another folder as a backup before proceeding:
```bash
git clone https://github.com/Ruhan-Saad-Dave/Faculty_appraisal.git backup_appraisal
```

### Step 3: Run the Replacements
Create a text file named `expressions.txt` in the root of your project, containing the replacements you want to make in every file across all commits:

```text
150.129.156.37==>YOUR_PUBLIC_VM_IP
10.100.0.23==>YOUR_PRIVATE_VM_IP
```

Run `git-filter-repo` pointing to your expressions file:
```bash
git filter-repo --replace-text expressions.txt
```
*(This command rewrites every single commit in your local history, replacing the actual IP addresses with placeholder strings.)*

### Step 4: Add the GitHub Remote Back
Running `git filter-repo` automatically removes your configured remotes to prevent accidental pushes. Re-add your GitHub repository link:
```bash
git remote add origin https://github.com/Ruhan-Saad-Dave/Faculty_appraisal.git
```

### Step 5: Force Push to GitHub
To overwrite the history on GitHub with your clean, rewritten local history, you must perform a force push:
```bash
git push origin --force --all
git push origin --force --tags
```

---

## Crucial Warnings & Edge Cases

* **Forks Remain Public**: If anyone has already **forked** your repository while it was public, those forks will retain the original commits containing your IP address. Changing your repository or rewriting its history does not affect forks.
* **Cached GitHub Commits**: Even after a force push, GitHub sometimes retains cached views of old commits if someone has the direct commit hash. To force GitHub to garbage collect and delete these commits immediately, you can contact GitHub Support.
* **Collaborator Syncing**: If other developers are working on this repository, they must **not** perform a standard `git pull` after your force push. Doing so will merge the old history back. They must perform a hard reset to the new origin:
  ```bash
  git fetch origin
  git reset --hard origin/main
  ```
