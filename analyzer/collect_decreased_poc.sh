#!/bin/bash

# Written and maintained by Jiang Xiyue <xiyue_jiang@outlook.com>

help_msg() {
    echo "Usage:"
    echo "collect_decreased_poc.sh < -i S_DIR > < -o D_DIR > < -b binary > [ -a args ]"
    echo ""
    echo "Description:"
    echo "S_DIR, the path of decreased PoCs."
    echo "D_DIR, the path for storing collected PoCs."
    echo "binary, the target binary."
    echo "args, the args of target binary."
    exit -1
}

if [ $# -eq 0 ]
then 
    help_msg
fi

while getopts 'i:o:b:a:h?' OPT; do
    case $OPT in
        i) S_DIR="$OPTARG";;
        o) D_DIR="$OPTARG";;
        b) BIN="$OPTARG";;
        a) ARGS="$OPTARG";;
        h) help_msg;;
        ?) help_msg;;
    esac
done

AFL_TMP=/tmp/tmp_$(basename $S_DIR)
BM_SIZE_O=/tmp/tmp_$(basename $S_DIR)/bm_size
BSF=$(dirname $0)/bitmap_size_formatter.py

mkdir $AFL_TMP $BM_SIZE_O
for i in $(ls $S_DIR); do
    # Record bitmap size of each decreased PoC.
    /magma/fuzzers/afl_asan/repo/bitmap-size -C -m none -i $S_DIR/$i/default/queue/ -o $AFL_TMP -- /magma_out/$BIN $ARGS >$BM_SIZE_O/$i.bitmap_size
    # Src file is the PoC, whose bitmap size is the smallest.
    src=$(python $BSF $BM_SIZE_O/$i.bitmap_size | sort -nk 2 | head -n1 | awk '{print $4}')
    # Copy the PoC with smallest bitmap size to the collection directory, add a "_concise" suffix.
    cp $S_DIR/${i}/default/queue/$src $D_DIR/${i}_concise
done

