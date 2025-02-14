#!/bin/bash

# List of node names
nodes=(
"musing-hypatia-4224660914"
"musing-joliot-3388638740"
"musing-keldysh-2869136091"
"naughty-newton-750302637"
"nice-jang-3245469233"
"nostalgic-hertz-217202897"
"objective-elgamal-515085459"
"peaceful-haibt-1734939770"
"peaceful-liskov-3537221843"
"pedantic-kirch-593082407"
"pedantic-napier-6728647"
"pedantic-ramanujan-2091422996"
"practical-johnson-793550544"
"priceless-yalow-2504292798"
"quizzical-heyrovsky-2640803887"
"quizzical-tharp-1161057499"
"relaxed-lamarr-1686853392"
"reverent-poincare-642181579"
"romantic-mestorf-4256936245"
"romantic-noether-1366574264"
"romantic-yalow-186117780"
"sad-antonelli-2543811744"
"serene-cerf-3382945628"
"stoic-nobel-188854297"
"strange-gates-40741159"
"strange-snyder-1614915876"
"thirsty-varahamihira-3125282894"
"trusting-leavitt-2324153520"
"unruffled-murdock-3719950854"
"upbeat-carson-856573686"
"upbeat-curran-4074551529"
"upbeat-nash-4184561948"
"wizardly-ellis-1381247853"
"wonderful-lumiere-2885320408"
"xenodochial-gauss-1373677520"
"xenodochial-roentgen-1161549882"
)

# Loop through each node and delete
for node in "${nodes[@]}"
do
  echo "Deleting node: $node"
  kubectl delete node "$node" --force
done

echo "All specified nodes have been requested for deletion."

