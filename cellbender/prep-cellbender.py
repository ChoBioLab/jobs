#!/usr/bin/env python3

import os
import glob
import argparse
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

def find_raw_h5_files_in_run(run_dir):
    """Find all raw feature matrix h5 files in a specific CellRanger run directory."""
    results = []

    # Check if this is a traditional CellRanger count output
    raw_h5_path = os.path.join(run_dir, "outs", "raw_feature_bc_matrix.h5")
    if os.path.exists(raw_h5_path):
        sample_name = os.path.basename(run_dir)
        results.append({
            'sample_name': sample_name,
            'file_path': os.path.abspath(raw_h5_path),
            'type': 'count',
            'run_id': sample_name
        })
        return results

    # Check if this is a CellRanger multi output - focus on per_sample_outs
    per_sample_path = os.path.join(run_dir, "outs", "per_sample_outs")
    if os.path.exists(per_sample_path):
        print(f"Found per_sample_outs directory: {per_sample_path}")

        # List sample directories
        sample_dirs = [d for d in os.listdir(per_sample_path) 
                      if os.path.isdir(os.path.join(per_sample_path, d)) 
                      and not should_skip_directory(d)]

        print(f"Sample directories found: {', '.join(sample_dirs)}")

        # Check each sample directory for count directory and h5 files
        for sample_dir in sample_dirs:
            count_dir = os.path.join(per_sample_path, sample_dir, "count")
            if os.path.exists(count_dir):
                print(f"  - {sample_dir} has count directory")

                # Check for sample_raw_feature_bc_matrix.h5 (CellRanger multi format)
                raw_h5 = os.path.join(count_dir, "sample_raw_feature_bc_matrix.h5")
                if os.path.exists(raw_h5):
                    print(f"    - Found sample_raw_feature_bc_matrix.h5")
                    results.append({
                        'sample_name': sample_dir,
                        'file_path': os.path.abspath(raw_h5),
                        'type': 'multi',
                        'run_id': os.path.basename(run_dir)
                    })
                else:
                    # Also check for standard raw_feature_bc_matrix.h5 as fallback
                    raw_h5 = os.path.join(count_dir, "raw_feature_bc_matrix.h5")
                    if os.path.exists(raw_h5):
                        print(f"    - Found raw_feature_bc_matrix.h5")
                        results.append({
                            'sample_name': sample_dir,
                            'file_path': os.path.abspath(raw_h5),
                            'type': 'multi',
                            'run_id': os.path.basename(run_dir)
                        })
                    else:
                        print(f"    - No raw feature matrix h5 file found")

                        # List files in count directory to see what's available
                        count_files = os.listdir(count_dir)
                        h5_files = [f for f in count_files if f.endswith('.h5')]
                        if h5_files:
                            print(f"    - Available h5 files: {', '.join(h5_files)}")

                            # Look for any file that might be a raw feature matrix
                            raw_candidates = [f for f in h5_files if "raw" in f.lower()]
                            if raw_candidates:
                                print(f"    - Potential raw matrix candidates: {', '.join(raw_candidates)}")
                                # Use the first candidate
                                raw_h5 = os.path.join(count_dir, raw_candidates[0])
                                print(f"    - Using {raw_candidates[0]} as raw feature matrix")
                                results.append({
                                    'sample_name': sample_dir,
                                    'file_path': os.path.abspath(raw_h5),
                                    'type': 'multi',
                                    'run_id': os.path.basename(run_dir)
                                })
                        else:
                            print(f"    - No h5 files found in count directory")
            else:
                print(f"  - {sample_dir} does NOT have count directory")

    # If no results found through direct paths, try a more focused search
    if not results:
        print(f"No results found through direct paths, trying focused search...")

        # Focus specifically on per_sample_outs
        for root, dirs, files in os.walk(os.path.join(run_dir, "outs", "per_sample_outs")):
            # Skip directories that should be skipped
            dirs[:] = [d for d in dirs if not should_skip_directory(d)]

            # Skip if we're in a path that should be skipped
            if is_in_skip_path(root):
                continue

            for file in files:
                # Look for both naming conventions
                if file == "sample_raw_feature_bc_matrix.h5" or file == "raw_feature_bc_matrix.h5":
                    file_path = os.path.join(root, file)
                    print(f"Found raw h5 file: {file_path}")

                    # Extract sample name from path
                    parts = file_path.split(os.sep)
                    sample_idx = parts.index("per_sample_outs") + 1 if "per_sample_outs" in parts else -1

                    if sample_idx != -1 and sample_idx < len(parts):
                        sample_name = parts[sample_idx]
                        results.append({
                            'sample_name': sample_name,
                            'file_path': os.path.abspath(file_path),
                            'type': 'multi',
                            'run_id': os.path.basename(run_dir)
                        })

    return results

def find_raw_h5_files(input_dir):
    """Find all raw feature matrix h5 files in the input directory."""
    results = []

    # Convert input_dir to absolute path
    input_dir = os.path.abspath(input_dir)

    # If input_dir is a specific CellRanger run directory
    if os.path.exists(os.path.join(input_dir, "outs")):
        return find_raw_h5_files_in_run(input_dir)

    # Otherwise, search for CellRanger outputs in subdirectories
    # Look for directories that might be CellRanger run directories
    potential_run_dirs = []
    for item in os.listdir(input_dir):
        item_path = os.path.join(input_dir, item)
        if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "outs")):
            potential_run_dirs.append(item_path)

    # If no potential run directories found at the top level, look one level deeper
    if not potential_run_dirs:
        for item in os.listdir(input_dir):
            item_path = os.path.join(input_dir, item)
            if os.path.isdir(item_path):
                for subitem in os.listdir(item_path):
                    subitem_path = os.path.join(item_path, subitem)
                    if os.path.isdir(subitem_path) and os.path.exists(os.path.join(subitem_path, "outs")):
                        potential_run_dirs.append(subitem_path)

    # Process each potential run directory
    for run_dir in potential_run_dirs:
        run_results = find_raw_h5_files_in_run(run_dir)
        results.extend(run_results)

    return results

def extract_run_id_from_logs(file_path):
    """Extract run ID from CellRanger log files if available."""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(file_path))), "_log")
    if os.path.exists(log_dir):
        log_files = glob.glob(os.path.join(log_dir, "*.log"))
        for log_file in log_files:
            with open(log_file, 'r') as f:
                content = f.read()
                # Look for run ID in log content
                match = re.search(r'Run ID: ([a-zA-Z0-9_-]+)', content)
                if match:
                    return match.group(1)

    # If no run ID found, use timestamp
    return f"cellranger_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

def generate_lsf_script(sample_info, output_dir, params):
    """Generate an LSF script for CellBender processing."""
    sample_name = sample_info['sample_name']
    input_file = sample_info['file_path']  # Already absolute path
    run_id = sample_info.get('run_id', extract_run_id_from_logs(input_file))

    # Create output directory structure with absolute paths
    if sample_info['type'] == 'multi':
        output_subdir = os.path.abspath(os.path.join(output_dir, run_id, sample_name))
    else:
        output_subdir = os.path.abspath(os.path.join(output_dir, sample_name))

    os.makedirs(output_subdir, exist_ok=True)

    output_file = os.path.join(output_subdir, f"{sample_name}_cellbender_output.h5")
    lsf_script_path = os.path.join(output_subdir, f"run_cellbender_{sample_name}.lsf")

    with open(lsf_script_path, 'w') as f:
        f.write(f"""#BSUB -P {params['project']}
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
    --expected-cells {params.get('expected_cells', 3000)} \\
    --total-droplets-included {params.get('total_droplets', 25000)} \\
    --fpr {params.get('fpr', 0.01)} \\
    --epochs {params.get('epochs', 150)}

echo "Completed CellBender for sample {sample_name} at $(date)"
""")

    return lsf_script_path

def main():
    parser = argparse.ArgumentParser(description='Generate LSF scripts for CellBender processing')

    # Required parameters
    required_group = parser.add_argument_group('required arguments')
    required_group.add_argument('--input-dir', required=True, help='Directory containing CellRanger outputs or a specific CellRanger run directory')
    required_group.add_argument('--output-dir', required=True, help='Directory for CellBender outputs')
    required_group.add_argument('--email', required=True, help='Email for job notifications')

    # LSF job parameters
    lsf_group = parser.add_argument_group('LSF job parameters')
    lsf_group.add_argument('--project', default='acc_untreatedIBD', help='LSF project (default: acc_untreatedIBD)')
    lsf_group.add_argument('--walltime', default='1:00', help='Wall time for jobs (default: 1:00)')
    lsf_group.add_argument('--queue', default='gpu', help='LSF queue (default: gpu)')
    lsf_group.add_argument('--cores', default='2', help='Number of cores (default: 2)')
    lsf_group.add_argument('--memory', default='4G', help='Memory per job (default: 4G)')

    # GPU parameters
    gpu_group = parser.add_argument_group('GPU parameters')
    gpu_group.add_argument('--gpu-model', default='h100nvl',
                          help='GPU model: v100, a100, a10080g, h10080g, h100nvl, l40s (default: h100nvl)')
    gpu_group.add_argument('--gpu-num', default='1', help='Number of GPU cards per node (default: 1)')
    gpu_group.add_argument('--cuda-version', default='11.8', help='CUDA version to load (default: 11.8)')

    # Environment parameters
    env_group = parser.add_argument_group('Environment parameters')
    env_group.add_argument('--conda-env', default='cellbender', help='Conda environment name (default: cellbender)')

    # CellBender parameters
    cellbender_group = parser.add_argument_group('CellBender parameters')
    cellbender_group.add_argument('--expected-cells', default='3000', help='Expected number of cells (default: 3000)')
    cellbender_group.add_argument('--total-droplets', default='25000', help='Total droplets to include (default: 25000)')
    cellbender_group.add_argument('--fpr', default='0.01', help='False positive rate (default: 0.01)')
    cellbender_group.add_argument('--epochs', default='150', help='Number of training epochs (default: 150)')

    args = parser.parse_args()

    # Convert input and output directories to absolute paths
    input_dir = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)

    # Find all raw feature matrix h5 files
    print(f"Searching for raw feature matrix h5 files in {input_dir}...")
    print(f"Note: Looking for sample_raw_feature_bc_matrix.h5 or raw_feature_bc_matrix.h5 in per_sample_outs")
    sample_files = find_raw_h5_files(input_dir)

    if not sample_files:
        print(f"No raw feature matrix h5 files found in {input_dir}")
        return

    # Get unique run IDs
    run_ids = set(sample['run_id'] for sample in sample_files)
    print(f"Found samples from {len(run_ids)} CellRanger runs: {', '.join(run_ids)}")

    print(f"Found {len(sample_files)} samples to process:")
    for sample in sample_files:
        print(f"  - {sample['sample_name']} ({sample['type']}) from {sample['run_id']}")

    # Create parameters dictionary
    params = {
        'project': args.project,
        'walltime': args.walltime,
        'queue': args.queue,
        'cores': args.cores,
        'memory': args.memory,
        'email': args.email,
        'conda_env': args.conda_env,
        'gpu_model': args.gpu_model,
        'gpu_num': args.gpu_num,
        'cuda_version': args.cuda_version,
        'expected_cells': args.expected_cells,
        'total_droplets': args.total_droplets,
        'fpr': args.fpr,
        'epochs': args.epochs
    }

    # Generate LSF scripts
    lsf_scripts = []
    for sample_info in sample_files:
        lsf_script = generate_lsf_script(sample_info, output_dir, params)
        lsf_scripts.append(lsf_script)

    # Create submission scripts for each run ID
    for run_id in run_ids:
        # Filter scripts for this run ID
        run_scripts = [script for script, sample in zip(lsf_scripts, sample_files) if sample['run_id'] == run_id]

        # Create a submission script specific to this run
        submit_script_path = os.path.join(output_dir, f"submit_cellbender_jobs_{run_id}.sh")
        with open(submit_script_path, 'w') as f:
            f.write("#!/bin/bash\n\n")
            f.write(f"# Submit CellBender jobs for CellRanger run: {run_id}\n\n")
            for script in run_scripts:
                f.write(f"bsub < {script}\n")

        os.chmod(submit_script_path, 0o755)
        print(f"\nGenerated submission script for run {run_id}: {submit_script_path}")

    # Also create a master submission script for all jobs
    all_submit_script_path = os.path.join(output_dir, "submit_all_cellbender_jobs.sh")
    with open(all_submit_script_path, 'w') as f:
        f.write("#!/bin/bash\n\n")
        f.write("# Submit all CellBender jobs for all runs\n\n")
        for script in lsf_scripts:
            f.write(f"bsub < {script}\n")

    os.chmod(all_submit_script_path, 0o755)

    print(f"\nGenerated {len(lsf_scripts)} LSF scripts")
    print(f"To submit all jobs, run: {all_submit_script_path}")
    print(f"Or submit jobs for specific runs using the run-specific submission scripts")

if __name__ == "__main__":
    main()

