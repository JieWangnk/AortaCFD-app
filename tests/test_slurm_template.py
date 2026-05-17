"""Tests for the SLURM-script generator with --cluster-conf and --slurm-template."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from run_batch import (  # noqa: E402
    _build_cluster_env_setup,
    _load_cluster_conf,
    _render_template,
    generate_slurm_script,
)


def test_load_cluster_conf_parses_kv_pairs(tmp_path: Path) -> None:
    conf = tmp_path / "x.conf"
    conf.write_text(
        '# comment line\n'
        'HPC_HOST="csf3"\n'
        'HPC_USER="me"\n'
        'HPC_PARTITION=multicore_small   # inline comment\n'
        '\n'
        'HPC_OF_MODULE=apps/gcc/openfoam/12\n'
    )
    out = _load_cluster_conf(str(conf))
    assert out["HPC_HOST"] == "csf3"
    assert out["HPC_USER"] == "me"
    assert out["HPC_PARTITION"] == "multicore_small"
    assert out["HPC_OF_MODULE"] == "apps/gcc/openfoam/12"


def test_load_cluster_conf_none_returns_empty() -> None:
    assert _load_cluster_conf(None) == {}


def test_load_cluster_conf_missing_file_returns_empty_and_warns(tmp_path: Path, capsys) -> None:
    out = _load_cluster_conf(str(tmp_path / "nope.conf"))
    assert out == {}
    captured = capsys.readouterr()
    assert "not found" in captured.out


def test_render_template_substitutes_tokens() -> None:
    text = "module load %%OF%%; partition %%P%%"
    out = _render_template(text, {"OF": "openfoam/12", "P": "multicore"})
    assert "module load openfoam/12" in out
    assert "partition multicore" in out


def test_render_template_passes_through_bash_variables() -> None:
    text = 'echo "$SLURM_ARRAY_TASK_ID"\nmodule load %%OF%%'
    out = _render_template(text, {"OF": "x"})
    assert "$SLURM_ARRAY_TASK_ID" in out


def test_render_template_warns_on_unsubstituted(capsys) -> None:
    text = "load %%MISSING%%"
    out = _render_template(text, {"OTHER": "x"})
    assert "%%MISSING%%" in out
    captured = capsys.readouterr()
    assert "MISSING" in captured.out


def test_cluster_env_setup_with_module() -> None:
    out = _build_cluster_env_setup({"HPC_OF_MODULE": "openfoam/12"}, "/tmp/conf")
    assert "module load openfoam/12" in out
    assert "module purge" in out
    assert "foamDotFile" in out


def test_cluster_env_setup_without_module_is_warning_block() -> None:
    out = _build_cluster_env_setup({}, None)
    assert "No --cluster-conf passed" in out


def test_generate_default_script_has_required_sbatch_lines(tmp_path: Path) -> None:
    out = tmp_path / "submit.sh"
    generate_slurm_script(
        cases=["A", "B", "C"],
        steps="all",
        config_override=None,
        partition="multicore_small",
        time_limit="02:00:00",
        cpus_per_task=8,
        mem_per_cpu="4G",
        output_script=str(out),
    )
    text = out.read_text()
    assert "#SBATCH --array=0-2" in text
    assert "#SBATCH --partition=multicore_small" in text
    assert 'CASES=("A" "B" "C")' in text
    assert "command -v foamRun" in text


def test_generate_with_cluster_conf_injects_module_load(tmp_path: Path) -> None:
    conf = tmp_path / "x.conf"
    conf.write_text('HPC_OF_MODULE=apps/gcc/openfoam/12\n')
    out = tmp_path / "submit.sh"
    generate_slurm_script(
        cases=["A"],
        steps="all",
        config_override=None,
        cluster_conf=str(conf),
        output_script=str(out),
    )
    text = out.read_text()
    assert "module load apps/gcc/openfoam/12" in text


def test_generate_with_user_template(tmp_path: Path) -> None:
    template = tmp_path / "my_template.sh"
    template.write_text(
        "#!/bin/bash\n"
        "#SBATCH --array=0-%%ARRAY_MAX%%\n"
        "#SBATCH --partition=%%PARTITION%%\n"
        "%%CLUSTER_ENV_SETUP%%\n"
        "CASES=(%%CASES%%)\n"
        "echo $SLURM_ARRAY_TASK_ID\n"
    )
    conf = tmp_path / "x.conf"
    conf.write_text('HPC_OF_MODULE=of/12\n')
    out = tmp_path / "submit.sh"
    generate_slurm_script(
        cases=["a", "b", "c", "d"],
        steps="all",
        config_override=None,
        partition="bigmem",
        cluster_conf=str(conf),
        slurm_template=str(template),
        output_script=str(out),
    )
    text = out.read_text()
    assert "#SBATCH --array=0-3" in text
    assert "#SBATCH --partition=bigmem" in text
    assert "module load of/12" in text
    assert 'CASES=("a" "b" "c" "d")' in text
    assert "$SLURM_ARRAY_TASK_ID" in text


def test_generate_exposes_arbitrary_conf_keys_as_tokens(tmp_path: Path) -> None:
    template = tmp_path / "t.sh"
    template.write_text("#!/bin/bash\n#SBATCH --account=%%HPC_ACCOUNT%%\n")
    conf = tmp_path / "x.conf"
    conf.write_text('HPC_ACCOUNT=myproject\nHPC_OF_MODULE=of/12\n')
    out = tmp_path / "submit.sh"
    generate_slurm_script(
        cases=["A"],
        steps="all",
        config_override=None,
        cluster_conf=str(conf),
        slurm_template=str(template),
        output_script=str(out),
    )
    text = out.read_text()
    assert "#SBATCH --account=myproject" in text


def test_generate_missing_template_raises(tmp_path: Path) -> None:
    out = tmp_path / "submit.sh"
    with pytest.raises(FileNotFoundError, match="not found"):
        generate_slurm_script(
            cases=["A"],
            steps="all",
            config_override=None,
            slurm_template=str(tmp_path / "absent.sh"),
            output_script=str(out),
        )


def test_generated_script_is_bash_valid(tmp_path: Path) -> None:
    out = tmp_path / "submit.sh"
    generate_slurm_script(
        cases=["BPM120", "VOL04"],
        steps="all",
        config_override=None,
        partition="multicore_small",
        output_script=str(out),
    )
    result = subprocess.run(["bash", "-n", str(out)], capture_output=True, text=True)
    assert result.returncode == 0, f"bash -n failed: {result.stderr}"


def test_run_name_appears_in_python_invocation(tmp_path: Path) -> None:
    """For hybrid local/HPC workflows, --run-name must propagate to each task."""
    out = tmp_path / "submit.sh"
    generate_slurm_script(
        cases=["A", "B"],
        steps="solver",
        config_override=None,
        partition="multicore_small",
        output_script=str(out),
        run_name="hpc_batch",
    )
    text = out.read_text()
    assert 'python run_patient.py "$CASE_ID" --steps solver --run-name hpc_batch' in text


def test_no_run_name_keeps_python_invocation_clean(tmp_path: Path) -> None:
    out = tmp_path / "submit.sh"
    generate_slurm_script(
        cases=["A"],
        steps="all",
        config_override=None,
        output_script=str(out),
    )
    text = out.read_text()
    assert 'python run_patient.py "$CASE_ID" --steps all' in text
    assert "--run-name" not in text
