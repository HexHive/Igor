#!/bin/bash
for file in $1/*
do
	name=$(basename $file)
	if [ ${name:0:3} = 'fzd' ]
	then
		mv $file $1/${name:4}
	fi
done
