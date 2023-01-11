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

set -a

# params
PROJ_DIR=		# /path/to/proj/dir
SAMPLE_DIR=$PROJ_DIR/	# /proj/subdir/to/fastqs
T=			# /path/to/tags.csv
CELLS=			# expected cell count

################################################################################



OUT_DIR=cs_`date '+%F_%H%M'`
mkdir -p $PROJ_DIR/analysis/cite_seq_count/$OUT_DIR && cd $_

# core cellranger function
csProcess () {
	CITE-seq-Count \
		-R1 $SAMPLE_DIR/$1/*_R1_*.fastq.gz \
		-R2 $SAMPLE_DIR/$1/*_R2_*.fastq.gz \
		-t $T \
		-cbf 1 \
		-cbl 16 \
		-umif 17 \
		-umil 26 \
		-cells $CELLS \
		-o $1
	}
#done

export -f csProcess

# cellranger function run with gnuparallel
parallel csProcess ::: $(ls $SAMPLE_DIR)

mv $T .
