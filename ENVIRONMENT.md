# Virtual Environment Quick Reference

## Initial Setup

```bash
# Automated setup (recommended)
./setup_env.sh

# Manual setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Daily Usage

```bash
# 1. Activate environment (required before using AortaCFD)
source venv/bin/activate

# 2. Use AortaCFD
python app.py runAll --case PAT1_2024 --profile sim_laminar_fine

# 3. Deactivate when done
deactivate
```

## Environment Management

```bash
# Check if environment is active (should show path to venv)
which python

# List installed packages
pip list

# Update packages
pip install --upgrade -r requirements.txt

# Add new package
pip install package_name
pip freeze > requirements.txt  # Update requirements file
```

## Troubleshooting

**Environment not found:**
```bash
# Recreate environment
rm -rf venv
./setup_env.sh
```

**Package conflicts:**
```bash
# Start fresh
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**IDE Integration:**
- **VS Code**: Select Python interpreter: `./venv/bin/python`
- **PyCharm**: Project Settings → Python Interpreter → Add Local → `./venv/bin/python`