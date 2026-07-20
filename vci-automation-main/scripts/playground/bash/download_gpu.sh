SOURCE_FOLDER="/data/pfeifer/capture/bonn_tele_bench_avif"
DESTINATION_PATH="/home/ximea/Sciebo/Capture/public/"

for i in ["bonn_tele_bench_001", "bonn_tele_bench_003", "bonn_tele_bench_015"]; do
    #rsync -avz "$SOURCE_FOLDER" -e ssh vci-gpu1:$DESTINATION_PATH
    rsync -Pav -e ssh vci-gpu1:"$SOURCE_FOLDER/$i" $DESTINATION_PATH