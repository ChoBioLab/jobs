
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

# this script should be executed from site of output dir
# fastqs should be arranged in dirs arranged by sample
# dirs should carry sample name

# params
PIPELINE=count               # name of cr pipeline
PROJ_DIR=/home               # /path/to/proj/dir
REF_DIR=/ref_dir                # /path/to/gene/refs
GENE_REF=/gene_ref               # name of gene ref
SAMPLE_DIR=$PROJ_DIR/fastqs   # /proj/subdir/to/fastqs

################################################################################

#module load cellranger parallel

if [[ $PIPELINE == "count" ]]
then
    GENOME_LABEL=transcriptome
else
    GENOME_LABEL=reference
fi

# core cellranger function
for i in *
#for i in $(seq 1 $COUNT)
do
echo "
cellranger $PIPELINE \
  --id=cr_$PIPELINE_$i_`date '+%F_%H%M'` \
  --$GENOME_LABEL=$REF_DIR/$GENE_REF \
  --fastqs=$SAMPLE_DIR \
  #--sample=$SAMPLE_PREFIX
  --sample=$i
"
done
