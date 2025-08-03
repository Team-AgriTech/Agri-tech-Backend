import joblib
import pandas as pd
import numpy as np

model = joblib.load('Models/xgboost_model.pkl')
ohe = joblib.load('Models/onehot_encoder.pkl')

new_data = pd.DataFrame({
    'ELEVATION': [2997.0, 2000, 500],
    'SLOPE': [42.94040, 25, 5],
    'LANDCOVER': ['Forest', 'Grassland', 'Others'],
    'T2M': [-5.73, 15, 25],
    'RH2M': [35.90, 60, 40],
    'WS2M': [1.45, 3, 1],
    'ssm(m³/m³)': [0.151760	, 0.15, 0.05]
})

# Preprocess the new data: One-hot encode 'LANDCOVER'
landcover_new_data = new_data[['LANDCOVER']]
landcover_encoded_new = ohe.transform(landcover_new_data)

# Create a DataFrame from the encoded features with appropriate column names
feature_names = ohe.get_feature_names_out(['LANDCOVER'])
landcover_encoded_new_df = pd.DataFrame(landcover_encoded_new, columns=feature_names, index=new_data.index)

new_data_processed = new_data.drop('LANDCOVER', axis=1).reset_index(drop=True)
new_data_processed = pd.concat([new_data_processed, landcover_encoded_new_df], axis=1)

predictions = model.predict(new_data_processed)

print("Predictions:", predictions)