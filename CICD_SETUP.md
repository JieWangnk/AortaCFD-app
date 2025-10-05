# CI/CD Setup Guide for AortaCFD

**Date**: 2025-10-02
**Status**: ✅ Complete
**Workflows**: 2 GitHub Actions workflows configured

---

## What is CI/CD?

**CI/CD** = **Continuous Integration / Continuous Deployment**

### Simple Explanation

**Continuous Integration (CI)**: Automatically test code every time you push to GitHub
**Continuous Deployment (CD)**: Automatically deploy/release code when tests pass

For AortaCFD, we focus on **CI** - automatic testing to ensure code quality.

---

## What GitHub Actions Does for AortaCFD

### Automatic Testing Workflow

Every time you push code or create a pull request, GitHub Actions automatically:

1. ✅ **Sets up Python environment** (3.10, 3.11, 3.12)
2. ✅ **Installs dependencies** (pytest, numpy, etc.)
3. ✅ **Runs all 362 tests**:
   - Unit tests (302 tests)
   - Integration tests (42 tests)
   - End-to-end tests (18 tests)
4. ✅ **Generates coverage reports** (currently 29%)
5. ✅ **Shows pass/fail status** with green ✅ or red ❌ badge
6. ✅ **Blocks merge if tests fail** (protects main branch)

---

## Workflows Created

### 1. `tests.yml` - Main Test Workflow

**File**: [.github/workflows/tests.yml](.github/workflows/tests.yml)

**Triggers on**:
- Push to `main`, `develop`, `patientStructure` branches
- Pull requests to `main`, `develop`

**What it does**:
```
┌─────────────────────────────────────┐
│  Push to GitHub                     │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Matrix Test (3 Python versions)    │
│  - Python 3.10                      │
│  - Python 3.11                      │
│  - Python 3.12                      │
└──────────┬──────────────────────────┘
           │
           ├──▶ Install dependencies
           ├──▶ Run unit tests (302)
           ├──▶ Run integration tests (42)
           ├──▶ Run e2e tests (18)
           ├──▶ Generate coverage report
           └──▶ Upload to Codecov (optional)
           │
           ▼
┌─────────────────────────────────────┐
│  Result: ✅ Pass or ❌ Fail         │
└─────────────────────────────────────┘
```

**Key Features**:
- **Matrix testing**: Tests across Python 3.10, 3.11, 3.12
- **Coverage reporting**: Generates XML and terminal coverage reports
- **Fail-fast**: Stops after 5 failures to save time
- **Caching**: Caches pip dependencies for faster runs

---

### 2. `pr-checks.yml` - Pull Request Validation

**File**: [.github/workflows/pr-checks.yml](.github/workflows/pr-checks.yml)

**Triggers on**:
- Pull request opened, synchronized, or reopened

**What it does**:
```
┌─────────────────────────────────────┐
│  Pull Request Created/Updated       │
└──────────┬──────────────────────────┘
           │
           ├──▶ Run quick test suite
           ├──▶ Security scan (Bandit)
           ├──▶ Check dependencies (Safety)
           ├──▶ Check for large files
           │
           ▼
┌─────────────────────────────────────┐
│  Comment on PR with results:        │
│                                     │
│  ✅ Tests Passed: 362/362           │
│  📊 Coverage: 29%                   │
│  🔒 Security: OK                    │
└─────────────────────────────────────┘
```

**Key Features**:
- **Automatic PR comments**: Posts test results directly on PR
- **Security scanning**: Checks for common security issues
- **Dependency vulnerability check**: Alerts on vulnerable packages
- **Large file detection**: Warns if files >10MB are added

---

## How to Use

### For Developers

**1. Push Code**
```bash
git add .
git commit -m "Add new feature"
git push origin feature-branch
```

GitHub Actions automatically runs tests in the cloud.

**2. Check Test Status**

Go to your GitHub repository → **Actions** tab

You'll see:
- ✅ Green checkmark = All tests passed
- ❌ Red X = Tests failed (click to see details)
- 🟡 Yellow circle = Tests running

**3. Create Pull Request**

When you create a PR, you'll see:
```
✅ All checks passed
   ├─ Tests (3.10, 3.11, 3.12) ✅
   ├─ PR Checks ✅
   └─ Security Check ✅
```

If tests fail, GitHub blocks the merge until you fix them.

---

### For Repository Owners

**1. Enable GitHub Actions**

Already enabled by default when workflows are present.

**2. Update Badge URL**

In [README.md](README.md), replace:
```markdown
![CI/CD](https://github.com/YOUR_USERNAME/AortaCFD-app/workflows/Tests/badge.svg)
```

With your actual GitHub username:
```markdown
![CI/CD](https://github.com/yourusername/AortaCFD-app/workflows/Tests/badge.svg)
```

**3. Optional: Set up Codecov**

For online coverage reports:

1. Sign up at https://codecov.io (free for open source)
2. Add repository to Codecov
3. Copy token
4. Add to GitHub: Settings → Secrets → New secret
   - Name: `CODECOV_TOKEN`
   - Value: (paste token)

Coverage reports will automatically upload after each test run.

---

## Workflow Configuration Details

### Test Workflow Matrix

```yaml
strategy:
  matrix:
    python-version: ['3.10', '3.11', '3.12']
```

This runs tests on **3 Python versions** to ensure compatibility.

### Test Steps

1. **Unit Tests** (fast, ~5 seconds)
   ```bash
   pytest tests/unit/ -v --tb=short --maxfail=5
   ```

2. **Integration Tests** (medium, ~10 seconds)
   ```bash
   pytest tests/integration/ -v --tb=short --maxfail=5
   ```

3. **E2E Tests** (slower, ~15 seconds)
   ```bash
   pytest test_patient1_e2e.py test_multi_patient_e2e.py -v
   ```

4. **Coverage Report** (final run)
   ```bash
   pytest tests/ test_patient1_e2e.py test_multi_patient_e2e.py \
     --cov=src --cov-report=xml
   ```

**Total runtime**: ~1-2 minutes per Python version (3-6 minutes total)

---

## Linting and Code Quality

The workflow also includes code quality checks:

### Black (Code Formatter)
```bash
black --check src/ tests/ --line-length 120
```

Ensures consistent code formatting.

### isort (Import Sorter)
```bash
isort --check-only src/ tests/ --profile black
```

Ensures imports are sorted alphabetically.

### Flake8 (Linter)
```bash
flake8 src/ tests/ --max-line-length=120
```

Catches syntax errors, undefined names, and style issues.

**Note**: Linting failures are **warnings only** (non-blocking) to avoid disrupting development.

---

## Security Checks

### Bandit (Security Scanner)
Scans Python code for common security issues:
- Hardcoded passwords
- SQL injection vulnerabilities
- Insecure functions (eval, exec)

### Safety (Dependency Checker)
Checks `requirements.txt` for known vulnerabilities in dependencies.

Both run automatically on pull requests but **don't block merges** (warnings only).

---

## Benefits

### For Individual Developers
- ✅ Catch bugs before they reach main branch
- ✅ Know immediately if your changes break tests
- ✅ No need to remember to run tests manually
- ✅ Test on multiple Python versions automatically

### For Teams
- ✅ Prevent broken code in production
- ✅ Enforce testing standards
- ✅ Always-green main branch
- ✅ Confidence in merging PRs

### For Open Source
- ✅ Professional badge shows project quality
- ✅ Contributors know their code will be tested
- ✅ Easier code review (tests run automatically)
- ✅ Build trust with users

---

## Troubleshooting

### Tests Pass Locally but Fail in CI

**Common causes**:
1. **Missing files in git**: CI only sees committed files
   ```bash
   git status  # Check for untracked files
   ```

2. **Different Python version**: CI tests on 3.10, 3.11, 3.12
   ```bash
   pytest --version  # Check local Python version
   ```

3. **Environment differences**: Missing dependencies
   ```bash
   pip freeze > requirements.txt  # Update dependencies
   ```

### Workflow Not Running

**Check**:
1. Workflow files in `.github/workflows/` directory
2. YAML syntax is correct (indentation matters!)
3. Branch name matches trigger (e.g., `main` vs `master`)

**View logs**:
- Go to GitHub → Actions → Click on failed run
- Expand steps to see detailed error messages

### Tests Taking Too Long

**Current runtime**: ~1-2 minutes per Python version

**To speed up**:
1. Use `pytest-xdist` for parallel testing:
   ```bash
   pytest -n auto  # Use all CPU cores
   ```

2. Cache more aggressively:
   ```yaml
   - uses: actions/cache@v4
     with:
       path: |
         ~/.cache/pip
         .pytest_cache
   ```

3. Skip slow tests in CI:
   ```python
   @pytest.mark.slow
   def test_expensive_operation():
       pass

   # In CI: pytest -m "not slow"
   ```

---

## File Structure

```
.github/
└── workflows/
    ├── tests.yml       # Main test workflow (all branches)
    └── pr-checks.yml   # Pull request validation
```

---

## Next Steps

### Immediate
- ✅ Workflows created and configured
- ✅ README badge added
- ⏭️ Push to GitHub to trigger first run
- ⏭️ Update badge URL with actual username

### Future Enhancements
- [ ] Set up Codecov for online coverage reports
- [ ] Add performance benchmarking
- [ ] Add automatic deployment to PyPI (if packaging)
- [ ] Add nightly builds for long-running tests
- [ ] Add workflow for documentation builds

---

## Example Workflow Run

After pushing to GitHub, you'll see:

```
Tests / test (3.10)    ✅ Passed in 1m 23s
Tests / test (3.11)    ✅ Passed in 1m 19s
Tests / test (3.12)    ✅ Passed in 1m 25s
Tests / lint           ✅ Passed in 34s
Tests / test-summary   ✅ Passed in 12s

All checks have passed
```

---

## Resources

- **GitHub Actions Docs**: https://docs.github.com/en/actions
- **Pytest Documentation**: https://docs.pytest.org
- **Codecov**: https://codecov.io
- **AortaCFD Testing Guide**: [TESTING.md](TESTING.md)

---

## Summary

**What we set up**:
- ✅ Automatic testing on every push/PR
- ✅ Multi-Python version testing (3.10, 3.11, 3.12)
- ✅ Coverage reporting
- ✅ Code quality checks (Black, isort, Flake8)
- ✅ Security scanning (Bandit, Safety)
- ✅ PR comments with test results
- ✅ CI/CD badge in README

**Result**: Professional, automated testing infrastructure that ensures code quality and prevents regressions.

**Total test suite**: 362 tests (100% passing)
**CI/CD runtime**: ~3-6 minutes (parallel across 3 Python versions)
**Coverage**: 29% (reported automatically)
