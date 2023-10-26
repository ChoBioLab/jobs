#!/bin/bash
#BSUB -P acc_untreatedIBD
#BSUB -W 48:00
#BSUB -q premium
#BSUB -J <JOB NAME>
#BSUB -o output_%J.stdout
#BSUB -e error_%J.sterr

# README
# this script should be executed from site of output dir
# fastqs should be arranged in dirs labeled using the Standard ID
# make note not to leave trailing / in param paths
# all cluster confg files (config.json, lsf.template, retry.json)
# should be present in the same location given for lsf.template
#
# this pipeline expects a library.csv and feature_ref.csv file
# to be present at the site of execution

# MINERVA PARAMS
ml cellranger/7.1.0

set -a

# params
PIPELINE=			        # name of cellranger pipeline
PROJ_DIR=			        # /path/to/proj/dir
REF_DIR=                    # /path/to/gene/ref
GENE_REF=                   # name of gene ref
LIB_DIR=$PROJ_DIR/		    # /proj/subdir/to/libraries.csv
CLUST_TEMPLATE=		        # /path/to/lsf.template cluster file

################################################################################

exec >> cr_${PIPELINE}_`date '+%F_%H%M'`.log
exec 2>&1

# needed because pipelines differ for name of reference genome
if [[ $PIPELINE == "count" ]]
then
    GENOME_LABEL=transcriptome
else
    GENOME_LABEL=reference
fi

OUT_DIR=$PROJ_DIR/analysis/cellranger/cr_${PIPELINE}_`date '+%F_%H%M'`
mkdir -p $OUT_DIR && cd $_
MRO_DISK_SPACE_CHECK=disable

# cellranger function
crProcess () {
    cellranger $PIPELINE \
        --id=$(echo $1 | sed 's/_libraries.csv//') \
        --$GENOME_LABEL=$REF_DIR/$GENE_REF \
        --libraries=$LIB_DIR/$1 \
        --feature-ref=$LIB_DIR/feature_ref.csv \
    	--jobmode=$CLUST_TEMPLATE
    }

    export -f crProcess

# cellranger execution
for i in $(ls $LIB_DIR/*_libraries.csv | xargs -n 1 basename)
do
    crProcess $i
done

mv $LIB_DIR/*_libraries.csv .
mv $LIB_DIR/feature_ref.csv .

# run cellranger summarizer
cd $(ls -d */ | head -n 1)
head -n 1 outs/metrics_summary.csv > ../combined_metrics.csv
cd ../
sed -i 's/^/Sample,/' combined_metrics.csv

for i in $(/bin/ls -d */)
do
    LABEL=$(echo $i | sed 's/\///g')
    METRICS=$(tail -n 1 ${i}outs/metrics_summary.csv)
    echo "${LABEL},${METRICS}" >> combined_metrics.csv
done

