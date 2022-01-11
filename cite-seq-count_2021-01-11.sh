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

# README
# this script should be executed from site of output dir
# fastqs should be arranged in dirs labeled by sample
# make note not to leave trailing / in param paths

set -a

# params
PROJ_DIR=		# /path/to/proj/dir
SAMPLE_DIR=$PROJ_DIR/	# /proj/subdir/to/fastqs
R1=			# /path/to/R1.fastq
R2=			# /path/to/R2.fastq
T=			# /path/to/tags.csv
CBF=			# first position barcode
CBL=			# last position barcode
UMIF=			# first position umi
UMIL=			# last position umi
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
		-cbf $CBF \
		-cbl $CBL \
		-umif $UMIF \
		-umil $UMIL \
		-cells $CELLS \
		-o $1
	}
#done

export -f csProcess

# cellranger function run with gnuparallel
parallel csProcess ::: $(ls $SAMPLE_DIR)

