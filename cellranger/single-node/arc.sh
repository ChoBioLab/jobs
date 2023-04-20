#!/bin/bash
#BSUB -J cr_count
#BSUB -P acc_untreatedIBD
#BSUB -W 02:00
#BSUB -q express
#BSUB -n 2
#BSUB -R rusage[mem=64GB]
#BSUB -R span[hosts=1]
#BSUB -o output_%J.stdout
#BSUB -eo error_%J.stderr
#BSUB -L /bin/bash

# README
# this script should be executed from site of output dir
# fastqs should be arranged in dirs labeled by sample
# make note not to leave trailing / in param paths
# note the number PARALLEL * CORES will be actual number of threads

set -a

# params
PIPELINE=count			        # name of cellranger pipeline
PROJ_DIR=                       # /path/to/proj/dir
REF_DIR=                        # /path/to/gene/ref
GENE_REF=refdata-cellranger-arc-GRCh38-2020-A-2.0.0	    # name of gene ref
LIB_DIR=$PROJ_DIR/analysis/cellranger	                # DIR containing libraries.csv
MEM=                            # memory total for cellranger
CORES=                          # core cap for cellranger
PARALLEL=                       # number of parallel tasks

################################################################################

exec >> cr_${PIPELINE}_`date '+%F_%H%M'`.log
exec 2>&1

OUT_DIR=cr_arc_${PIPELINE}_`date '+%F_%H%M'`
mkdir -p $PROJ_DIR/analysis/cellranger/$OUT_DIR && cd $_

# core cellranger function
crProcess () {
    cellranger-arc $PIPELINE \
        --id=$(echo $1 | sed 's/_libraries.csv//') \
        --reference=$REF_DIR/$GENE_REF \
        --libraries=$LIB_DIR/$1 \
        --localmem=$MEM \
        --localcores=$CORES
    }

export -f crProcess

# cellranger function run with gnuparallel
TARGETS=$(ls $LIB_DIR/*_libraries.csv | xargs -n 1 basename)
parallel -j $PARALLEL crProcess ::: $TARGETS

mv $LIB_DIR/*_libraries.csv .

# run cellranger summarizer
cd $(ls -d */ | head -n 1)
head -n 1 outs/summary.csv > ../combined_metrics.csv
cd ../
sed -i 's/^/Sample,/' combined_metrics.csv

for i in $(/bin/ls -d */)
do
    LABEL=$(echo $i | sed 's/\///g')
    METRICS=$(tail -n 1 ${i}outs/summary.csv)
    echo "${LABEL},${METRICS}" >> combined_metrics.csv
done

