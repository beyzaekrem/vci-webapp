SOURCE_FOLDER="Capture/xxxxx"
DESTINATION_PATH="/data/vci"

#rsync -avz "$SOURCE_FOLDER" -e ssh vci-gpu1:$DESTINATION_PATH
rsync -Pav "$SOURCE_FOLDER" vci-gpu1:$DESTINATION_PATH