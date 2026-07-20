#python src/capture_replay.py -n 2026_02_03_orbbec_test --fps 15 -f 144:160:6 198 282 -o CAPTURE/orbbec --cams "C*" "D*" --preview-images EVERY_FRAME --processing processed_depth
#python src/capture_replay.py -n 2026_02_03_orbbec_test_001 --fps 15 -f 24:108:6 -o CAPTURE/orbbec --cams "C*" "D*" --preview-images EVERY_FRAME --processing processed_depth

#python src/capture_replay.py -o GPU1/pfeifer/capture/bonn_tele_bench_avif -n bonn_tele_bench --series 6 17 27  --processing SMOL --quality avif --fps 25

# re-download C0030
python scripts/capture/replay.py -n bonn_tele_bench -o GPU1/pfeifer/capture/bonn_tele_bench_avif --no-preview --no-calib --cams C0030 --quality avif --processing SMOL --fps 25 --series

python scripts/capture/replay.py -n 2026_02_03_orbbec_test --fps 15 -o GPU1/pfeifer/capture/orbbec_pth --cams "D*" --no-preview --processing processed_depth --quality torch:32 --no-mattes -f 42 66 120:160:6 198 282 --legacy-ouput-structure
python scripts/capture/replay.py -n 2026_02_03_orbbec_test_001 --fps 15 -o GPU1/pfeifer/capture/orbbec_pth --cams "D*" --no-preview --processing processed_depth --quality torch:32 --no-mattes -f 24:108:6 --legacy-ouput-structure

python scripts/capture/replay.py -n voludogs --fps 60 -o GPU1/pfeifer/capture/voludogs --processing processed --legacy-output-structure --quality avif



python scripts/capture/replay.py -n DATE_orbbec --series --video 15 -o GPU1/pfeifer/capture/orbbec --processing processed_depth --legacy-output -f ::10 --cams D* --quality torch:32 --no-preview --no-mattes 
python scripts/capture/replay.py -n DATE_orbbec --series --video 15 -o GPU1/pfeifer/capture/orbbec --processing processed_depth --legacy-output -f ::10 --cams "C*" "D*" --quality png