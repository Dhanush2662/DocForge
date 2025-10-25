# 🤝 Contributing to DocQuest Extraction Pipeline

> **Read this before touching anything or we'll haunt your dreams with JSON parsing errors**

---

## 🚨 GOLDEN RULES (BREAK THESE = BAN)

1. **NEVER** commit directly to `main` branch. Use feature branches.
2. **NEVER** edit JSON files manually unless you're fixing a bug in the JSON structure itself.
3. **NEVER** overwrite someone else's work without asking first.
4. **ALWAYS** test your changes before pushing.
5. **ALWAYS** write meaningful commit messages.

---

## 🌳 BRANCHING STRATEGY

```
main (protected) ← develop (integration)
                  ← feature/your-name-what-youre-doing
                  ← hotfix/urgent-broken-thing
```

### Feature Branch Naming
- `feature/parser-goblin-improvements`
- `feature/classifier-accuracy-boost`
- `feature/vision-ocr-upgrade`
- `feature/dashboard-ui-polish`

### Hotfix Branch Naming
- `hotfix/critical-parser-bug`
- `hotfix/db-connection-issue`

---

## 📝 COMMIT MESSAGE FORMAT

```
type(scope): brief description

Optional longer explanation if needed.

Fixes #issue-number (if applicable)
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code formatting (no logic changes)
- `refactor`: Code cleanup
- `test`: Adding/updating tests
- `chore`: Maintenance tasks

**Examples:**
✅ Good:
```
feat(parser): add support for multi-column PDFs

The parser now handles 2-column layouts by detecting column breaks
and processing them separately. This improves extraction accuracy
for textbooks with sidebars.

Fixes #23
```

```
fix(classifier): resolve infinite loop on malformed questions

Add bounds checking to prevent infinite recursion when processing
edge cases with incomplete question structures.
```

❌ Bad:
```
fixed stuff
changed parser
update
```

---

## 🔧 DEVELOPMENT WORKFLOW

### 1. Before You Start
```bash
git checkout develop
git pull origin develop
git checkout -b feature/your-awesome-feature
```

### 2. Make Your Changes
- Write clean, readable code
- Add comments for complex logic
- Test locally with sample data
- Don't break existing functionality

### 3. Before Committing
```bash
# Check what you're changing
git status
git diff

# Run tests (when we have them)
# python -m pytest

# Stage and commit
git add .
git commit -m "feat(your-feature): description of changes"
```

### 4. Push and Create PR
```bash
git push origin feature/your-awesome-feature
```
Then create a Pull Request on GitHub with:
- Clear title
- Description of changes
- Testing done
- Screenshots if UI changes

---

## 📁 FILE HANDLING RULES

### ✅ SAFE TO EDIT
- `scripts/*.py` (your assigned script)
- `review_dashboard/` (your assigned component)
- `db/` (only if you're the DB person)
- This `CONTRIBUTING.md` file

### ⚠️ ASK FIRST
- `data/` folder contents (coordinate with team)
- Shared utility functions
- Database schema changes
- API contracts

### 🚫 NEVER TOUCH
- Someone else's assigned scripts
- `main` branch directly
- Production database
- Approved JSON outputs without review

---

## 🧪 TESTING YOUR CHANGES

### Parser Testing
```bash
python scripts/parse_pdf.py test_sample.pdf --out test_output.json
# Check that test_output.json looks sane
```

### Classifier Testing
```bash
python scripts/classify_text.py --in data/raw_blocks.json --out test_classified.json
# Verify classification accuracy
```

### Dashboard Testing
```bash
cd review_dashboard/backend
uvicorn main:app --reload --port 8000
# Test endpoints at http://localhost:8000/docs
```

### Database Testing
```bash
# Use test database schema, not production!
python db/upload_to_db.py --test-mode
```

---

## 📋 CODE REVIEW CHECKLIST

Before submitting a PR, ensure:

### Code Quality
- [ ] Code follows existing style
- [ ] No TODO/FIXME comments left
- [ ] Error handling is appropriate
- [ ] No hardcoded values that should be configurable

### Functionality
- [ ] Feature works as expected
- [ ] No regressions in existing features
- [ ] Edge cases are handled
- [ ] Performance isn't degraded

### Documentation
- [ ] Updated README if needed
- [ ] Added inline comments for complex logic
- [ ] Updated API docs if applicable

### Testing
- [ ] Tested with sample data
- [ ] No crashes or exceptions
- [ ] Output format is correct

---

## 🐛 BUG REPORTS

Found a bug? Create an issue with:

1. **Clear title**: "Parser crashes on PDF with rotated pages"
2. **Environment**: OS, Python version, dependencies
3. **Steps to reproduce**: Exact commands and data
4. **Expected vs actual behavior**
5. **Error messages** (full stacktraces)
6. **Sample data** (if possible and non-sensitive)

---

## 💡 FEATURE REQUESTS

Want something new? Create an issue with:

1. **Use case**: Why do we need this?
2. **Proposed solution**: How should it work?
3. **Alternatives considered**: What else did you think of?
4. **Priority**: Nice-to-have or must-have?

---

## 🚫 FORBIDDEN PATTERNS

### JSON Editing
```bash
# DON'T DO THIS
echo '{"broken": "json"}' > data/approved_output.json
git add data/approved_output.json
git commit -m "update json"
```

### Direct Main Commits
```bash
# NEVER DO THIS
git checkout main
git commit -am "hotfix"
git push origin main
```

### Overwriting Team Work
```bash
# DON'T DO THIS WITHOUT ASKING
git checkout feature/teammates-work
git commit -am "fixed their stuff"
git push origin feature/teammates-work
```

---

## 🆘 GETTING HELP

1. **Check this file first** - 90% of questions are answered here
2. **Search existing issues** - someone might have asked already
3. **Ask in team chat** - tag relevant people
4. **Create an issue** - if it's a bug or feature request

### When Asking for Help:
- What are you trying to do?
- What have you tried?
- What error are you getting?
- What did you expect to happen?

---

## 🎯 YOU BREAK IT, YOU FIX IT

- Accidentally pushed to main? Fix it immediately and tell the team
- Broke the parser? Roll back and investigate before continuing
- Messed up the database? Restore from backup (we have backups, right?)
- Caused a merge conflict? Resolve it properly, don't force push

---

## 👏 RECOGNITION

Good contributions get:
- 🏆 Mention in project updates
- 🎁 First dibs on interesting features
- 😎 Respect from the team
- ☕ Virtual coffee from the Overlord

Bad contributions get:
- 🚫 Revoked commit access
- 😅 Team ridicule (we're nice, but still)
- 🧹 Assigned to documentation duty

---

**Now go build something awesome! But follow the rules, or we'll find you.** 👀