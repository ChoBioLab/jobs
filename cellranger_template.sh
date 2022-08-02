#!/bin/bash
#BSUB -J cr_count
#BSUB -P acc_untreatedIBD
#BSUB -W 02:00
#BSUB -q express
#BSUB -n 2
#BSUB -R rusage[mem=64GB]
#BSUB -R span[hosts=1]
#BSUB -o ../logs/output_%J.stdout
#BSUB -eo ../logs/error_%J.stderr
#BSUB -L /bin/bash

# VELOCYTO MINERVA PARAMS
# module load anaconda3
# ml python/3.7.3
# ml velocyto
# source activate /hpc/packages/minerva-centos7/velocyto/0.17/velocyto
# ml samtools

# README
# this script should be executed from site of output dir
# fastqs should be arranged in dirs labeled by sample
# make note not to leave trailing / in param paths

set -a

# params
PIPELINE=			        # name of cellranger pipeline
PROJ_DIR=			        # /path/to/proj/dir
REF_DIR=                    # /path/to/gene/ref
GENE_REF=                   # name of gene ref
SAMPLE_DIR=$PROJ_DIR/		# /proj/subdir/to/fastqs
CELLS=				        # expected cell count
CHEM=auto			        # chemistry type (e.g. fiveprime)
MEM=                        # memory cap

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

# cellranger function
crProcess () {
    cellranger $PIPELINE \
        --id=$1 \
        --$GENOME_LABEL=$REF_DIR/$GENE_REF \
        --fastqs=$SAMPLE_DIR/$1 \
        --sample=$(ls SAMPLE_DIR/$1 | head -1 | cut -f1 -d "_") \
        --expect-cells=$CELLS \
        --chemistry=$CHEM \
        --localmem=$MEM
    }

# velocyto function
vcProcess () {
    velocyto run10x \
        $OUT_DIR/$1 \
        $REF_DIR/$GENE_REF/genes/genes.gtf
    }

export -f crProcess
export -f vcProcess

# cellranger execution with gnuparallel
parallel crProcess ::: $(ls $SAMPLE_DIR)

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

source $HOME/miniconda3/etc/profile.d/conda.sh
conda activate velocyto

# velocyto execution with gnuparallel
parallel vcProcess ::: $(find $OUT_DIR -mindepth 1 -maxdepth 1 -type d -printf '%f\n')

