# Model weights

Copy your trained model into this folder before uploading to GitHub:

```
C:\Users\seela\Documents\Term4\water_quality\weights\best.pt  ->  weights\best.pt
```

The app uses this file automatically when the Windows path in `config.py` does not exist
(for example on Streamlit Community Cloud).

GitHub refuses files larger than 100 MB. A YOLOv8n/YOLO11n `best.pt` is usually 5-20 MB, which is fine.
