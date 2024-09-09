#!/bin/bash

# reference: https://solvedac.github.io/unofficial-documentation/#/operations/getProblemsCountGroupByLevel

echo '' > problem_level_mapping.csv

result=$(seq 1 35000 | paste -sd "," - | sed 's/\([^,]*,\)\{100\}/&\n/g')

IFS=$'\n' read -rd '' -a number_array <<< "$result"

for i in "${!number_array[@]}"; do
    number_array[$i]=${number_array[$i]%?} # remove last comma

    echo "Processing $((i+1))th group..."
    response=$(curl -s --request GET \
        --url "https://solved.ac/api/v3/problem/lookup?problemIds=${number_array[$i]}" \
        --header 'Accept: application/json' --header 'x-solvedac-language: ko')

    echo $response | jq -r '.[] | "\(.problemId),\(.level)"' >> problem_level_mapping.csv
    sleep 5
done

echo "Done."
