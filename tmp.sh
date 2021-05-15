#DIR=$1
#FILE=$2
#cd $DIR
COUNT=8 		# number of samples

module load cellranger parallel
cd /hpc/users/tastac01/ctastad/projects/conv_covid_seq/analysis

## direct path of config cs should be give as first argument
cr_multi () {
  cellranger multi \
    --id=cr_multi_$1_`date '+%F_%H%M'` \
    --csv=$1.csv
}

export -f cr_multi 		# export cr function to env for parallel

# iterate through generation of config csv per sample
for i in $(seq 1 $COUNT); do
  cp cellranger_multi_config_template.csv TD005310-CP-$i.csv
  sed -i -e "s/\*\*\*/$i/g" TD005310-CP-$i.csv
done

# execute cellranger in parallel
find TD005310-CP-* | cut -d. -f1 | parallel cr_multi {}

rm TD005310-CP-*