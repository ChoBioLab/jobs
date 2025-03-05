#!/usr/bin/env python3

import argparse
import glob
import logging
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
    return f"cellranger_run_{datetime.now().strftime('%Y-%m-%d')}"


def generate_lsf_script_multi(sample_info, parent_dir, params, multi_lib_id):
    """Generate an LSF script for CellBender processing for multi samples."""
    sample_name = sample_info["sample_name"]
    input_file = sample_info["file_path"]
    run_id = sample_info.get("run_id", extract_run_id_from_logs(input_file))

    # Create sample-specific subdirectory
    sample_dir = os.path.join(parent_dir, sample_name)
    os.makedirs(sample_dir, exist_ok=True)

    # Log the input/output mapping
    logging.info(f"Processing sample: {sample_name}")
    logging.info(f"Input file: {input_file}")
    logging.info(f"Output directory: {sample_dir}")

    output_file = os.path.join(sample_dir, f"{sample_name}_cellbender_output.h5")
    lsf_script_path = os.path.join(sample_dir, f"run_cellbender_{sample_name}.lsf")

    script_content = f"""#BSUB -P {params['project']}
#BSUB -J {sample_name}_cellbender
#BSUB -W {params['walltime']}
#BSUB -q {params['queue']}
#BSUB -n {params['cores']}
#BSUB -R span[hosts=1]
#BSUB -R {params['gpu_model']}
#BSUB -gpu num={params['gpu_num']}
#BSUB -R rusage[mem={params['memory']}]
#BSUB -u {params['email']}
#BSUB -o {sample_dir}/output_{sample_name}_%J.stdout
#BSUB -eo {sample_dir}/error_{sample_name}_%J.stderr
#BSUB -L /bin/bash
#BSUB -cwd {sample_dir}

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

# Ensure we're in the sample directory
cd {sample_dir}
echo "Working directory: $(pwd)"

# Redirect stdout and stderr using exec
exec 1> "{sample_dir}/output_{sample_name}.stdout"
exec 2> "{sample_dir}/error_{sample_name}.stderr"

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


def generate_lsf_script_single(sample_info, output_dir, params):
    """Generate an LSF script for CellBender processing for single samples."""
    sample_name = sample_info["sample_name"]
    input_file = sample_info["file_path"]
    run_id = sample_info.get("run_id", extract_run_id_from_logs(input_file))

    # Log the input/output mapping
    logging.info(f"Processing sample: {sample_name}")
    logging.info(f"Input file: {input_file}")
    logging.info(f"Output directory: {output_dir}")

    output_file = os.path.join(output_dir, f"{sample_name}_cellbender_output.h5")
    lsf_script_path = os.path.join(output_dir, f"run_cellbender_{sample_name}.lsf")

    script_content = f"""#BSUB -P {params['project']}
#BSUB -J {sample_name}_cellbender
#BSUB -W {params['walltime']}
#BSUB -q {params['queue']}
#BSUB -n {params['cores']}
#BSUB -R span[hosts=1]
#BSUB -R {params['gpu_model']}
#BSUB -gpu num={params['gpu_num']}
#BSUB -R rusage[mem={params['memory']}]
#BSUB -u {params['email']}
#BSUB -o {output_dir}/output_{sample_name}_%J.stdout
#BSUB -eo {output_dir}/error_{sample_name}_%J.stderr
#BSUB -L /bin/bash
#BSUB -cwd {output_dir}

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

# Ensure we're in the output directory
cd {output_dir}
echo "Working directory: $(pwd)"

# Redirect stdout and stderr using exec
exec 1> "{output_dir}/output_{sample_name}.stdout"
exec 2> "{output_dir}/error_{sample_name}.stderr"

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

    # Optional multi-lib-id parameter
    parser.add_argument(
        "--multi-lib-id",
        help="Library ID for grouping multi outputs (required for CellRanger multi outputs)",
        default=None,
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
        "--memory", default="16G", help="Memory per job (default: 16G)"
    )

    # GPU parameters
    gpu_group = parser.add_argument_group("GPU parameters")
    gpu_group.add_argument(
        "--gpu-model",
        default="a100",
        help="GPU model: v100, a100, a10080g, h10080g, h100nvl, l40s (default: a100)",
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
    sample_files = find_raw_h5_files(input_dir)

    if not sample_files:
        print(f"No raw feature matrix h5 files found in {input_dir}")
        return

    # Determine if this is a multi run
    is_multi_run = any(sample["type"] == "multi" for sample in sample_files)

    # Validate multi-lib-id requirement for multi runs
    if is_multi_run and not args.multi_lib_id:
        print("Error: --multi-lib-id is required for CellRanger multi outputs")
        return

    # Set up parameters dictionary
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

    # Base output directory
    base_output_dir = os.path.abspath(args.output_dir)
    date_stamp = datetime.now().strftime("%Y-%m-%d")

    # Handle multi and non-multi runs differently
    if is_multi_run and args.multi_lib_id:
        # For multi runs, create a single parent directory
        parent_dir = os.path.join(base_output_dir, f"{args.multi_lib_id}_{date_stamp}")
        os.makedirs(parent_dir, exist_ok=True)

        # Setup logging for multi run
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(os.path.join(parent_dir, "prep-cellbender.log")),
                logging.StreamHandler(),
            ],
        )

        # Generate LSF scripts for all samples in the multi run
        lsf_scripts = []
        for sample_info in sample_files:
            # Create sample-specific subdirectory
            sample_name = sample_info["sample_name"]
            sample_dir = os.path.join(parent_dir, sample_name)
            os.makedirs(sample_dir, exist_ok=True)

            # Generate LSF script
            lsf_script = generate_lsf_script_multi(sample_info, parent_dir, params, args.multi_lib_id)
            lsf_scripts.append(lsf_script)

        # Create a single submission script for all samples
        submit_script_path = os.path.join(parent_dir, "submit_cellbender_jobs.sh")
        with open(submit_script_path, "w") as f:
            f.write("#!/bin/bash\n\n")
            f.write(f"# Submit CellBender jobs for CellRanger multi run: {args.multi_lib_id}\n\n")
            for script in lsf_scripts:
                f.write(f"bsub < {script}\n")
                f.write("sleep 2\n")

        os.chmod(submit_script_path, 0o755)

        logging.info(f"\nGenerated {len(lsf_scripts)} LSF scripts for multi run")
        logging.info(f"Submission script created at: {submit_script_path}")

    else:
        # For non-multi runs, create a separate directory for each sample
        for sample_info in sample_files:
            sample_name = sample_info["sample_name"]
            sample_output_dir = os.path.join(base_output_dir, f"{sample_name}_{date_stamp}")
            os.makedirs(sample_output_dir, exist_ok=True)

            # Setup logging for this sample
            sample_log_handler = logging.FileHandler(os.path.join(sample_output_dir, "prep-cellbender.log"))
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(levelname)s - %(message)s",
                handlers=[sample_log_handler, logging.StreamHandler()],
                force=True  # Reset handlers for each sample
            )

            # Generate LSF script for this sample
            lsf_script = generate_lsf_script_single(sample_info, sample_output_dir, params)

            # Create a submission script for this sample
            submit_script_path = os.path.join(sample_output_dir, "submit_cellbender_jobs.sh")
            with open(submit_script_path, "w") as f:
                f.write("#!/bin/bash\n\n")
                f.write(f"# Submit CellBender job for sample: {sample_name}\n\n")
                f.write(f"bsub < {lsf_script}\n")

            os.chmod(submit_script_path, 0o755)

            logging.info(f"Generated LSF script for sample {sample_name}")
            logging.info(f"Submission script created at: {submit_script_path}")

            # Close the log handler for this sample
            sample_log_handler.close()
            logging.getLogger().removeHandler(sample_log_handler)

        print(f"\nGenerated LSF scripts for individual samples")
        print("Each sample has its own directory with submission script")


if __name__ == "__main__":
    main()

