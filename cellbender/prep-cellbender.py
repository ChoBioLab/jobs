#!/usr/bin/env python3

import argparse
import glob
import os
import re
from datetime import datetime


def should_skip_directory(dir_path):
    """Check if a directory should be skipped (SC_*_CS directories)."""
    dir_name = os.path.basename(dir_path)
    if dir_name.startswith("SC_") and dir_name.endswith("_CS"):
        return True
    return False


def is_in_skip_path(file_path):
    """Check if a file path contains any directory component that should be skipped."""
    parts = file_path.split(os.sep)
    for part in parts:
        if part.startswith("SC_") and part.endswith("_CS"):
            return True
    return False


def create_result_dict(sample_name, file_path, result_type, run_id):
    """Create a standardized result dictionary."""
    return {
        "sample_name": sample_name,
        "file_path": os.path.abspath(file_path),
        "type": result_type,
        "run_id": run_id,
    }


def find_h5_in_count_directory(count_dir, sample_dir, run_id):
    """Search for h5 files in a count directory with different naming patterns."""
    h5_patterns = [
        "sample_raw_feature_bc_matrix.h5",
        "raw_feature_bc_matrix.h5",
    ]

    # Check for standard naming patterns first
    for pattern in h5_patterns:
        h5_path = os.path.join(count_dir, pattern)
        if os.path.exists(h5_path):
            return create_result_dict(sample_dir, h5_path, "multi", run_id)

    # Fall back to searching for any h5 file containing "raw"
    h5_files = [
        f
        for f in os.listdir(count_dir)
        if f.endswith(".h5") and "raw" in f.lower()
    ]
    if h5_files:
        h5_path = os.path.join(count_dir, h5_files[0])
        return create_result_dict(sample_dir, h5_path, "multi", run_id)

    return None


def find_raw_h5_files_in_run(run_dir):
    """Find all raw feature matrix h5 files in a specific CellRanger run directory."""
    results = []
    run_id = os.path.basename(run_dir)

    # Check for traditional CellRanger count output
    raw_h5_path = os.path.join(run_dir, "outs", "raw_feature_bc_matrix.h5")
    if os.path.exists(raw_h5_path):
        results.append(create_result_dict(run_id, raw_h5_path, "count", run_id))
        return results

    # Check for CellRanger multi output
    per_sample_path = os.path.join(run_dir, "outs", "per_sample_outs")
    if not os.path.exists(per_sample_path):
        return results

    # Process each sample directory
    sample_dirs = [
        d
        for d in os.listdir(per_sample_path)
        if os.path.isdir(os.path.join(per_sample_path, d))
        and not should_skip_directory(d)
    ]

    for sample_dir in sample_dirs:
        count_dir = os.path.join(per_sample_path, sample_dir, "count")
        if not os.path.exists(count_dir):
            continue

        result = find_h5_in_count_directory(count_dir, sample_dir, run_id)
        if result:
            results.append(result)

    # If no results found, try a focused search
    if not results:
        for root, dirs, files in os.walk(per_sample_path):
            if is_in_skip_path(root):
                continue

            dirs[:] = [d for d in dirs if not should_skip_directory(d)]

            for file in files:
                if file in [
                    "sample_raw_feature_bc_matrix.h5",
                    "raw_feature_bc_matrix.h5",
                ]:
                    file_path = os.path.join(root, file)
                    parts = file_path.split(os.sep)
                    try:
                        sample_idx = parts.index("per_sample_outs") + 1
                        if sample_idx < len(parts):
                            sample_name = parts[sample_idx]
                            results.append(
                                create_result_dict(
                                    sample_name, file_path, "multi", run_id
                                )
                            )
                    except ValueError:
                        continue

    return results


def find_raw_h5_files(input_dir):
    """Find all raw feature matrix h5 files in the input directory."""
    results = []
    input_dir = os.path.abspath(input_dir)

    # If input_dir is a specific CellRanger run directory
    if os.path.exists(os.path.join(input_dir, "outs")):
        return find_raw_h5_files_in_run(input_dir)

    # Search for CellRanger outputs in subdirectories
    potential_run_dirs = []

    # Look for run directories at top level
    for item in os.listdir(input_dir):
        item_path = os.path.join(input_dir, item)
        if os.path.isdir(item_path) and os.path.exists(
            os.path.join(item_path, "outs")
        ):
            potential_run_dirs.append(item_path)

    # Look one level deeper if nothing found
    if not potential_run_dirs:
        for item in os.listdir(input_dir):
            item_path = os.path.join(input_dir, item)
            if os.path.isdir(item_path):
                for subitem in os.listdir(item_path):
                    subitem_path = os.path.join(item_path, subitem)
                    if os.path.isdir(subitem_path) and os.path.exists(
                        os.path.join(subitem_path, "outs")
                    ):
                        potential_run_dirs.append(subitem_path)

    # Process each potential run directory
    for run_dir in potential_run_dirs:
        results.extend(find_raw_h5_files_in_run(run_dir))

    return results


def extract_run_id_from_logs(file_path):
    """Extract run ID from CellRanger log files if available."""
    log_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(file_path))), "_log"
    )
    if os.path.exists(log_dir):
        log_files = glob.glob(os.path.join(log_dir, "*.log"))
        for log_file in log_files:
            with open(log_file, "r") as f:
                content = f.read()
                match = re.search(r"Run ID: ([a-zA-Z0-9_-]+)", content)
                if match:
                    return match.group(1)
    return f"cellranger_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def generate_lsf_script(sample_info, output_dir, params):
    """Generate an LSF script for CellBender processing."""
    sample_name = sample_info["sample_name"]
    input_file = sample_info["file_path"]
    run_id = sample_info.get("run_id", extract_run_id_from_logs(input_file))

    # Create output directory structure
    output_subdir = os.path.abspath(
        os.path.join(output_dir, run_id, sample_name)
        if sample_info["type"] == "multi"
        else os.path.join(output_dir, sample_name)
    )
    os.makedirs(output_subdir, exist_ok=True)

    output_file = os.path.join(
        output_subdir, f"{sample_name}_cellbender_output.h5"
    )
    lsf_script_path = os.path.join(
        output_subdir, f"run_cellbender_{sample_name}.lsf"
    )

    script_content = f"""#BSUB -P {params['project']}
#BSUB -W {params['walltime']}
#BSUB -q {params['queue']}
#BSUB -n {params['cores']}
#BSUB -R span[hosts=1]
#BSUB -R {params['gpu_model']}
#BSUB -gpu num={params['gpu_num']}
#BSUB -R rusage[mem={params['memory']}]
#BSUB -u {params['email']}
#BSUB -o {output_subdir}/output_{sample_name}_%J.stdout
#BSUB -eo {output_subdir}/error_{sample_name}_%J.stderr
#BSUB -L /bin/bash

# Generated LSF submission script for CellBender
# Sample: {sample_name}
# Input file: {input_file}
# Output file: {output_file}

export http_proxy=http://172.28.7.1:3128
export https_proxy=http://172.28.7.1:3128
export all_proxy=http://172.28.7.1:3128
export no_proxy=localhost,*.chimera.hpc.mssm.edu,172.28.0.0/16

source /hpc/users/tastac01/micromamba/etc/profile.d/conda.sh
conda init bash
conda activate {params['conda_env']}

# Load CUDA module if needed
ml cuda/{params['cuda_version']}

# Create output directory
mkdir -p {output_subdir}

# Redirect stdout and stderr using exec
exec 1> "{output_subdir}/output_{sample_name}.stdout"
exec 2> "{output_subdir}/error_{sample_name}.stderr"

echo "Starting CellBender for sample {sample_name} at $(date)"
echo "Input file: {input_file}"
echo "Output file: {output_file}"
echo "GPU devices available: $CUDA_VISIBLE_DEVICES"

cellbender remove-background \\
    --cuda \\
    --input {input_file} \\
    --output {output_file} \\

echo "Completed CellBender for sample {sample_name} at $(date)"
"""

    with open(lsf_script_path, "w") as f:
        f.write(script_content)

    return lsf_script_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate LSF scripts for CellBender processing"
    )

    # Required parameters
    required_group = parser.add_argument_group("required arguments")
    required_group.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing CellRanger outputs or a specific CellRanger run directory",
    )
    required_group.add_argument(
        "--output-dir", required=True, help="Directory for CellBender outputs"
    )
    required_group.add_argument(
        "--email", required=True, help="Email for job notifications"
    )

    # LSF job parameters
    lsf_group = parser.add_argument_group("LSF job parameters")
    lsf_group.add_argument(
        "--project",
        default="acc_untreatedIBD",
        help="LSF project (default: acc_untreatedIBD)",
    )
    lsf_group.add_argument(
        "--walltime", default="1:00", help="Wall time for jobs (default: 1:00)"
    )
    lsf_group.add_argument(
        "--queue", default="gpu", help="LSF queue (default: gpu)"
    )
    lsf_group.add_argument(
        "--cores", default="2", help="Number of cores (default: 2)"
    )
    lsf_group.add_argument(
        "--memory", default="4G", help="Memory per job (default: 4G)"
    )

    # GPU parameters
    gpu_group = parser.add_argument_group("GPU parameters")
    gpu_group.add_argument(
        "--gpu-model",
        default="h100nvl",
        help="GPU model: v100, a100, a10080g, h10080g, h100nvl, l40s (default: h100nvl)",
    )
    gpu_group.add_argument(
        "--gpu-num",
        default="1",
        help="Number of GPU cards per node (default: 1)",
    )
    gpu_group.add_argument(
        "--cuda-version",
        default="11.8",
        help="CUDA version to load (default: 11.8)",
    )

    # Environment parameters
    env_group = parser.add_argument_group("Environment parameters")
    env_group.add_argument(
        "--conda-env",
        default="cellbender",
        help="Conda environment name (default: cellbender)",
    )

    args = parser.parse_args()

    # Process directories and find files
    input_dir = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)
    sample_files = find_raw_h5_files(input_dir)

    if not sample_files:
        print(f"No raw feature matrix h5 files found in {input_dir}")
        return

    # Get unique run IDs and create parameters dictionary
    run_ids = set(sample["run_id"] for sample in sample_files)
    params = {
        "project": args.project,
        "walltime": args.walltime,
        "queue": args.queue,
        "cores": args.cores,
        "memory": args.memory,
        "email": args.email,
        "conda_env": args.conda_env,
        "gpu_model": args.gpu_model,
        "gpu_num": args.gpu_num,
        "cuda_version": args.cuda_version,
    }

    # Generate LSF scripts
    lsf_scripts = [
        generate_lsf_script(sample_info, output_dir, params)
        for sample_info in sample_files
    ]

    # Create run-specific submission scripts
    for run_id in run_ids:
        run_scripts = [
            script
            for script, sample in zip(lsf_scripts, sample_files)
            if sample["run_id"] == run_id
        ]

        submit_script_path = os.path.join(
            output_dir, f"submit_cellbender_jobs_{run_id}.sh"
        )
        with open(submit_script_path, "w") as f:
            f.write("#!/bin/bash\n\n")
            f.write(
                f"# Submit CellBender jobs for CellRanger run: {run_id}\n\n"
            )
            for script in run_scripts:
                f.write(f"bsub < {script}\n")

        os.chmod(submit_script_path, 0o755)

    # Create master submission script
    all_submit_script_path = os.path.join(
        output_dir, "submit_all_cellbender_jobs.sh"
    )
    with open(all_submit_script_path, "w") as f:
        f.write("#!/bin/bash\n\n")
        f.write("# Submit all CellBender jobs for all runs\n\n")
        for script in lsf_scripts:
            f.write(f"bsub < {script}\n")

    os.chmod(all_submit_script_path, 0o755)

    print("\nGenerated {count} LSF scripts".format(count=len(lsf_scripts)))
    print(
        "To submit all jobs, run: {script}".format(
            script=all_submit_script_path
        )
    )
    print(
        "Or submit jobs for specific runs using the run-specific submission scripts"
    )


if __name__ == "__main__":
    main()
