#!/bin/sh
# Downloads the Commons test photos (see CREDITS.md) into photos/raw/commons/.
cd "$(dirname "$0")/.." && mkdir -p photos/raw/commons
while read name url; do
  curl -s -4 -f --retry 3 -A "effort-budget (github.com/Phantom8420/Hacktoberfest)" -o "photos/raw/commons/$name" "$url" && echo "$name"
done < eval/commons_photos.txt
