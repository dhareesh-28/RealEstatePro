import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import LabelEncoder
import joblib

def train_model():
    # Load the dataset
    df = pd.read_csv('chennai_housing_data_1000.csv')
    
    # Preprocessing
    # Encode categorical variables
    le_location = LabelEncoder()
    le_property_type = LabelEncoder()
    le_condition = LabelEncoder()
    
    df['location_encoded'] = le_location.fit_transform(df['location'])
    df['property_type_encoded'] = le_property_type.fit_transform(df['property_type'])
    df['condition_encoded'] = le_condition.fit_transform(df['condition'])
    
    # Features and target
    X = df[['location_encoded', 'property_type_encoded', 'sq_ft', 'bedrooms', 
            'bathrooms', 'year_built', 'parking_spaces', 'condition_encoded']]
    y = df['price']
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    print(f"Model trained with MAE: {mae:.2f}, R2 Score: {r2:.2f}")
    
    # Save model and encoders
    joblib.dump(model, 'price_predictor_model.pkl')
    joblib.dump(le_location, 'location_encoder.pkl')
    joblib.dump(le_property_type, 'property_type_encoder.pkl')
    joblib.dump(le_condition, 'condition_encoder.pkl')
    
    return model, le_location, le_property_type, le_condition

def predict_price(location, property_type, sq_ft, bedrooms, bathrooms, year_built, parking_spaces, condition):
    try:
        # Load model and encoders
        model = joblib.load('price_predictor_model.pkl')
        le_location = joblib.load('location_encoder.pkl')
        le_property_type = joblib.load('property_type_encoder.pkl')
        le_condition = joblib.load('condition_encoder.pkl')
        
        # Encode categorical features
        location_encoded = le_location.transform([location])[0]
        property_type_encoded = le_property_type.transform([property_type])[0]
        condition_encoded = le_condition.transform([condition])[0]
        
        # Create feature array
        features = [[location_encoded, property_type_encoded, sq_ft, bedrooms, 
                     bathrooms, year_built, parking_spaces, condition_encoded]]
        
        # Predict price
        price = model.predict(features)[0]
        return round(price, 2)
    except Exception as e:
        print(f"Error in prediction: {e}")
        return None

# Train the model when this file is run directly
if __name__ == '__main__':
    train_model()