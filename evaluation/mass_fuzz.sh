#!/bin/bash

##
# Pre-requirements:
# - env FUZZER: path to fuzzer work dir
# - env TARGET: path to target work dir
# - env OUT: path to directory where artifacts are stored
# - env SHARED: path to directory shared with host (to store results)
# - env PROGRAM: name of program to run (should be found in $OUT)
# - env ARGS: extra arguments to pass to the program
# - env FUZZARGS: extra arguments to pass to the fuzzer
##

#Written and maintained by Akira <jzyakira@gmail.com>
#This is a script which can fuzzing all seeds in a dir on any number of fuzzing tasks each time you want

#At first you should check if Pre-requirments are set appropriately, especially PROGRAM.
#Usage: ./mass_fuzz.sh /home/.../poc_dir /home/.../output_dir 30(parallel fuzzing tasks each time) 1h2m3s(fuzzing duration each time) 
#Harvest:$OUTPUTDIR/$NAME/

mkdir -p "$SHARED/findings"

#flag_cmplog=(-m none -c "$OUT/cmplog/$PROGRAM")
INPUTDIR=$1
OUTPUTDIR=$2
NUM=$3
echo INPUTDIR is $INPUTDIR
echo OUTPUTDIR is $OUTPUTDIR
echo $NUM pocs will be trim!
export AFL_SKIP_CPUFREQ=1
export AFL_NO_AFFINITY=1
export AFL_NO_UI=1
echo AFL_NO_UI is on!
export AFL_MAP_SIZE=256000
export AFL_DRIVER_DONT_DEFER=1

prepare_env() {
echo "Preparing working dir!"
if test -d $INPUTDIR/seed
then
     rm -r $INPUTDIR/seed
     mkdir $INPUTDIR/seed
else
     mkdir $INPUTDIR/seed
fi
echo "Preparing working dir Done!"
}

NOT_FIN=0

launch_fuzzing_process() {
echo "we are launching!"
PROCESS_NUM=$1
for POC in $INPUTDIR/*
do
     if [$PROCESS_NUM -le 0]
     then 
          break
     elif test -d $POC
     then
         continue
     else
	    NAME=$(basename $POC)
     	if test ${NAME:0:3} != 'fzd'
     	then
          NOT_FIN=1
	      mkdir $INPUTDIR/seed/$NAME"_dir"
	      cp $POC $INPUTDIR/seed/$NAME"_dir"
	      timeout -s SIGINT $2 "$FUZZER/repo/afl-fuzz" -m none -C -i $INPUTDIR/seed/$NAME"_dir" -o "$OUTPUTDIR/$NAME" \
              $FUZZARGS -- "$OUT/afl/$PROGRAM" $ARGS 2>&1 &
          echo "fuzzing $POC !"
	      let PROCESS_NUM--
	      NEW_NAME="fzd_"$NAME
          mv $POC $INPUTDIR/$NEW_NAME
    	fi
    fi
done
}


while true
do
    prepare_env
    NOT_FIN=0
    launch_fuzzing_process "$NUM" "$4"
    if [ $NOT_FIN == 0 ]
    then
	    echo "all poc are fuzzed !!!"
        exit
    fi
    sleep $4
    sleep 5s
done


echo mass_fuzz.sh ends !!!

