import pandas as pd
import glob
import os
from pathlib import Path
import argparse
import re

def clean_complex_value(value):
    """Handle complex string formats"""
    if isinstance(value, str):
        value = value.replace(',', '')
        value = re.sub(r'[^0-9.]', '', value)
        return float(value)
    return value

def clean_percentage(value):
    """Convert percentage values to fractions and round to 3 sig figs"""
    if isinstance(value, str):
        if '%' in value:
            value = re.sub(r'[^0-9.]', '', value)
            # Convert to fraction and round to 4 sig figs
            return round(float(value) / 100, 4)
    return value

def process_metrics_summaries(cellranger_outs_dir, output_dir=None):
    metrics_files = glob.glob(os.path.join(cellranger_outs_dir, "per_sample_outs", "*", "metrics_summary.csv"))

    if not metrics_files:
        raise FileNotFoundError(f"No metrics_summary.csv files found in {cellranger_outs_dir}/per_sample_outs/*/")

    # Define metrics for both outputs
    individual_metric_names = [
        'Cells',
        'Confidently mapped reads in cells',
        'Estimated UMIs from genomic DNA',
        'Estimated UMIs from genomic DNA per unspliced probe',
        'Median UMI counts per cell',
        'Median genes per cell',
        'Median reads per cell',
        'Number of reads from cells called from this sample',
        'Reads confidently mapped to filtered probe set',
        'Reads confidently mapped to probe set',
        'Reads mapped to probe set',
        'Total genes detected'
    ]

    pooled_metric_names = [
        'Estimated UMIs from genomic DNA',
        'Estimated UMIs from genomic DNA per unspliced probe',
        'Number of reads',
        'Number of short reads skipped',
        'Q30 GEM barcodes',
        'Q30 RNA read',
        'Q30 UMI',
        'Q30 barcodes',
        'Q30 probe barcodes',
        'Confidently mapped reads in cells',
        'Estimated number of cells',
        'Fraction of initial cell barcodes passing high occupancy GEM filtering',
        'Mean reads per cell',
        'Number of reads in the library',
        'Reads confidently mapped to filtered probe set',
        'Reads confidently mapped to probe set',
        'Reads mapped to probe set',
        'Sequencing saturation',
        'Valid GEM barcodes',
        'Valid UMIs',
        'Valid barcodes',
        'Valid probe barcodes'
    ]

    # Process per-sample metrics
    all_metrics = []
    for file_path in metrics_files:
        sample_name = Path(file_path).parent.name
        df = pd.read_csv(file_path)
        df['Sample'] = sample_name
        all_metrics.append(df)

    combined_df = pd.concat(all_metrics, ignore_index=True)

    # Create individual metrics summary
    individual_metrics = combined_df[
        (combined_df['Category'] == 'Cells') & 
        (combined_df['Metric Name'].isin(individual_metric_names))
    ].pivot(
        index='Sample',
        columns='Metric Name',
        values='Metric Value'
    )

    # Clean numeric values in individual_metrics first
    for col in individual_metrics.columns:
        if individual_metrics[col].dtype == 'object':
            if any('%' in str(x) for x in individual_metrics[col] if isinstance(x, str)):
                individual_metrics[col] = individual_metrics[col].apply(clean_percentage)
            else:
                individual_metrics[col] = individual_metrics[col].apply(clean_complex_value)

    # Get estimated number of cells from pooled metrics and clean it
    estimated_cells = combined_df[
        (combined_df['Category'] == 'Library') & 
        (combined_df['Metric Name'] == 'Estimated number of cells')
    ]['Metric Value'].iloc[0]
    estimated_cells = clean_complex_value(estimated_cells)

    # Calculate Cells detected in this sample as fraction and round to 3 sig figs
    individual_metrics['Cells detected in this sample'] = (individual_metrics['Cells'] / estimated_cells).round(3)

    # Process pooled metrics (using first file only)
    df = pd.read_csv(metrics_files[0])
    pooled_df = df[
        (df['Category'] == 'Library') &
        (df['Library Type'] == 'Gene Expression') &
        (df['Metric Name'].isin(pooled_metric_names))
    ][['Metric Name', 'Metric Value']]

    # Clean up numeric values in pooled_df
    if isinstance(pooled_df, pd.DataFrame):
        pooled_df['Metric Value'] = pooled_df.apply(
            lambda row: clean_percentage(row['Metric Value']) 
            if isinstance(row['Metric Value'], str) and '%' in row['Metric Value']
            else clean_complex_value(row['Metric Value']),
            axis=1
        )

    # Save outputs
    if output_dir is None:
        output_dir = os.path.join(cellranger_outs_dir, 'analysis')
    os.makedirs(output_dir, exist_ok=True)

    # Save individual metrics summary
    individual_metrics_output = os.path.join(output_dir, 'individual_metrics.csv')
    individual_metrics.to_csv(individual_metrics_output)
    print(f"Saved individual metrics to: {individual_metrics_output}")

    # Save pooled metrics
    pooled_output = os.path.join(output_dir, 'pooled_metrics.csv')
    pooled_df.to_csv(pooled_output, index=False)
    print(f"Saved pooled metrics to: {pooled_output}")

    return individual_metrics, pooled_df

def main():
    parser = argparse.ArgumentParser(
        description='Process CellRanger Multi metrics summaries',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--cellranger-dir',
        required=True,
        metavar='DIR',
        help='Path to CellRanger Multi output directory (containing per_sample_outs/)'
    )

    parser.add_argument(
        '--output-dir',
        metavar='DIR',
        help='Custom output directory (default: creates "analysis" in cellranger directory)'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress printing of summary metrics'
    )

    args = parser.parse_args()

    try:
        individual_metrics, pooled_metrics = process_metrics_summaries(
            args.cellranger_dir,
            args.output_dir
        )

        if not args.quiet:
            print("\nIndividual metrics summary:")
            print(individual_metrics)
            print("\nPooled metrics:")
            print(pooled_metrics)

    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()

