#!/usr/bin/env bash
B=http://127.0.0.1:8080; J=/tmp/pj2.txt; PY=/home/ubuntu/audio-portal/venv/bin/python
prop() { (cd /home/ubuntu/audio-portal && $PY -c "import display;print(display.get_prop('$1'))"); }
rm -f $J; curl -s -c $J $B/login >/dev/null
curl -s -b $J -c $J -o /dev/null --data-urlencode username=admin --data-urlencode password=El0vwUbgSA-oMRZj $B/login
CSRF=$(curl -s -b $J $B/ | grep -oE 'name="csrf" content="[^"]+"' | sed 's/.*content="//; s/"$//')
post() { curl -s -b $J -H "X-CSRF: $CSRF" -H "X-Requested-With: fetch" --data "$1" $B$2 >/dev/null; }
echo "idle pan:        $(prop video-pan-x) $(prop video-pan-y)   (moving)"
post "audio_id=9&video=1&minutes=1" /play
sleep 3; echo "during video 1:  $(prop video-pan-x) $(prop video-pan-y)   (must be 0 0)"
sleep 2; echo "during video 2:  $(prop video-pan-x) $(prop video-pan-y)   (must be 0 0)"
post "x=1" /stop; sleep 3
echo "after stop path: $(prop path | sed 's#.*/##')   pan: $(prop video-pan-x) $(prop video-pan-y)"
rm -f $J
