#!/bin/bash
#BSUB -P acc_untreatedIBD
#BSUB -W 48:00
#BSUB -q premium
#BSUB -J <JOB NAME>
#BSUB -o output_%J.stdout
#BSUB -e error_%J.sterr

# README
# this script should be executed from site of output dir
# fastqs should be arranged in dirs labeled by sample
# make note not to leave trailing / in param paths
# all cluster confg files (config.json, lsf.template, retry.json)
# should be present in the same location given for lsf.template

# MINERVA PARAMS 
# ml cellranger-arc/2.0.2

set -a

# params
PIPELINE=        	    # name of cellranger pipeline
PROJ_DIR=              	# /path/to/proj/dir
REF_DIR=               	# /path/to/gene/ref
GENE_REF=    		    # name of gene ref
LIB_DIR=$PROJ_DIR/     	# DIR containing libraries.csv
CLUST_TEMPLATE=		    # /path/to/lsf.template cluster file

################################################################################

exec >> cr-arc_${PIPELINE}_`date '+%F_%H%M'`.log
exec 2>&1

OUT_DIR=cr_arc_${PIPELINE}_`date '+%F_%H%M'`
mkdir -p $PROJ_DIR/analysis/cellranger/$OUT_DIR && cd $_
MRO_DISK_SPACE_CHECK=disable

# core cellranger function
crProcess () {
    cellranger-arc $PIPELINE \
        --id=$(echo $1 | sed 's/_libraries.csv//') \
        --reference=$REF_DIR/$GENE_REF \
        --libraries=$LIB_DIR/$1 \
    	--jobmode=$CLUST_TEMPLATE
    }

export -f crProcess

# cellranger function
TARGETS=$(ls $LIB_DIR/*_libraries.csv | xargs -n 1 basename)
for i in $TARGETS
do
    crProcess $i
done

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

